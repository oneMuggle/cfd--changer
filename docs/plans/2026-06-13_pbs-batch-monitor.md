# 算例批量提交与 PBS 监控 — 实施计划

| 字段 | 值 |
|---|---|
| **创建日期** | 2026-06-13 |
| **目标版本** | v0.14.0（minor bump — 新增能力） |
| **当前版本** | v0.13.0 |
| **作者** | Claude（基于 brainstorming + 参考实现分析） |
| **状态** | 待用户最终确认 → 切到 `feat/pbs-batch-monitor` 分支 |
| **范围** | `inp_tool` 新增 cluster/batch/monitor 子模块（核心零依赖） |

---

## 1. 背景与目标

### 1.1 背景

`cfd--changer` 项目目前以 `.inp` 前处理（`inp_tool`）为主，CFD++ 实际计算散落在
本地脚本 + 手工 `qsub`。本计划引入**算例批量提交**与**运行中监控**能力，让用户：

- 在本地 sweep 出 N 个 case 后，**一条命令**推到集群（10.10.10.251）排队
- 在计算过程中**准实时**看每 case 的当前步数、CFL、残差曲线
- 与未来 Phase 1 `resid_tool`（后处理）共用残差解析逻辑，零重复

### 1.2 目标（v0.14.0）

1. **修 pbs.py 的 -N 长度 bug**（v0.13 已知问题，15 字符限制未遵守）
2. **集群配置抽象化**（host/user/ssh_key/queue/限流 全配置，不写死）
3. **调度器可插拔**（默认 Torque，可选 Slurm 备）
4. **批量提交**（rsync + qsub + 并发限流）
5. **状态查询**（qstat 解析 + 表格输出 + JSON）
6. **运行中监控**（基于 `mcfd.info0`，列名从 `minfo0.mpf1d` 读，**不**hardcode）
7. ≥ 80% 测试覆盖，零运行时依赖核心

### 1.3 非目标（v0.14.0）

- 2D/3D 场量可视化（Phase 2 / `resid_tool`）
- HTML/PDF 报告（Phase 5）
- 跨集群联邦提交（v0.x+1）
- GUI "提交+监控" 按钮（v0.x+1，CLI 先跑通）
- 求解器调度适配（"按 case 跑 CFD++"） — `reference/code` 那种
  cmd_run_all 的**本地 os.system 方式不学**（无 SSH 抽象）

---

## 2. 关键参考（已落地的硬性事实）

### 2.1 集群环境（来自 `reference/docs/1.md`）

| 维度 | 值 |
|---|---|
| 管理节点 | `10.10.10.251`，root / 密码 6 个 1 |
| 共享存储 | `10.10.10.200/16`（**本计划不直接用**，仅 rsync 推 251） |
| 计算网段 | `10.10.10.1` ~ `.N`（R620/X620/R640 G30） |
| 业务网 / IB / 管理网 | `10.10.10.0/16` / `11.11.11.0/16` / `10.10.20.0/16` |
| 调度器 | **Torque**（开源 PBS，qsub/qstat/qdel/qmgr/pbsnodes/pestat） |
| 队列 | `q01`, `q02`（用户明确列出，可访问；配置可加更多） |
| 监控 Web | `http://10.10.10.251:6080`（SIMS，本计划不集成） |
| **PBS `-N` 限制** | **15 字符，首字符为字母，无空格** ⬅ v0.13 bug |
| MPI 环境 | `/public/software/profile.d/mpi_openmpi-2.1.6.sh` 等 |
| CFD++ 路径 | `/public/software/apps/cfd++/CFD++18.5/mlib/mcfd.18.5/exec/hpmpimcfd` |

### 2.2 真实残差/状态文件（来自 `reference/full_case/Case`）

**`mcfd.info0`** — 1 行/步，8 列，**无内嵌表头**：

```
step#   time    time_step_size  RHS_average  RHS_maximum  CFL_global  CFL_local  eigenvalue_max
  1   0.0e+00   3.201e+10      1.918e+06    7.291e+08    1.000e+15   1.000e-01  3.124e+04
  ...
2000   0.0e+00   2.121e+10      2.168e+02    2.459e+07    1.000e+15   2.000e+01  4.714e+04
```

