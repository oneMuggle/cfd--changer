# 14 — 端到端软件使用教程

> 5 个完整工作流,从"命令行一行扫 6 个 case"到"SLURM 集群提交",把 `inp_tool v0.4.0` 在真实工程场景里串起来用。每教程都是 **准备 → 操作 → 预期输出 → 验证** 四段。

---

## 1. 工作流总览

不管你从哪个入口(CLI / Python / Web GUI)开始,整条 CFD 参数扫描流水线都长这样:

```
  模板 mcfd.inp   ──parse──▶  InpFile  ──modify──▶  CaseSweep 配置
   (1 个文件)                    (内存对象)             (YAML / JSON)
                                                          │
                                                          │ generate
                                                          ▼
   报告 / 图表  ◀──ParaView──  N 个 .plt/.vtu  ◀──求解器──  N 个 .inp + manifest.json
```

**`inp_tool` 负责前 4 步**,把 1 个模板变成 N 个可执行的 `.inp`;后 2 步交给求解器和后处理工具。教程 1-5 分别对应这条流水线上的不同姿势。

| 教程 | 适用人群 | 流水线节点 | 入口 |
|---|---|---|---|
| 教程 1 | 想跑第一组扫描的工程师 | 模板 → N 个 .inp | CLI |
| 教程 2 | 非命令行同事 / 教学演示 | 模板 → N 个 .inp | Web GUI |
| 教程 3 | DevOps / 团队协作 | N 个 .inp → 求解 | GitHub Actions |
| 教程 4 | 想改 alpha/ma 之外字段的人 | 模板 → 1 个 .inp(单文件) | CLI `set` |
| 教程 5 | 集群用户 / HPC 团队 | N 个 .inp → 集群 | Python API + sbatch |

---

## 2. 教程 1:从零做一个 alpha-Mach 扫描

**目标:** 用 5 分钟,从一个 1300 行的真实模板 `mcfd_v2_modified.inp` 生成 6 个 case(3 个 α × 2 个 Ma),落到 `./out_aero/`,写出 manifest。

### 2.1 准备

| 项 | 值 | 备注 |
|---|---|---|
| `inp-tool` | 已装,`conda run -n cfdchanger inp-tool --version` 输出 `inp-tool v0.4.0` | 见 [02-安装](02-installation.md) |
| 模板文件 | `inp_tool/examples/mcfd_v2_modified.inp`(随项目提供,~43 KB) | 路径相对仓库根 |
| 工作目录 | 任意空目录(本教程用 `out_aero`) | `mkdir -p out_aero` |
| 配置工具 | 三选一:CLI 快捷 / YAML / JSON | 本教程用 CLI 快捷(最快) |

### 2.2 操作

**步骤 1:试跑(先 dry-run,不写盘)**

```bash
cd /home/fz/project/cfd--changer
conda run -n cfdchanger inp-tool sweep inp_tool/examples/mcfd_v2_modified.inp \
    --alpha 0,4,8 --mach 0.6,0.8 --t-inf 288.15 --p-inf 101325 \
    --naming "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp" \
    --out ./out_aero --dry-run
```

**步骤 2:真跑(拿掉 `--dry-run`)**

```bash
conda run -n cfdchanger inp-tool sweep inp_tool/examples/mcfd_v2_modified.inp \
    --alpha 0,4,8 --mach 0.6,0.8 --t-inf 288.15 --p-inf 101325 \
    --naming "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp" \
    --out ./out_aero
```

**步骤 3:把配置存成 YAML(便于复现)**

```yaml
# sweep_aero.yaml
template: inp_tool/examples/mcfd_v2_modified.inp
output_dir: ./out_aero
sweeps:
  alpha:  [0, 4, 8]            # 3 个
  mach:   [0.6, 0.8]           # 2 个
  T_inf:  [288.15]             # 单值
  p_inf:  [101325.0]           # 单值
naming: "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp"
manifest: { path: ./out_aero/manifest.json }
```

```bash
# sweep_aero.yaml 提交进 git,以后同事一键复现
git add sweep_aero.yaml
conda run -n cfdchanger inp-tool sweep sweep_aero.yaml
```

