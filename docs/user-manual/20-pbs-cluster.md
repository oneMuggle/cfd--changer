# PBS 集群批量提交与监控

> **面向用户:** 用 sweep 工具生成算例后,需要把算例推到远端 PBS 集群(10.10.10.251)
> 排队 / 看进度 / 取结果的用户。
>
> **本章适用版本:** `inp_tool` v0.14.0+ (2026-06-14 起)
>
> **依赖:** 完成 [sweep/01-sweeping](sweep/01-sweeping.md) + [sweep/02-config-files](sweep/02-config-files.md)
> 章节,已经能跑 `inp-tool sweep` 生成 `manifest.json`。
>
> **本章不覆盖:** sweep 本身的用法 / 模板编辑 / 字段参考 — 那些在 sweep/ + reference/ 章节。

## 1. 5 分钟跑通

```bash
# 1. 第一次:让 inp-tool 识别集群(只需做一次)
inp-tool cluster probe --host 10.10.10.251 --user root --ssh-key ~/.ssh/id_rsa

# 2. 批量提交(走 dry-run 先看会发什么)
inp-tool pbs submit All/manifest.json --dry-run

# 3. 没问题就真提交
inp-tool pbs submit All/manifest.json

# 4. 看状态
inp-tool pbs status All/manifest.json

# 5. 持续监控 step / CFL / 残差(每 30s 刷新)
inp-tool pbs watch All/manifest.json
```