- **CFL_global**（列 5 = 0.1→20）逐步升 — **CFD++ ramp from `cflbot` to `cfllen`**
- **RHS_average**（列 3）、**RHS_maximum**（列 4）— 残差，监控核心
- **time_step_size**（列 2）— 物理时间步长
- **eigenvalue_max**（列 7）— 谱半径监控

**`minfo0.mpf1d`** — **元数据文件，含列名表**（无扩展名，就是文本）：

```
title
mcfd.info0 output
variables 8
step#              ← 列 0
time               ← 列 1
time_step_size     ← 列 2
RHS_average        ← 列 3
RHS_maximum        ← 列 4
CFL_global         ← 列 5
CFL_local          ← 列 6
eigenvalue_max     ← 列 7
variablesets 0
```

> **本计划 parser 先读 `minfo0.mpf1d` 拿列名 → 动态映射**，不 hardcode。

**`mcfd.rhsav`** — 求解器内部另一格式（2 行/步：step header + 5 残差值），
**不**用于本计划监控。`mcfd.inp` 里相关参数（仅供了解）：

```
cflbot 1.000000e-004    # CFL 下界（启动时）
cfller 0.950000         # ramp 系数
cfllen 20.0             # CFL 上界（最终目标）
cflglo 1.000000e+015    # 全局残差容差
```

### 2.3 已有实现参考（来自 `reference/code/CFDPlus_*.py`）

| 模式 | 位置 | 我们怎么做 |
|---|---|---|
| 批量提交所有 case | `CFDPlus_V4.py:cmd_run_all:1263`（`os.walk` 找 `*.sh` + `sbatch`） | 抽象为 `ClusterClient.submit()`，走 SSH + rsync |
| 停止所有 case | `cmd_end_all:1283`（找 `.out` 抽 job_id + `scancel`） | 抽 `pbs cancel` CLI |
| 查进度 | `cmd_check_all:1303`（读 `mcfd.info0` 末行拿 nstep/ntime） | `CaseMonitor.refresh()`，增量 tail |
| 解析 mcfd.info1（气动力） | `CFDPlus_extract.py:read_info1_file:285` | **本计划不动 info1**（属后处理，Phase 1 resid_tool 范畴） |
| 控制参数 txt | `CFDPlus_V4.py:read_batch_ctrpara:189` | **不学** — 我们已有 `SweepSpec` YAML |
| numpy 依赖 | 全局 `import numpy as np` | **不引入** — inp_tool 核心仍 stdlib only |

### 2.4 已存在的设计文档（**已有重叠，须说明**）

`docs/superpowers/specs/2026-06-02-cfdplusplus-toolkit-phase1-design.md`
提出 `resid_tool` 做**离线**残差 log 解析/绘图（info0/info1 → PNG/HTML）。
状态"未启动"。

**本计划与它的关系**：

| 维度 | 本计划（v0.14.0） | Phase 1 resid_tool |
|---|---|---|
| 时机 | **运行中** | 跑完后 |
| 数据流 | `ssh tail` + 增量 | 全文件 `read` |
| 输出 | 终端表格 + 实时刷新 | PNG / HTML 静态图 |
| 解析 | `mcfd.info0`（`minfo0.mpf1d` 取列名） | `mcfd.info0` + `mcfd.info1` |
| 依赖 | inp_tool + stdlib | `resid_tool` 独立包 + matplotlib/plotly |
| 关系 | 抽 `parse_info0()` 共享函数 | 同 |

**原则**：本计划**不** import `resid_tool`（保持 inp_tool 零依赖）；
双方在 `parse_info0()` 层面对齐接口，未来 resid_tool 落地后可共用。

---

## 3. 实施阶段（**7 个 Phase，11-14 天**）

### Phase 0: 修 pbs.py 的 -N 长度 bug（**0.5 天**）

**文件**: `inp_tool/inp_tool/pbs.py`

| 函数 | 改动 |
|---|---|
| `render_pbs_name(..., max_len=200)` | 默认值改 `15`（15 字符限制） |
| `extract_pbs_basename(..., max_len=8)` | 默认值改 `14`（留 1 给 suffix） |
| **新增** `validate_pbs_name(name: str) -> list[PbsIssue]` | 长度 / 首字符 / 字符集 / 连字符 / 点 全部检查 |
| `write_pbs()` | 写出前调 `validate_pbs_name`，违规则 `raise PbsValidationError` |

**测试**: `inp_tool/tests/test_pbs_name.py`（10+ 用例）