### 2.3 预期输出

```
[sweep] generated 6 cases -> ./out_aero
  - case_aoa00_ma0.60.inp  (alpha=0.0 mach=0.6 T_inf=288.15 p_inf=101325.0)
  - case_aoa00_ma0.80.inp  (alpha=0.0 mach=0.8 ...)
  - case_aoa04_ma0.60.inp  (alpha=4.0 mach=0.6 ...)
  - case_aoa04_ma0.80.inp  (alpha=4.0 mach=0.8 ...)
  - case_aoa08_ma0.60.inp  (alpha=8.0 mach=0.6 ...)
  - case_aoa08_ma0.80.inp  (alpha=8.0 mach=0.8 ...)
[sweep] manifest -> ./out_aero/manifest.json
```

### 2.4 验证

```bash
# 1) 文件数(6 .inp + 1 manifest)
ls ./out_aero/ | wc -l          # → 7

# 2) 抽查 alpha=8 / mach=0.8 关键字段写进去了
grep -E "^aero_(alpha|ma) " ./out_aero/case_aoa08_ma0.80.inp
# 期望: aero_alpha 8.0   /   aero_ma 0.8

# 3) manifest 可读、total 正确
python -c "import json; m=json.load(open('./out_aero/manifest.json')); print('total:', m['total'])"

# 4) 模板文件没被改过
md5sum inp_tool/examples/mcfd_v2_modified.inp   # 与 git 中版本对比
```

**完成标志:** `./out_aero/` 里有 6 个 `.inp` + `manifest.json`,且原始模板 MD5 不变。

---

## 3. 教程 2:Web GUI 教程(给非命令行同事)

**目标:** 老板/合作方不愿用终端,用浏览器 5 步生成 6 个 case 并下载。

### 3.1 准备

- `inp-tool-api` 已装,模板 `inp_tool/examples/mcfd_v2_modified.inp`
- 浏览器:Chrome / Edge / Firefox 任一(IE 不行)

### 3.2 操作

**步骤 1:启动 Web 服务**

```bash
conda run -n cfdchanger inp-tool-api
# 期望输出:
#   浏览器打开: http://127.0.0.1:8765
#   API 文档:   http://127.0.0.1:8765/docs
# Ctrl+C 停止
```

**步骤 2:浏览器 5 步**

| 步 | 动作 | 位置 | 备注 |
|---|---|---|---|
| 1 | 浏览器开 `http://127.0.0.1:8765/` | 左侧"inp 文件路径"输入框 | 把模板的**绝对路径**粘进去(Windows 写 `D:\...`,Linux 写 `/home/...`),点"加载" |
| 2 | 左侧块列表点 `guiopts` | 主区出现所有 aero_* / cfl* 等字段 | 确认要扫的字段(`aero_alpha` / `aero_ma` / `aero_temp`)存在 |
| 3 | 顶栏点 **Sweep** 切到扫描视图 | "扫描参数" 表单 | 填 alpha = `0, 4, 8`,mach = `0.6, 0.8`,输出目录 = `./sweep_cases`,命名 = `case_aoa{alpha:02.0f}_ma{mach:.2f}.inp` |
| 4 | 点 **生成** | 弹窗显示 `generated 6 cases -> ./sweep_cases` | 如果 4xx/5xx 看 [10-FAQ §Web GUI](10-faq.md) |
| 5 | 文件管理器去 `./sweep_cases/` | 取走 6 个 `.inp` + `manifest.json` | 邮件 / 飞书 / 共享盘都行 |

### 3.3 预期输出

终端:

```
INFO:     Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)
INFO:     127.0.0.1 - "POST /api/files/load HTTP/1.1" 200 OK
INFO:     127.0.0.1 - "POST /api/sweep HTTP/1.1" 200 OK
```

浏览器弹窗:`generated 6 cases -> ./sweep_cases`(列出 6 个文件名,见教程 1)

### 3.4 验证

