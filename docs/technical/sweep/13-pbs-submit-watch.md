# PBS 批量提交 + 运行中监控(v0.14.0 / 架构)

> **面向开发者:** 理解 `cluster.py` / `batch.py` / `monitor.py` 三个模块的内部架构、
> 数据流、调度器抽象、与既有 sweep 系统的集成点。
>
> **配套用户文档:** [`../../user-manual/20-pbs-cluster.md`](../../user-manual/20-pbs-cluster.md)
>
> **本文不覆盖:** sweep 本身的批量算例生成 — 看 [01-sweep-overview](01-sweep-overview.md)。

## 1. 模块全景

v0.14.0 引入 3 个新模块 + 1 个扩展,共 **+2531 行生产代码**:

| 模块 | 行数 | 职责 |
|---|---|---|
| `inp_tool.cluster` (Phase 1) | 659 | 调度器抽象 + SSH 客户端 + 配置持久化 |
| `inp_tool.batch` (Phase 2+3+5+6) | ~750 | sweep 提交/状态/取消/重跑的批量逻辑 |
| `inp_tool.monitor` (Phase 4) | 427 | mcfd.info0 解析 + 运行中监控 |
| `inp_tool.pbs` (Phase 0 扩展) | +98 | 任务名校验(扩展既有) |
| `inp_tool.cli` (扩展) | +600 | 6 个新子命令 |
| `inp_tool.__init__` (扩展) | +30 | 30+ 新公共 API |

数据流:

```
sweep_report.json                    cluster.json
       │                                │
       ▼                                ▼
   ┌──────────┐    ┌──────────┐    ┌─────────────┐
   │  batch   │◄──►│  cluster │◄──►│ SshCluster  │──► SSH
   │ submit   │    │  status  │    │  Client     │     │
   │ status  │    │  cancel  │    └─────────────┘
   │ cancel  │    │  parse   │           │
   │ rerun   │    │  rsync   │           ▼
   │ query_* │    └──────────┘      mcfd.info0 + minfo0.mpf1d
   └──────────┘           │              │
       │                  │              ▼
       ▼                  ▼         ┌──────────┐
   manifest.json   PbsJobStatus     │ monitor  │──► CaseProgress
   (patched)                          │ refresh  │
                                      │ history  │
                                      │ watch    │
                                      └──────────┘
```

---

## 2. 关键设计决策

### 2.1 零运行时依赖

`cluster.py` / `batch.py` / `monitor.py` 全部**纯 stdlib**(json / time / tempfile / dataclasses / enum / re / pathlib / subprocess)。

- ✅ 沿用 `inp_tool` 核心零依赖原则(参考 `pbs.py` / `sweep.py`)
- ✅ 不引入 `paramiko`(用 `subprocess.run` 调系统 ssh)
- ✅ 未来 `resid_tool` 可共享 `parse_info0_meta()` 而不引入新依赖

### 2.2 调度器可插拔(双调度器适配)

```python
class SchedulerType(str, Enum):
    TORQUE = "torque"      # 10.10.10.251 默认
    SLURM = "slurm"        # 旧参考实现
    PBSPRO = "pbspro"      # 留接口
```

`TorqueAdapter` / `SlurmAdapter` 是**类**(不是 enum 值),提供 `parse_submit_stdout` / `parse_qstat_f` / `parse_squeue` 等**静态方法**。

为什么不直接用 enum + 分发:

- 不同调度器命令名不同(qsub vs sbatch)→ 调法简单 if/else 就够
- 解析逻辑差异大(`qsub` 输出 `1234.head01`,sbatch 输出 `Submitted batch job 1234`)
  → 用类封装,各调度器独立维护

### 2.3 集群配置全 dataclass + JSON 持久化

`ClusterConfig` 是**单一 dataclass**,所有字段(连接/调度器/队列/限流/资源/路径/列映射)都可配置,默认反映 10.10.10.251 集群。

```python
@dataclass
class ClusterConfig:
    host: str = "10.10.10.251"
    user: str = "root"
    auth_method: str = "ssh-key"
    ssh_key: Optional[str] = None
    # ... 共 30+ 字段
```

持久化用 `to_dict` / `from_dict` + `save` / `load`,写到 `~/.inp_tool/cluster.json`(Win/Linux 都支持,自动选 `HOME` 或 `USERPROFILE`)。

**为什么不用 yaml/toml 配置?** 保持零依赖 + 简单,JSON 就够。

### 2.4 ClusterClient Protocol 而非 enum

```python
class ClusterClient:
    def probe(self) -> ClusterInfo: ...
    def submit(self, script_text, *, remote_dir, pbs_overrides=None) -> str: ...
    def status(self, job_id) -> PbsJobStatus: ...
    # ... 共 9 个方法
```