**验收**: 16 字符名字 `assert raises PbsValidationError`；首字符数字同样；空字符串同样。

---

### Phase 1: 集群配置 + 调度器抽象（**3 天**）

**新文件**: `inp_tool/inp_tool/cluster.py`（**stdlib only**）

#### 1.1 调度器抽象

```python
class SchedulerType(str, Enum):
    TORQUE = "torque"      # 10.10.10.251 集群
    SLURM = "slurm"        # 旧参考实现环境
    PBSPRO = "pbspro"      # 留接口

class SchedulerAdapter(Protocol):
    submit_cmd_fmt: str         # "qsub {script}" | "sbatch {script}"
    cancel_cmd_fmt: str         # "qdel {job_id}" | "scancel {job_id}"
    list_cmd: str               # "qstat -f" | "squeue"
    list_user_cmd_fmt: str      # "qstat -u {user}" | "squeue -u {user}"
    status_cmd_fmt: str         # "qstat -f {job_id}" | "squeue -j {job_id}"
    parse_submit_stdout(self, text: str) -> str       # -> job_id
    parse_status(self, text: str) -> list["PbsJobStatus"]
    parse_full(self, text: str) -> list["PbsJobStatus"]

class TorqueAdapter: ...   # 默认
class SlurmAdapter: ...    # 备
```

**用户答复 Q2 = (a) 自动探测**：`probe` 阶段先尝试 `qstat --version` / `pbs_version`，
失败再试 `sinfo` / `squeue --version`，把识别结果写回 `cluster.json` 的 `scheduler` 字段。

#### 1.2 集群配置 dataclass

```python
@dataclass
class ClusterConfig:
    # —— 连接 ——
    host: str = "10.10.10.251"
    user: str = "root"
    port: int = 22
    auth_method: str = "ssh-key"           # ssh-key | password | proxycommand
    ssh_key: Optional[str] = None          # ⬅ Q2: 用户明确要求 Win7/Linux 路径可指定
    ssh_key_passphrase: Optional[str] = None
    password: Optional[str] = None        # 不推荐,fallback
    proxycommand: Optional[str] = None

    # —— 调度器 ——
    scheduler: str = "auto"               # auto-detect on probe
    detected_scheduler: Optional[str] = None   # probe 后填回

    # —— 队列与限流 ——
    available_queues: list[str] = field(default_factory=lambda: ["q01", "q02"])
    default_queue: str = "q02"
    max_concurrent_jobs: int = 20         # ⬅ 用户明确值,配置可改

    # —— 资源默认值 ——
    default_walltime: str = "04:00:00"
    default_nodes: int = 1
    default_ppn: int = 48

    # —— 路径与文件 ——
    remote_workdir: str = "/root/cases"   # 远端 case 推送根目录
    local_ssh_key: Optional[str] = None   # 冗余(== ssh_key),为清晰保留

    # —— 监控文件格式（v0.14.0 关键）——
    info_file: str = "mcfd.info0"         # 监控数据
    info_meta_file: str = "minfo0.mpf1d"  # 列名元数据
    # 列名优先从 info_meta_file 读,失败时用下列默认
    col_step: int = 0
    col_time: int = 1
    col_dt: int = 2
    col_rhs_avg: int = 3
    col_rhs_max: int = 4
    col_cfl_global: int = 5
    col_cfl_local: int = 6
    col_eigenvalue: int = 7
    info_n_columns: int = 8
```

**用户答复 Q1**: 残差列名 → 从 `minfo0.mpf1d` 动态读 `variables N` 段，
**不** hardcode "RHS_average/mass/energy"。本配置里的 col_xxx 提供 fallback。

#### 1.3 客户端

```python
class ClusterClient(Protocol):
    def probe(self) -> "ClusterInfo": ...
    def submit(self, script_text: str, *, remote_dir: str,
               pbs_overrides: Optional[dict] = None) -> str: ...   # -> job_id
    def status(self, job_id: str) -> "PbsJobStatus": ...
    def status_many(self, job_ids: list[str]) -> list["PbsJobStatus"]: ...
    def cancel(self, job_id: str, *, force: bool = False) -> bool: ...
    def list_user_jobs(self, user: str) -> list["PbsJobStatus"]: ...
    def tail(self, remote_path: str, n: int = 50) -> str: ...
    def rsync_to(self, local_dir: str, remote_dir: str,
                 *, exclude: list[str]) -> None: ...
    def rsync_from(self, remote_path: str, local_path: str) -> None: ...
    def check_concurrency(self, user: str) -> int: ...   # 当前 user 的 job 数

class SshClusterClient:        # ssh + rsync + ssh tail
class LocalDryRunClient:       # 单元测试 + --dry-run 模式
```