| 检查 | 命令 | 期望 |
|---|---|---|
| 文件数 | `ls ./sweep_cases/ \| wc -l` | 7(6 个 .inp + 1 个 manifest) |
| 与教程 1 一致 | `diff -q ./sweep_cases/case_aoa00_ma0.60.inp ./out_aero/case_aoa00_ma0.60.inp` | 无输出 |
| API 健康 | `curl -s http://127.0.0.1:8765/api/health \| jq` | `{"status":"ok",...}` |
| Swagger UI | 浏览器开 `http://127.0.0.1:8765/docs` | 列出 12 个端点 |

**完成标志:** 非命令行同事能在 5 分钟内自给自足,不再 @ 你帮忙改 alpha。

---

## 4. 教程 3:CI 自动化(sweep + 求解器)

**目标:** 每次 `git push` 都自动跑一组 baseline sweep,产出 manifest + .inp artifact。**纯示意**,实际工作流按需调整。

### 4.1 准备

- GitHub 仓库已启用 `Actions`
- 模板 `inp_tool/examples/mcfd_v2_modified.inp` + 配置 `ci/sweep_baseline.yaml`
- CI 容器里有 `mcrun` / `cfd++`(本 workflow 仅 sweep,不解算)

### 4.2 操作

**步骤 1:把 sweep 配置进仓库**

```yaml
# ci/sweep_baseline.yaml
template: inp_tool/examples/mcfd_v2_modified.inp
output_dir: ./out_baseline
sweeps:
  alpha: [0, 4, 8]
  mach:  [0.6, 0.8]
  T_inf: [288.15]
  p_inf: [101325.0]
naming: "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp"
manifest: { path: ./out_baseline/manifest.json }
```

**步骤 2:写 GitHub Actions workflow**

```yaml
# .github/workflows/sweep-baseline.yml
name: sweep-baseline
on:
  push: { paths: ['inp_tool/**', 'ci/**'] }
  workflow_dispatch:
jobs:
  sweep:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: conda-incubator/setup-miniconda@v3
        with: { environment-file: environment.yml, activate-environment: cfdchanger }
      - run: conda run -n cfdchanger inp-tool sweep ci/sweep_baseline.yaml
      - uses: actions/upload-artifact@v4
        with: { name: sweep-manifest, path: out_baseline/manifest.json }
      - uses: actions/upload-artifact@v4
        with: { name: sweep-inputs, path: out_baseline/*.inp }
```

**步骤 3:`git push` 触发**

```bash
git add ci/ .github/ && git commit -m "ci: baseline sweep" && git push origin main
# 去 GitHub 仓库 Actions 页面看 run
```

### 4.3 预期输出

| 产物 | 来源 | 用途 |
|---|---|---|
| `out_baseline/manifest.json` | sweep 步骤 | 记录 6 个 case 的 params + applied |
| 6 个 `.inp` | sweep 步骤 | 后续可喂给 CFD++ 求解器(本 workflow 没跑求解) |
| `sweep-manifest` artifact | upload-artifact | 30 天可下载,审稿人可复现 |
| `sweep-inputs` artifact | upload-artifact | 同上 |

### 4.4 验证

| 检查 | 期望 |
|---|---|
| GitHub Actions 页面出现 "sweep-baseline" run | run 显示 ✓ |
| run 详情 → sweep 步骤日志 | 含 "generated 6 cases" |
| run 详情 → Artifacts | 2 个 zip:sweep-manifest + sweep-inputs |

**完成标志:** 改 `sweep_baseline.yaml` 后 `git push` 即可看到新 artifact。

---

## 5. 教程 4:用 inp-tool 做单文件修改

**目标:** 教程 1 教了"扫多个 case",但实际工作里也常需要"就改一个值",比如把 baseline 的 `cflbot` 从 0.005 改成 0.001(收敛出问题先降 CFL)。本教程用 `inp-tool set` 改一个值,用 `inp-tool diff` 验证只动了那一处。

> [04-扫描参数](04-sweeping.md) 详述了"扫多个 case"姿势,本教程聚焦"单文件原地改"。

### 5.1 准备

- 模板:`inp_tool/examples/mcfd_v2_modified.inp`
- 目标:`tsteps` 块的 `cflbot`(原值 0.005,先 `inp-tool get` 查)

### 5.2 操作

**步骤 1:先看 `cflbot` 现在是多少**