两个实现:

- `SshClusterClient`: 真 SSH(subprocess + sshpass + rsync)
- `LocalDryRunClient`: 不真提交,只记录命令

**为什么用 base class + 子类 而非 Protocol?** Python 3.8 `typing.Protocol` 运行时不能 check,base class 让 IDE 跳转更友好,且子类可继承公共方法。

### 2.5 submit_sweep 复用 pbs.write_pbs

`batch.py:submit_sweep` 不重新实现 pbs 脚本生成,直接复用 `pbs.write_pbs()`:

```python
# pbs.py
def write_pbs(template_path, output_path, job_name, template_text=None) -> None:
    # 替换 #PBS -N,写出到 case_dir/

# batch.py
script_text = _load_script_text(case_dir, pbs_template, pbs_name)
job_id = cluster.submit(
    script_text=script_text,
    remote_dir=remote_case_dir,
    pbs_overrides=pbs_overrides,
)
```

这样**v0.14.0 不重复造 pbs 生成逻辑**,且自动继承 v0.14.0 Phase 0 的 -N 校验。

### 2.6 mcfd.info0 列名动态读

`monitor.py:parse_info0_meta()` 解析 `minfo0.mpf1d`(CFD++ 写出的元数据文件),不 hardcode 列名:

```python
def parse_info0_meta(text: str) -> Dict[str, int]:
    # "variables 8" 段后的 8 行是列名
    # 返回 {"step#": 0, "time": 1, "CFL_global": 5, ...}
```

这样:

- 不同 CFD++ 版本改了列名顺序也能自动适应
- 用户在 `cluster.json` 覆盖 `col_cfl_global` 等也能生效

⚠️ **CFD++ 内部命名约定 vs 用户直觉**(用户文档 §5.2 详述):

| minfo0.mpf1d 列名 | 实际含义 |
|---|---|
| `CFL_global` | `cflglo` 残差上界 (常值 1e15) |
| `CFL_local` | **真实 CFL ramp** (0.1→20.0) |

`monitor.py` 走 column **index** 而非 name 拿值,所以 `--col-cfl-global 6` 能切到真实 CFL。

### 2.7 并发限流(暂停等待)

`batch.py:submit_sweep` 默认**尊重** `max_concurrent_jobs`:

```python
while True:
    current = cluster.check_concurrency(user)
    if current < max_concurrent:
        break
    if waited >= wait_timeout_seconds:
        result.failed.append((case_dir, "concurrency limit timeout"))
        break
    time.sleep(wait_poll_interval)
    waited += wait_poll_interval
```

设计权衡:

- **暂停等待 vs 报错退出**: 用户答 (a) 暂停等待 → 实现
- **5 min 超时**: 避免永久卡死
- **`--no-respect-concurrency`**: 留个 escape hatch

### 2.8 sweep_report.json patch 策略

`submit_sweep` 调 `_patch_manifest`,把结果写到原 `manifest.json`:

```python
def _patch_manifest(report_path, manifest, result):
    existing = list(manifest.get("pbs_submissions", []))
    # 过滤掉本次重提的同名 case
    new_submission_dirs = {s.case_dir for s in result.submissions}
    kept = [s for s in existing if s.get("case_dir") not in new_submission_dirs]
    # 追加本次新的
    kept.extend(s.to_dict() for s in result.submissions)
    manifest["pbs_submissions"] = kept
    report_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
```

**追加而非覆盖**: 这样重提同 case 不会丢老 entries 的 state=C(已完成)等历史。

---

## 3. 数据契约(跨模块)

### 3.1 `manifest.json` 字段(扩展)

```python
{
    # 既有字段(sweep.py 写)
    "template": str,
    "total": int,
    "cases": [Case, ...],          # 必含 pbs_name (per_dir + pbs 模式)
    "layout": "per_dir" | "flat",
    "source_dir": str,
    "copy_strategy": str,
    "exclude": [str, ...],
    "template_sha256": str,
    "generated_at": "2026-06-13T10:00:00",

    # v0.14.0 新增字段(Phase 2 写)
    "pbs_submissions": [
        {
            "case_dir": str,           # 本地路径
            "case_name": str,          # basename
            "job_id": str,             # qsub 返回的 job_id
            "pbs_name": str,           # 替换过的 #PBS -N
            "submit_time": "2026-06-13T10:00:00",
            "state": "Q",              # 提交时 Q;Phase 3/4 更新
            "host": str,
            "queue": str,
            "pbs_template": str | null,
            "script_remote": str | null,
        },
        ...
    ],
}
```

### 3.2 `cluster.json` 字段(全字段)

见 [`ClusterConfig`](../../user-manual/20-pbs-cluster.md) dataclass 定义,30+ 字段,全部可配。