#### 1.4 CLI

```
inp-tool cluster probe
  --host <h> --user <u> --ssh-key <p>
  # 探测:scheduler 类型 + 队列列表 + mcfd 安装版本 + ssh 延迟
inp-tool cluster config [--init] [--show]
inp-tool cluster test <sweep_dir>
  # 真 ssh + 跑通"探测 + 提交一个测试 case + 取消"
```

#### 1.5 持久化

`~/.inp_tool/cluster.json`（手改或 `cluster config --init` 交互生成）：

```json
{
  "host": "10.10.10.251",
  "user": "root",
  "ssh_key": "C:/Users/me/.ssh/id_rsa",   # Win7 路径例子
  "scheduler": "auto",
  "detected_scheduler": "torque",
  "default_queue": "q02",
  "available_queues": ["q01", "q02"],
  "max_concurrent_jobs": 20,
  "default_walltime": "04:00:00",
  "remote_workdir": "/root/cases",
  "info_file": "mcfd.info0",
  "info_meta_file": "minfo0.mpf1d"
}
```

**测试**: `inp_tool/tests/test_cluster.py`（mock subprocess）+ `test_schedulers.py`（双调度器解析）

---

### Phase 2: 批量提交（**2 天**）

**新文件**: `inp_tool/inp_tool/batch.py`

```python
@dataclass
class PbsSubmission:
    case_dir: str
    case_name: str
    job_id: str
    pbs_name: str
    submit_time: datetime
    host: str
    queue: str
    state: str                       # 提交时一般是 Q
    script_remote: str
    info_overrides: dict = field(default_factory=dict)

@dataclass
class PbsBatchResult:
    submissions: list[PbsSubmission]
    failed: list[tuple[str, str]]    # (case_dir, error)
    skipped: list[str]
    dry_run: bool
    elapsed_seconds: float

def submit_sweep(
    sweep_report_path: str,
    cluster: ClusterClient,
    *,
    dry_run: bool = False,
    limit: Optional[int] = None,
    skip_existing: bool = True,
    pbs_overrides: Optional[dict] = None,
    respect_concurrency: bool = True,    # ⬅ Q3: 默认尊重 max_concurrent_jobs
) -> PbsBatchResult: ...
```

#### 2.1 行为

1. 读 `sweep_report.json` → 对每 case 复用 `pbs.write_pbs()` 生成 per-case 脚本
2. **用户答复 Q3 = (a) 暂停等待**：提交前 `check_concurrency`；如 ≥ `max_concurrent_jobs`：
   - 默认：阻塞 + watch 现有 job 直到空出 slot 再提下一个
   - `--no-respect-concurrency`：直接报错退出，让用户决定
3. `rsync_to` 推整个 case_dir 到 `remote_workdir/<case_name>/`，exclude:
   - `mlog/`, `*.bak`, `*.back`, `nodesout.bin`, `cdepsout.bin`, `cellsout.bin`,
     `mcfd_tec*.bin`, `cgrpsout.bin`, `cdepsin.bin`, `cgrpsin.bin.1`, `__pycache__`
4. ssh `cd <dir> && qsub run_<name>.pbs` → 拿 `job_id`
5. patch `sweep_report.json`，加 `pbs_submissions: [...]` 段
6. `--skip-existing`（默认 True）：检查已提交且未取消/未完成的 case，跳过

#### 2.2 CLI

```
inp-tool pbs submit <sweep_dir_or_report.json>
  [--host ... --user ... --ssh-key ...]   # 覆盖 cluster.json
  [--queue q02]                           # 覆盖 -q
  [--walltime 04:00:00]                   # 覆盖 -l walltime
  [--nodes 1] [--ppn 48]
  [--max-concurrent-jobs 20]              # 覆盖 cluster.json
  [--dry-run]                             # 只打印 qsub 命令清单
  [--limit 10] [--skip-existing]          # 跳过/限制
  [--no-respect-concurrency]              # Q3: 强提,忽略限流
  [--exclude PATTERN]                     # 额外排除文件(可多次)
```