```bash
conda run -n cfdchanger inp-tool get \
    inp_tool/examples/mcfd_v2_modified.inp cflbot \
    -b tsteps
# 期望:cflbot = 0.005 (或类似的 baseline 值)
```

**步骤 2:用 `inp-tool set` 改成 0.001,另存为新文件**

```bash
# 关键:-o 指定输出文件,**原模板不动**
conda run -n cfdchanger inp-tool set \
    inp_tool/examples/mcfd_v2_modified.inp tsteps cflbot 0.001 \
    -o inp_tool/examples/mcfd_v2_cfl001.inp
# 期望输出:
#   已写入: inp_tool/examples/mcfd_v2_cfl001.inp
#   tsteps[0].cflbot = 0.001
```

> ⚠️ 漏掉 `-o` 会**原地覆盖**原文件!如果要覆盖原文件,确保有 git 备份或手上有副本。

**步骤 3:`inp-tool diff` 验证只动了那一处**

```bash
conda run -n cfdchanger inp-tool diff \
    inp_tool/examples/mcfd_v2_modified.inp \
    inp_tool/examples/mcfd_v2_cfl001.inp
# 期望输出:
# === a -> b ===
# 差异条数: 1
#   ~ block:tsteps[0] cflbot: (0.005,) -> (0.001,)
```

### 5.3 预期输出

```
已写入: inp_tool/examples/mcfd_v2_cfl001.inp
  tsteps[0].cflbot = 0.001
```

```
=== a -> b ===
差异条数: 1
  ~ block:tsteps[0] cflbot: (0.005,) -> (0.001,)
```

### 5.4 验证

| 检查 | 命令 | 期望 |
|---|---|---|
| 新文件 cflbot 改了 | `inp-tool get inp_tool/examples/mcfd_v2_cfl001.inp cflbot -b tsteps` | `0.001` |
| 原文件没动 | `inp-tool get inp_tool/examples/mcfd_v2_modified.inp cflbot -b tsteps` | `0.005` |
| diff 确实只 1 条 | `inp-tool diff ...` | "差异条数: 1" |
| 配合 sweep 用 | `inp-tool sweep inp_tool/examples/mcfd_v2_cfl001.inp --alpha 0,4,8 --mach 0.6,0.8 --out ./out_lowcfl` | 生成 6 个**低 CFL** 的 case(适合高 α 失速工况) |

**完成标志:** 你能精准控制"只改一个值、只影响一个 case",并用 `diff` 自证"只动了一处"。

---

## 6. 教程 5:把 sweep 结果送调度系统(SLURM 示意)

**目标:** 本地生成 6 个 `.inp` + `manifest.json` 后,自动生成 6 个 `sbatch` 脚本并提交到 SLURM 集群,跑完收结果。

### 6.1 准备

| 项 | 值 |
|---|---|
| 集群 | 任意 SLURM(HPC 中心 / 自建皆可) |
| 模板 | `inp_tool/examples/mcfd_v2_modified.inp`(本教程把 `mcrun` 替成 `sleep` 模拟) |
| 账号 | 替换 `<YOUR_ACCOUNT>` |

### 6.2 操作

**步骤 1:本地生成 sweep(沿用教程 1 的配置)**

```bash
conda run -n cfdchanger inp-tool sweep inp_tool/examples/mcfd_v2_modified.inp \
    --alpha 0,4,8 --mach 0.6,0.8 --t-inf 288.15 --p-inf 101325 \
    --naming "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp" \
    --out ./out_hpc --manifest ./out_hpc/manifest.json
```

**步骤 2:写 `submit.py`(读 manifest → 生成 sbatch → 提交)**