### 3.3 `mcfd.info0` 格式(读)

```
<step>  <time>  <time_step_size>  <RHS_avg>  <RHS_max>  <CFL_global=残差上界>  <CFL_local=真实CFL>  <eigenvalue_max>
  2000   0.0e+00    2.121e+10       216.8       2.5e+07       1.0e+15                 2.0e+01           4.7e+04
```

- 1 行/步, 8 列(默认), 无表头
- 列名从 `minfo0.mpf1d` 动态读

### 3.4 `minfo0.mpf1d` 格式(读)

```
title
mcfd.info0 output
variables 8
step#
time
time_step_size
RHS_average
RHS_maximum
CFL_global
CFL_local
eigenvalue_max
variablesets 0
```

- 头 1 行: `title`
- 第 2 行: 输出文件名(`mcfd.info0 output` 等)
- `variables N` 段 + N 行列名
- `variablesets 0` 收尾

---

## 4. 与 sweep 的集成

### 4.1 数据流

```
1. 用户跑 `inp-tool sweep` → 生成 manifest.json + All/case_*/ 目录
2. (可选) `inp-tool pbs submit All/manifest.json` → ssh + rsync + qsub
3. `inp-tool pbs watch All/manifest.json` → ssh tail mcfd.info0 + parse
4. 作业完成 → 拉结果(sweep 不管;用户自己 rsync 或 SIMS 界面)
```

### 4.2 触发条件

`pbs` 子命令仅在 **per_dir + pbs 模式**有意义:

```bash
inp-tool sweep ... --pbs/--no-pbs  # 默认 yes(per_dir)
# OR JSON/YAML:
sweep:
  pbs:
    enabled: true
    template: run.pbs
    naming: "Mars-{alpha}-{mach}"
    basename_max_len: 14
```

`pbs_name == null` 的 case(per_dir + pbs disabled 或 flat 模式)会被 `submit_sweep` 跳过(进 `skipped`)。

### 4.3 目录布局约定

```
<remote_workdir>/         # cluster.json remote_workdir
  └── <case_name>/         # case_name = sweep.manifest.cases[].case_id
        ├── mcfd.inp
        ├── run_<pbs_name>.pbs
        ├── mcfd.info0      # 求解时生成
        ├── minfo0.mpf1d
        ├── result.out
        └── ...
```

**重要**: `case_name` 必须和 `case.path` 的 basename 一致(否则监控时找不到 mcfd.info0)。`submit_sweep` 用 `Path(case.path).name` 当 case_name。

---

## 5. 关键测试策略

### 5.1 三层 mock

```python
# Level 1: 纯单元(无 mock)
Info0Parser(meta_path="...").parse_line("...")
parse_info0_meta(SAMPLE_MINFO0_META)

# Level 2: 客户端 mock(用 ClusterClient 子类)
class MockClient(ClusterClient):
    def status(self, job_id):
        return PbsJobStatus(job_id, "n", "u", "R", "q02")
    # ... 其他方法

# Level 3: subprocess mock
monkeypatch.setattr("subprocess.run", fake_run)
inp_tool.cluster.probe_scheduler(...)
```

### 5.2 真实样本回归

`test_monitor.py` 用**真实样本**做断言(从 `reference/full_case/Case/mcfd.info0` 验证 step=2000, cfl=20)。这个样本是用户授权读的文档样本,不是生产数据。

### 5.3 覆盖率目标

- `cluster.py`: 83%(目标 80%)
- `batch.py`: 88%(目标 80%)
- `monitor.py`: 待 CI 报告
- `pbs.py`: 95%(v0.14.0 扩展)
- **总覆盖率**: 80.66%(目标 ≥ 80%)

CI `--cov-fail-under=80` 强制。

---

## 6. 已知坑 / 边界

### 6.1 minfo0.mpf1d 与 mcfd.info0 的数据冗余

`mcfd.rhsav` 也有 5 列残差,和 `mcfd.info0` 的 3/4 列残差重复。v0.14.0 只用 `mcfd.info0`(因为有 step/CFL),不动 `mcfd.rhsav`。

### 6.2 qsub 后的 result.out

v0.14.0 **不自动拉 result.out**。用户要么:

- 自己 SSH 上去看
- 用 `inp_tool` 后续的 `pbs fetch` 命令(暂未实现,见 [§8 未来工作](#8-未来工作))

### 6.3 SweepMonitor.info_meta_path

CLI `pbs watch` 默认从本地 case 目录读 `minfo0.mpf1d`(假设本地和远端文件一致 — 实际应该,因 sweep 同步)。如果 sweep 用 `--source-dir` 从其他位置复制,**minfo0.mpf1d 可能不在 case 目录**,这时 watch 会 fallback 默认 8 列。

修复:让 sweep 把 `minfo0.mpf1d` 也复制到 case 目录(已通过 `CopyStrategy.copy` 解决;`hardlink` / `symlink` 不一定带 minfo0.mpf1d)。

### 6.4 并发限流 vs skip-existing

这两个有微妙交互:
- `skip-existing=True` (默认) 跳过 manifest 里有 pbs_submissions 的 case → 不调 submit → 不查并发
- `skip-existing=False` 重提所有 → check_concurrency() 触发限流暂停

**结论**: 正常工作流(skip-existing=True)不会触发限流;`rerun` / `pbs run` 重提时会触发。

---

## 7. 性能特性

| 操作 | 时间 | 备注 |
|---|---|---|
| `cluster probe` | ~5s | ssh 1 次 + qstat/sinfo 探测 |
| `pbs submit` 1 case | ~3s | 1 次 rsync + 1 次 ssh qsub |
| `pbs submit` 10 cases 串行 | ~30s | 10 次串行 rsync+qsub |
| `pbs status` 10 cases | ~5s | 1 次 ssh qstat 拉全部 |
| `pbs watch` refresh | ~3s | N 次 ssh tail(N cases) |
| `pbs cancel` 5 jobs | ~2s | 5 次 ssh qdel 串行 |

**未做并行**: 提交/取消都是串行。Phase 7+ 可加 `concurrent.futures` 并行(简单)。

---

## 8. 未来工作

| 项 | 优先级 | 说明 |
|---|---|---|
| `pbs fetch --case X` 拉 result.out | 中 | 拉单个 case 结果到本地 |
| `pbs resubmit-failed` 快捷命令 | 低 | 等价于 `rerun --states E` |
| 并行 submit/cancel (`ThreadPoolExecutor`) | 中 | 10+ cases 时省时间 |
| 残差曲线绘图(monitor.plot) | 中 | 接 `resid_tool` 后端,GUI 显示 |
| Web UI 集成(实时刷新) | 低 | inp_tool_web 已经有,可加 SSE |
| 集群资源可视化(队列占用) | 低 | 调 `qstat -Q` + `pbsnodes` |
| `pbs run --watch-mode=rich` | 低 | rich/Textual 美化输出 |

---

## 9. 关联文档

- **用户向:** [`../../user-manual/20-pbs-cluster.md`](../../user-manual/20-pbs-cluster.md)
- **变更日志:** [`../../../CHANGELOG.md`](../../../CHANGELOG.md) v0.14.0 段
- **Plan(已删,历史):** `git log --grep "v0.14.0"`
- **sweep 架构:** [02-sweep-architecture](02-sweep-architecture.md)
- **pbs 模块既有架构:** `inp_tool/inp_tool/pbs.py` (Phase 0 扩展)
- **参考实现(参考代码,非生产):** `reference/code/CFDPlus_V4.py:cmd_check_all` (监控思路来源)

## 10. FAQ(开发者向)

### Q1: 为什么不用 paramiko?

A: 零依赖原则。`subprocess.run(["ssh", ...])` 在所有 Linux/Mac/WSL 都有,无需额外安装。Win7 需装 OpenSSH。

### Q2: 为什么不用 `pexpect`?

A: 同样,零依赖。subprocess + ssh 就够。

### Q3: ClusterConfig 怎么扩展?

A: 加字段 + 给默认值;旧 `cluster.json` 没有该字段时 `from_dict` 跳过(用 `cls(**{k: v for k, v in d.items() if k in valid_keys})`)。CLI 加 `--set KEY=VALUE` 自动支持(看 `cmd_cluster_config`)。

### Q4: SweepMonitor 的 watch 循环怎么打断?

A: `watch()` 内 try/except KeyboardInterrupt,主函数 return 0,CLI 不报错退出。

### Q5: 怎么测真实集群?

A: 用户给 ssh key → 配 `cluster.json` → 用 `inp-tool cluster test` 测连通 → `inp-tool pbs submit --dry-run` 测命令构造 → 真提交 1 个 case 验证。CI 不测真实集群(成本/网络限制)。

### Q6: 为什么 rerun 写临时 manifest 而不是改 submit_sweep 加 case_dirs 参数?

A: 改 submit_sweep 签名影响 API 稳定性 + 临时 manifest 是隔离的好做法(写完即删,不影响原文件)。代价是 1 次磁盘 IO(rerun 调一次)。

### Q7: CFD++ 的 CFL_local 是从 cflbot ramp 到 cfllen 的 — 监控时显示的 current_cfl_local 是瞬时值还是累计?

A: 瞬时值。每步 solver 重写 `mcfd.info0` 末行,`tail_progress()` 取最后一行。所以 `current_cfl_local` 是"当前 step 的 CFL"。