**测试**: `inp_tool/tests/test_batch.py`（mock cluster + 并发限流 + skip-existing）

---

### Phase 3: 状态查询（**1.5 天**）

**pbs.py 新增**:

```python
@dataclass
class PbsJobStatus:
    job_id: str
    name: str
    user: str
    state: str                       # Q|R|E|H|C|...（Torque 状态机）
    queue: str
    ncpus: int
    walltime_req: str                # HH:MM:SS
    walltime_used: str
    submit_time: str
    start_time: Optional[str]
    exec_host: Optional[str]
    exit_status: Optional[int]
    raw: dict[str, str]              # 全部 qstat 字段

def parse_qstat_f(text: str) -> list[PbsJobStatus]: ...      # Torque
def parse_squeue(text: str) -> list[PbsJobStatus]: ...       # Slurm
def parse_qstat_u(text: str) -> list[PbsJobStatus]: ...      # -u <user>
```

**CLI**:
```
inp-tool pbs status <sweep.json>
  [--host ...] [--json] [--filter state=R,state=Q]
  [--watch]                          # 持续刷新(默认 5s)
  [--no-color]
```

**测试**: `test_pbs_status.py`（双调度器解析回归）+ `test_cli_pbs.py`

---

### Phase 4: 残差/步数/CFL 监控（**3 天**）

**新文件**: `inp_tool/inp_tool/monitor.py`（**stdlib only**）

```python
@dataclass
class CaseProgress:
    case_name: str
    case_dir_local: str               # 本地路径(可能 None if 纯远程)
    case_dir_remote: str
    job_id: Optional[str]
    state: str                        # 来自 qstat
    current_step: Optional[int]
    current_time: Optional[float]
    current_dt: Optional[float]
    current_cfl_global: Optional[float]
    current_cfl_local: Optional[float]
    current_rhs_avg: Optional[float]
    current_rhs_max: Optional[float]
    current_eigenvalue: Optional[float]
    last_update: datetime
    log_offset: int                   # 增量 tail 字节偏移
    parse_warnings: list[str]

class Info0Parser:
    """mcfd.info0 解析器(列名从 minfo0.mpf1d 读)"""
    def __init__(self, meta_path: Optional[str] = None,
                 config: Optional[ClusterConfig] = None): ...
    def parse_meta(self) -> dict[str, int]: ...    # {"step#": 0, "time": 1, ...}
    def parse_line(self, line: str) -> dict[str, float]: ...
    def tail_progress(self, text: str) -> CaseProgress: ...

class CaseMonitor:
    """单 case 监控。模仿 reference/code/CFDPlus_V4.py:cmd_check_all:1303"""
    def __init__(self, case_name: str, cluster: ClusterClient,
                 config: ClusterConfig): ...
    def refresh(self) -> CaseProgress: ...        # ssh tail + 解析
    def history(self, col: str) -> list[tuple[int, float]]: ...  # 累计
    def plot(self, col: str) -> bytes: ...        # 需 [plot] extras

class SweepMonitor:
    def __init__(self, sweep_report: dict, cluster: ClusterClient,
                 config: ClusterConfig): ...
    def refresh_all(self) -> list[CaseProgress]: ...
    def summary_table(self) -> str: ...           # 终端表格
    def watch(self, interval: int = 30, *,
              once: bool = False, callback=None) -> None: ...
```

#### 4.1 远程 log 拉取策略（避免 IO 风暴）

```
ssh cluster "wc -c <remote>/mcfd.info0"        # 拿总字节数
ssh cluster "tail -c +<offset+1> <remote>/mcfd.info0"  # 增量 tail
# 解析:按 col_step 列找到首个未读 step,记录 log_offset
# 末行 -> CaseProgress
```

**监控状态机**（cli 输出友好化）：

| qstat 状态 | 监控显示 | 说明 |
|---|---|---|
| Q | `⏳ queued` | 排队 |
| R | `▶ running` (step=N, CFL=X) | 跑中 |
| E | `⚠ exit` (exit_code=X) | 异常退出 |
| H | `⏸ held` | 挂起 |
| C | `✓ done` | 跑完 |

#### 4.2 CLI