如果第 1 步成功,后面 4 步就都能用。如果失败,看 [§7 常见问题](#7-常见问题)。

---

## 2. 集群配置(只需做一次)

### 2.1 第一次:探测 + 写配置

```bash
# ssh 远端探测,识别是 torque 还是 slurm
inp-tool cluster probe \
  --host 10.10.10.251 \
  --user root \
  --ssh-key ~/.ssh/id_rsa
```

成功输出:

```
Probing root@10.10.10.251:22 ...
✅ scheduler: torque
   queues: q01, q02
   user: root
   配置已写回: /home/<you>/.inp_tool/cluster.json
```

配置写到 `~/.inp_tool/cluster.json`(Win/Linux 都支持,自动选 `HOME` 或 `USERPROFILE`)。

### 2.2 修改配置

```bash
# 看当前配置
inp-tool cluster config --show

# 改 ssh key(Win7 路径不一样)
inp-tool cluster config --set ssh_key=C:/Users/me/.ssh/id_rsa

# 改默认队列
inp-tool cluster config --set default_queue=q01

# 改并发上限(集群规定 20)
inp-tool cluster config --set max_concurrent_jobs=20

# 改远端工作目录
inp-tool cluster config --set remote_workdir=/home/cfd_user/cases
```

所有字段都可以改,不需要直接编辑 JSON。完整字段列表见 [reference/02-cli-api-reference](reference/02-cli-api-reference.md)。

### 2.3 验证连接

```bash
# 跑通 ssh + qstat (不真提交任何东西)
inp-tool cluster test --host 10.10.10.251 --user root
```

输出 `✅ scheduler: torque` + ssh_key 存在提示 = OK。如果失败,看 [§7.1 ssh 失败排查](#71-ssh-连接失败)。

---

## 3. 批量提交

```bash
# sweep 已生成 All/manifest.json(per_dir + pbs 模式),直接提交
inp-tool pbs submit All/manifest.json
```

输出:

```
提交 /path/All/manifest.json 到 root@10.10.10.251 ...
📊 提交结果(用时 12.3s):
   ✅ 成功: 8
      Mars_a04 → job_id=1234 (queue=q02)
      Mars_a08 → job_id=1235 (queue=q02)
      ...
   ⏭ 跳过: 0
   ❌ 失败: 0
```

`manifest.json` 会被原地修改,加 `pbs_submissions` 段记录每 case 的 job_id。**再次跑** `pbs submit` 默认会跳过已提交的(`--skip-existing`,默认 True)。

### 3.1 常用选项

| 选项 | 作用 | 默认 |
|---|---|---|
| `--limit N` | 只提交前 N 个 case | 全部 |
| `--skip-existing` / `--no-skip-existing` | 跳过/重提已提交 | 跳过 (True) |
| `--dry-run` | 不真提交,只打印 qsub 命令 | False |
| `--queue q01` | 覆盖 `-q` 队列 | cluster.json 的 default |
| `--walltime 08:00:00` | 覆盖 `-l walltime` | default_walltime |
| `--nodes 2 --ppn 24` | 覆盖 `-l nodes` | 1 node / 48 ppn |
| `--max-concurrent-jobs 10` | 覆盖并发上限 | cluster.json 的 max |
| `--no-respect-concurrency` | 强行超限提交(忽略 max_concurrent) | False(尊重限流) |

例:

```bash
# 试投 3 个,看效果
inp-tool pbs submit All/manifest.json --limit 3 --dry-run

# 真投,改用 q01 队列,8 小时 walltime
inp-tool pbs submit All/manifest.json --queue q01 --walltime 08:00:00
```

### 3.2 并发限流

集群规定单用户最多同时跑 20 个 job。`pbs submit` 默认**尊重**这个限制:

- 提交时如发现当前并发 ≥ 20 → **暂停等待**(每 10s 检查一次)
- 5 分钟超时 → 进 `failed` 列表
- 想强行突破:加 `--no-respect-concurrency`

---

## 4. 状态查询

```bash
inp-tool pbs status All/manifest.json
```

输出(终端表格):

```
📊 /path/All/manifest.json 状态(8 case; R=2 Q=6):
case       job_id  state  queue  ncpu  walltime_used  exec_host
---------  ------  -----  -----  ----  -------------  ---------
Mars_a04   1234    R      q02    48    01:23:45       node1/0*48
Mars_a08   1235    Q      q02    -     -              -
...
```

### 4.1 常用选项

```bash
# 只看运行中 + 排队的(过滤掉已完成)
inp-tool pbs status All/manifest.json --filter R,Q

# JSON 输出(给脚本消费)
inp-tool pbs status All/manifest.json --json

# 持续刷新(每 5s 一次,Ctrl-C 退出)
inp-tool pbs status All/manifest.json --watch
```

### 4.2 状态码速查

| 状态 | 含义 |
|---|---|
| `Q` | Queued, 排队 |
| `R` | Running, 运行中 |
| `E` | Exited (异常退出) |
| `H` | Held, 挂起 |
| `C` | Completed, 完成 |
| `Unknown` | qstat 没返回 / 作业已被集群清理 |

---

## 5. 监控 (step / CFL / 残差)

```bash
inp-tool pbs watch All/manifest.json
```

每 30s 刷新一次,显示:

```
⏱  监控 /path/All/manifest.json (interval=30s; 8 case):
case       state  step    CFL_global  RHS_avg  RHS_max  last_update
---------  -----  ------  -----------  -------  -------  ----------
Mars_a04   R      2000    1e+15        216.8    2.5e+07  14:30:01
Mars_a08   R      1850    1e+15        3.2e+03  1.2e+08  14:30:01
...
```

`CFL_global` 列实际是 `cflglo` 残差上界(常值 `1e15`)— **真实 CFL 在 `mcfd.info0` 的 `CFL_local` 列(0.1→20.0 逐步升)**。详见 [§5.2 列名约定](#52-cfd-列名约定)。

### 5.1 常用选项

```bash
# 刷新间隔 10s(默认 30)
inp-tool pbs watch All/manifest.json --interval 10

# 只跑一次不循环
inp-tool pbs watch All/manifest.json --once

# JSON 输出
inp-tool pbs watch All/manifest.json --once --json

# 覆盖列索引(集群 mcfd.info0 列顺序不一样时)
inp-tool pbs watch All/manifest.json \
  --col-cfl-global 4 --col-step 0 --col-time 1
```

### 5.2 CFD 列名约定

CFD++ 的 `minfo0.mpf1d` 列名是**内部命名**, 与用户直觉相反:

| minfo0.mpf1d 列名 | 实际含义 | 数值行为 |
|---|---|---|
| `CFL_global` | `cflglo` **残差上界** | 常值 `1e15` |
| `CFL_local` | **真实 CFL** (从 `cflbot` ramp 到 `cfllen`) | 0.1 → 20.0 |
| `RHS_average` | 全局平均残差 | 求解时下降 |
| `RHS_maximum` | 全局最大残差 | 求解时下降 |

`inp-tool pbs watch` 默认按 `mcfd.info0` 第 5 列(`CFL_global`)取数,**想要真实 CFL 看 `CFL_local` 列(第 6 列,需在 `cluster.json` 配置或 `--col-cfl-global 6` 覆盖)**。

---

## 6. 取消 / 重跑 / 一站式

### 6.1 取消

```bash
# 取消所有 active (默认跳过 C/E 已完成)
inp-tool pbs cancel All/manifest.json

# 取消指定 job_ids
inp-tool pbs cancel All/manifest.json --job-ids 1234,1235,1236

# 包括已完成的也强制删
inp-tool pbs cancel All/manifest.json --all

# 强删(qdel -W 15)
inp-tool pbs cancel All/manifest.json --force
```

输出:

```
🛑 取消结果:
   ✅ 已取消: 5
      1234
      1235
      ...
   ⏭  跳过: 3
      1237 (case=Mars_a12, state=C)
      ...
   ❌ 失败: 0
```

### 6.2 重跑

```bash
# 默认:重跑已完成(C) + 失败(E)的 case
inp-tool pbs rerun All/manifest.json

# 只重跑失败的(E)
inp-tool pbs rerun All/manifest.json --states E

# 只重跑 queued 的(Q)— 比如 Q 卡太久想换队列
inp-tool pbs rerun All/manifest.json --states Q

# 强删 + 重跑
inp-tool pbs rerun All/manifest.json --force-cancel
```

`rerun` = 取消 + 重新提交(原子操作)。

### 6.3 一站式 submit + watch

```bash
# 提交完立即进入 watch 循环
inp-tool pbs run All/manifest.json

# 改用 q01 队列 + 5 分钟刷新
inp-tool pbs run All/manifest.json --queue q01 --interval 300

# dry-run 模式(走 LocalDryRunClient,不真提交)
inp-tool pbs run All/manifest.json --dry-run
```

`pbs run` = `pbs submit` + 立即 `pbs watch` 串起来。Ctrl-C 退出 watch 后,`manifest.json` 已被 `submit` 阶段写过。

---

## 7. 常见问题

### 7.1 ssh 连接失败

```
❌ SSH 失败: ...
```

排查顺序:

1. **手测 ssh**: `ssh -i ~/.ssh/id_rsa root@10.10.10.251 qstat --version` 能跑吗?
2. **key 路径**: Win7 用 `C:/Users/<me>/.ssh/id_rsa`; Linux 用 `/home/<me>/.ssh/id_rsa`
3. **权限**: Linux 上 `chmod 600 ~/.ssh/id_rsa` (key 文件不能 group-readable)
4. **密码 vs key**: 如果用密码,设 `auth_method: password` + `password: ...`(走 sshpass)
5. **ProxyCommand**: 通过跳板机时,设 `proxycommand: "ssh jump -W %h:%p"`

### 7.2 qsub 提交被拒

```
❌ qsub failed: rc=1 stderr=qsub: Bad UID
```

- **错任务名** (>15 字符 / 含空格 / 首字符非字母):看 v0.13 已知 bug,
  v0.14.0 已修。验证 `inp_tool.PBS_NAME_MAX_LEN == 15`
- **队列不存在**: 用 `qstat -Q` 查可用队列,改 `cluster.json` 的 `default_queue` 或 CLI `--queue`
- **资源超限**: `walltime` / `nodes` / `ppn` 超出队列限制,降级或换队列

### 7.3 watch 看不到 step

```
case  state  step  CFL_global  RHS_avg  RHS_max
c0    Q      -     -           -        -
```

- 状态 `Q` 表示作业还没开始计算 → `mcfd.info0` 还没生成
- 切到 `R` 后几分钟会开始有数据
- 若 `R` 状态还是没 step: 远端路径不对,检查 `cluster.json` 的 `remote_workdir` 和 case 子目录命名

### 7.4 真实 CFL 是哪一列?

见 [§5.2 CFD 列名约定](#52-cfd-列名约定)。简言之: `CFL_local` (col 6), 不是 `CFL_global` (col 5)。

### 7.5 取消不了?

```
❌ cancel 失败: cancel 返回 False
```

- 作业可能已被集群自动清理
- 用 `--force` 试试
- 直接 SSH 上去 `qstat -f <job_id>` 看真实状态

### 7.6 怎么同时管理多个 sweep?

`pbs` 子命令每次只读一个 `manifest.json`。要管理多个,起多个终端或写个 shell 循环:

```bash
for d in sweep_alpha sweep_beta sweep_gamma; do
  inp-tool pbs status $d/manifest.json
done
```

---

## 8. 进阶

### 8.1 自动化脚本 (示例)

把整个工作流写进 shell 脚本, 起 cron 定期跑:

```bash
#!/bin/bash
# auto_monitor.sh - 每 5 分钟看一次 sweep 进度,完成/失败的 case 打印通知
set -e
MANIFEST="$1"
inp-tool pbs status "$MANIFEST" --json > /tmp/pbs_status.json
DONE=$(python3 -c "import json; d=json.load(open('/tmp/pbs_status.json')); print(d['summary'].get('C', 0))")
FAIL=$(python3 -c "import json; d=json.load(open('/tmp/pbs_status.json')); print(d['summary'].get('E', 0))")
if [ "$FAIL" -gt 0 ]; then
  echo "[WARN] $FAIL case(s) failed in $MANIFEST" | mail -s "CFD++ 失败通知" me@org.com
fi
echo "[INFO] $MANIFEST: $DONE done, $FAIL failed"
```

### 8.2 集成到现有 Python 流程

```python
from inp_tool import (
    ClusterConfig, SshClusterClient,
    submit_sweep, query_sweep_status, SweepMonitor,
)

cfg = ClusterConfig.load()
client = SshClusterClient(cfg)

# 提交
result = submit_sweep("All/manifest.json", client, limit=10)
print(f"成功 {len(result.submissions)}, 失败 {len(result.failed)}")

# 查状态
entries = query_sweep_status("All/manifest.json", client, filter_states=["R"])
for e in entries:
    print(f"{e.case_name}: step={e.current_step}, cfl={e.current_cfl_local}")

# 监控循环(集成到自己的 main loop)
monitor = SweepMonitor("All/manifest.json", client)
progresses = monitor.refresh_all()
# 你的处理逻辑...
```

### 8.3 不通过 sweep,直接用 cluster API

```python
from inp_tool import ClusterConfig, SshClusterClient

cfg = ClusterConfig.load()
client = SshClusterClient(cfg)

# 提交单个 case(不走 manifest)
job_id = client.submit(
    script_text="#!/bin/bash\n#PBS -N myjob\n...",
    remote_dir="/root/cases/mycase",
)
print(f"已提交: {job_id}")

# 看状态
status = client.status(job_id)
print(f"{status.name}: {status.state}, walltime={status.walltime_used}")

# 取消
client.cancel(job_id)
```

---

## 9. 关联章节

| 想了解 | 看 |
|---|---|
| sweep 怎么生成 manifest.json | [sweep/01-sweeping](sweep/01-sweeping.md) |
| 字段含义 / CLI / API 速查 | [reference/02-cli-api-reference](reference/02-cli-api-reference.md) |
| 集群内部架构(开发者向) | [../technical/sweep/13-pbs-submit-watch.md](../technical/sweep/13-pbs-submit-watch.md) |
| 项目历史(本功能怎么来的) | [../../CHANGELOG.md](../../CHANGELOG.md) v0.14.0 段 |