```python
#!/usr/bin/env python
"""读 manifest.json → 为每个 case 生成 sbatch → 提交到 SLURM"""
import json, subprocess
from pathlib import Path

TPL = """#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --account=<YOUR_ACCOUNT>
#SBATCH --partition=compute
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=16
#SBATCH --time=02:00:00
#SBATCH --output={case_id}.out
#SBATCH --error={case_id}.err
set -euo pipefail
module load cfd++
echo "[$(date)] start: {case_id}"
sleep 10   # 本教程用 sleep 模拟;生产替换为 mcrun/cfd++
echo "[$(date)] done: {case_id}"
"""

manifest = json.loads(Path("./out_hpc/manifest.json").read_text())
results = []
for case in manifest["cases"]:
    case_id   = case["case_id"]                          # 例:case_aoa04_ma0.60.inp
    case_dir  = Path(case["path"]).parent
    case_name = Path(case_id).stem
    sbatch    = case_dir / f"{case_name}.sbatch"
    sbatch.write_text(TPL.format(job_name=case_name[:20], case_id=case_id))
    sbatch.chmod(0o755)

    r = subprocess.run(["sbatch", str(sbatch)], capture_output=True, text=True, cwd=case_dir)
    if r.returncode != 0:
        print(f"  ✗ {case_id}: {r.stderr.strip()}"); continue
    job_id = r.stdout.strip().split()[-1]               # "Submitted batch job 12345"
    results.append({"case_id": case_id, "job_id": job_id})
    print(f"  ✓ {case_id} -> job {job_id}")

Path("./out_hpc/jobs.json").write_text(json.dumps(results, indent=2))
print(f"\n提交了 {len(results)} 个 job,见 ./out_hpc/jobs.json")
```

```bash
# 在集群上(已激活 cfdchanger 环境)
python submit.py
# 期望:6 行 ✓ case_aoaXX_maX.XX.inp -> job <id>
```

**步骤 3:监控与收数**

```bash
squeue -u $USER --name="case_aoa*"           # 看运行中
sacct  -u $USER --name="case_aoa*" --state=COMPLETE   # 完成后看历史
```

### 6.3 预期输出

`./out_hpc/` 目录(从教程 1 延续过来):

```
case_aoa00_ma0.60.inp       # inp-tool 生成的输入
case_aoa00_ma0.60.sbatch    # 本教程生成的提交脚本
case_aoa00_ma0.60.out       # 求解器 stdout(job 跑完后)
case_aoa00_ma0.60.err       # 求解器 stderr
... (× 6)
manifest.json                # sweep 产物
jobs.json                    # 本教程产物(case_id -> job_id 映射)
```

### 6.4 验证

| 检查 | 命令 | 期望 |
|---|---|---|
| 6 个 sbatch 文件 | `ls ./out_hpc/*.sbatch \| wc -l` | 6 |
| 6 个 job 提交成功 | `cat ./out_hpc/jobs.json \| jq 'length'` | 6 |
| 全部完成 | `sacct -u $USER --name="case_aoa*" --state=COMPLETE` | 6 行 COMPLETED |
| 失败时复现 | `grep aero_alpha ./out_hpc/case_aoa04_ma0.60.inp` | `aero_alpha 4.0` |

**完成标志:** 你能从 sweep 一键推到集群,6 个 case 跑完拿到结果,中间不需要手动改 sbatch。

---
## 7. 5 个教程速查表

| # | 入口 | 产物 | 用时 | 失败时看 |
|---|---|---|---|---|
| 1 | CLI `sweep` | 6 个 .inp + manifest | 5 分钟 | [03-快速开始](03-quickstart.md) §姿势 A |
| 2 | Web GUI | 同上 | 10 分钟(含讲解) | [10-FAQ §Web GUI](10-faq.md) |
| 3 | GitHub Actions | artifact zip | 15 分钟(配 CI) | [10-FAQ §CI](10-faq.md) |
| 4 | CLI `set` + `diff` | 1 个新 .inp | 2 分钟 | [03-快速开始](03-quickstart.md) §姿势 A 之后 |
| 5 | Python API + sbatch | 6 个 job_id | 30 分钟(集群需排队) | [10-FAQ §集群](10-faq.md) |

---

## 8. 关联章节

- 配置写法:[05-配置文件](05-config-files.md) · 字段覆盖:[07-字段覆盖](07-overrides.md) · CLI/API:[13-CLI 与 API 速查](13-cli-api-reference.md)
- 真实场景:[09-完整示例](09-examples.md) · 排错:[10-FAQ](10-faq.md) · 内部:[../technical/](../technical/)