```
inp-tool pbs watch <sweep.json>
  [--interval 30]
  [--host ... --user ... --ssh-key ...]
  [--info-file mcfd.info0]            # 默认值
  [--info-meta-file minfo0.mpf1d]     # 列名源
  [--col-step 0 --col-time 1 --col-cfl-global 5]   # 列覆盖
  [--res-cols 3,4]                    # 想看的残差列索引(默认 3=RHS_avg, 4=RHS_max)
  [--once]                            # 只跑一次
  [--json] [--no-color]
  [--tail-bytes 8192]                 # 增量 tail 字节
  [--no-fetch-state]                  # 跳过 qstat,只看 info0
```

**测试**: `inp_tool/tests/test_monitor.py`
- `test_info0_parser.py`：列名解析（minfo0.mpf1d）+ 单行解析
- `test_case_monitor.py`：mock ssh tail + 增量偏移
- 真实样本回归（mark=`external`）：读 `reference/full_case/Case/mcfd.info0` 验证

---

### Phase 5/6（可选，2-3 天）: cancel / rerun / run

```
inp-tool pbs cancel  <sweep.json> [--job-ids <csv>] [--all] [--force]
inp-tool pbs rerun   <sweep.json> [--failed-only] [--state C,E]
inp-tool pbs run     <sweep.json>      # = submit + watch 一体
```

---

## 4. CLI/API 表面（汇总）

### 4.1 CLI

```
# 集群
inp-tool cluster probe   --host ... --user ... [--ssh-key ...]
inp-tool cluster config  [--init] [--show] [--set key=value]
inp-tool cluster test    <sweep_dir>

# PBS（双调度器：torque/slurm/pbspro）
inp-tool pbs submit  <sweep_dir_or_report.json>
  [--host ... --user ... --ssh-key ...]
  [--queue ...] [--walltime ...] [--nodes ...] [--ppn ...]
  [--max-concurrent-jobs ...] [--dry-run] [--limit N]
  [--skip-existing] [--no-respect-concurrency] [--exclude PATTERN]

inp-tool pbs status  <sweep.json> [--host ...] [--json]
  [--filter state=R] [--watch] [--no-color]

inp-tool pbs watch   <sweep.json> [--interval 30] [--host ...]
  [--info-file ...] [--info-meta-file ...]
  [--col-step ... --col-time ... --col-cfl-global ...]
  [--res-cols 3,4] [--once] [--json] [--no-color]
  [--tail-bytes 8192] [--no-fetch-state]

inp-tool pbs cancel  <sweep.json> [--job-ids <csv>] [--all] [--force]
inp-tool pbs rerun   <sweep.json> [--failed-only] [--state C,E]
inp-tool pbs run     <sweep.json>      # submit + watch
```

### 4.2 API（FastAPI 扩展 `inp_tool.api`）

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/pbs/submit` | body: `{sweep_report, cluster?, overrides?}` |
| `GET`  | `/api/pbs/status` | ?report=…&host=…&filter=R |
| `GET`  | `/api/pbs/watch`  | ?report=…&once=true&json=true |
| `POST` | `/api/pbs/cancel` | body: `{report, job_ids, force}` |

---

## 5. 关键文件清单

```
inp_tool/inp_tool/
├── pbs.py            # 扩展:+PbsJobStatus +parse_qstat_* +parse_squeue +validate_pbs_name +修 max_len
├── cluster.py        # 新:SchedulerType/Adapter(Torque/Slurm) + ClusterConfig + ClusterClient
├── batch.py          # 新:submit_sweep() + PbsSubmission + PbsBatchResult + 并发限流
├── monitor.py        # 新:Info0Parser + CaseMonitor + SweepMonitor + CaseProgress
├── cli.py            # 加 7 个新子命令(cluster + pbs x6)
└── __init__.py       # 导出

inp_tool/tests/
├── test_pbs_name.py          # Phase 0:长度/首字符/字符集
├── test_cluster.py           # Phase 1:mock subprocess
├── test_schedulers.py        # Phase 1:Torque vs Slurm 解析
├── test_batch.py             # Phase 2:mock cluster + 限流
├── test_pbs_status.py        # Phase 3:双调度器解析
├── test_monitor.py           # Phase 4:info0 解析 + 增量 tail + 列覆盖
├── test_info0_parser.py      # Phase 4:列名从 minfo0.mpf1d 读
└── test_cli_pbs.py           # 端到端 CLI

docs/
├── technical/sweep/13-pbs-submit-watch.md    # 新
├── user-manual/20-pbs-cluster.md             # 新
└── plans/2026-06-13_pbs-batch-monitor.md     # 本文件
```

---

## 6. 测试策略

| 维度 | 测什么 |
|---|---|
| 单元 | 每个模块独立(mock subprocess / cluster / ssh) |
| 集成 | submit_sweep + status + watch 端到端（mock cluster） |
| 真实样本 | `pytest -m external` 读 `reference/full_case/Case/mcfd.info0` |
| 双调度器 | Torque 和 Slurm 解析都跑回归 |
| 错误 | ssh 失败 / 私钥错 / 远端无 qsub / qsub 返回非 job_id / 限流触发 |
| 性能（软目标） | `pbs status` 100 case < 5s；`pbs watch` refresh < 3s |

**目标**: `pytest --cov=inp_tool --cov-report=term-missing` ≥ 80%

---

## 7. 风险与缓解

| 级别 | 风险 | 缓解 |
|---|---|---|
| 🟢 真实样本 | `mcfd.info0` + `minfo0.mpf1d` 格式已确认 | 模仿 `reference/code/CFDPlus_V4.py:cmd_check_all` |
| 🟡 列名假设 | minfo0.mpf1d 在某些 case 可能不存在 | 走 `col_step=0/col_cfl=5` fallback；配置文件可覆盖 |
| 🟡 调度器差异 | Torque vs Slurm 字段名不同 | 抽象 `SchedulerAdapter`；单元测试两边都跑 |
| 🟠 mcfd.info* 多文件 | MPI 进程可能生成 info0/info1/... | 默认只读 `info0`（rank 0 = 聚合），用户可指定 |
| 🟠 Win7 私钥格式 | PuTTY .ppk vs OpenSSH | 文档要求 PuTTY 用户用 `puttygen` 转 .ppk → OpenSSH |
| 🟠 Q3 暂停等待 | 阻塞逻辑死锁（slot 永远空不出） | 加超时：等 5 min 没空就报错退出 |
| 🟡 Q2 自动探测 | 探测失败时 fallback | `cluster.json` `scheduler: "torque"` 显式值优先 |
| 🟢 SSH 私钥 | 路径走 `--ssh-key` 显式 | **不**读 `~/.ssh/config` 默认值 |
| 🟢 队列 | `q01`/`q02` 可配置 | `available_queues` list 可加更多 |

---

## 8. 实施步骤（可勾选）

- [ ] **Phase 0**（0.5 天）: 修 pbs.py -N 长度 bug
  - [ ] `render_pbs_name` `max_len=15`
  - [ ] `extract_pbs_basename` `max_len=14`
  - [ ] 新增 `validate_pbs_name()`
  - [ ] `test_pbs_name.py` 通过
  - [ ] 跑现有 sweep 测试确认没回归
- [ ] **Phase 1**（3 天）: cluster.py
  - [ ] `SchedulerType` + `TorqueAdapter` + `SlurmAdapter`
  - [ ] `ClusterConfig` dataclass
  - [ ] `SshClusterClient` + `LocalDryRunClient`
  - [ ] `cluster probe/config/test` CLI
  - [ ] `~/.inp_tool/cluster.json` 持久化
  - [ ] `test_cluster.py` + `test_schedulers.py` 通过
- [ ] **Phase 2**（2 天）: batch.py
  - [ ] `PbsSubmission` + `PbsBatchResult`
  - [ ] `submit_sweep()` + 并发限流
  - [ ] `pbs submit` CLI
  - [ ] `sweep_report.json` patch 逻辑
  - [ ] `test_batch.py` 通过
- [ ] **Phase 3**（1.5 天）: pbs.py status 解析
  - [ ] `PbsJobStatus` + `parse_qstat_f` / `parse_squeue` / `parse_qstat_u`
  - [ ] `pbs status` CLI + 表格
  - [ ] `test_pbs_status.py` 通过
- [ ] **Phase 4**（3 天）: monitor.py
  - [ ] `Info0Parser`（从 minfo0.mpf1d 读列名 + fallback）
  - [ ] `CaseMonitor.refresh()` 增量 tail
  - [ ] `SweepMonitor.watch()` + 表格
  - [ ] `pbs watch` CLI
  - [ ] `test_monitor.py` + `test_info0_parser.py` 通过
  - [ ] `pytest -m external` 跑真实样本
- [ ] **Phase 5/6**（2-3 天，可选）: cancel/rerun/run
- [ ] **文档 + 收尾**（2 天）
  - [ ] `docs/technical/sweep/13-pbs-submit-watch.md`
  - [ ] `docs/user-manual/20-pbs-cluster.md`
  - [ ] `CHANGELOG.md` v0.14.0 条目
  - [ ] 覆盖率报告 ≥ 80%
  - [ ] PR 提交流程

---

## 9. 验收清单

- [ ] `inp-tool cluster probe` 能识别 Torque
- [ ] `inp-tool pbs submit --dry-run` 100 个 case 输出可读 qsub 命令清单
- [ ] `inp-tool pbs submit` 真提交后 `sweep_report.json` 含 `pbs_submissions` 段
- [ ] `inp-tool pbs status` 10 case < 5s
- [ ] `inp-tool pbs watch` 30s 刷新一次，CPU < 5%
- [ ] `inp-tool pbs watch --once --json` 真实样本（`reference/full_case/Case/mcfd.info0`）能正确读出 step=2000, CFL=20
- [ ] `pytest --cov=inp_tool` ≥ 80%
- [ ] 现有 55+ 测试无回归
- [ ] Win7 + Linux 双平台 key 路径测试覆盖

---

## 10. 复杂度

| 阶段 | 工作量 |
|---|---|
| Phase 0 | 0.5 天 |
| Phase 1 | 3 天 |
| Phase 2 | 2 天 |
| Phase 3 | 1.5 天 |
| Phase 4 | 3 天 |
| Phase 5/6 | 2-3 天（可选） |
| 测试 + 文档 | 2 天 |
| **合计** | **11-14 天** |

---

## 11. 用户答复（已确认）

| Q | 答复 | 影响 |
|---|---|---|
| Q1 残差列名 | 读 `reference/full_case/Case` → 已找到 `minfo0.mpf1d` 给出 `step#/time/time_step_size/RHS_average/RHS_maximum/CFL_global/CFL_local/eigenvalue_max` | `Info0Parser` 动态读列名；不再 hardcode |
| Q2 scheduler 字段 | (a) 自动探测 | `probe` 阶段识别后写回 `cluster.json`；用户改 cluster.json 可强制指定 |
| Q3 并发限流行为 | (a) 暂停等待 | `submit_sweep` 阻塞到有空 slot；超时 5min 后报错 |
| SSH 认证 | SSH 私钥 | `--ssh-key` 必传；Win7/Linux 路径各异 |
| 目录传输 | rsync 推到 251 | Phase 2 默认行为 |
| max_concurrent_jobs | 20（不写死） | `ClusterConfig` 字段，可配置 |
| 队列 | q01, q02（不写死） | `available_queues` list，可加 |

---

## 12. ⏸ 等待最终确认

请回复其一：

- **"yes" / "proceed"** — 我把当前分支 `main` 切到 `feat/pbs-batch-monitor`，从 Phase 0 开始
- **"modify: …"** — 指出要改的地方
- **"再拆细"** — 某个 Phase 想再分细
- **"先只做 Phase 0+1"** — 最小起步：先修 bug + cluster 抽象（不依赖集群访问）
- **"Phase 4 独立 PR"** — 把监控拆成独立 PR，先合 submit+status

---

**附录 A: 与 v0.13 公共 API 的兼容性**

- `pbs.py` 现有公共 API 保持不变：
  - `PbsConfig`, `PbsIssue`, `detect_pbs_template`, `validate_base_case_dir`,
    `render_pbs_name`, `write_pbs`, `extract_pbs_basename` — 签名 + 行为不变
- `max_len` 默认值改动（200→15）属于**修复 bug**，不是 breaking change
  （原 200 字符生成的 pbs_name 本来就提交不了）
- 新增 `validate_pbs_name()` 是新 API
- `sweep.py` / `cli.py` 既有 sweep 子命令不受影响

**附录 B: 不在 v0.14.0 范围**

- 任何 GUI 集成（PySide2 GUI 留 v0.x+1）
- 任何 resid_tool 集成（Phase 1 独立子包）
- 任何 2D/3D 场量（Phase 2）
- 任何 Web UI 集群面板（用 SIMS 即可）
- 任何 CI 集成（CI 仍跑单元测试 + 真集群留给用户 smoke test）
