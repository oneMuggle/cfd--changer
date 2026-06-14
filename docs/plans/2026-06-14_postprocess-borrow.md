# 实施计划:把 `reference/code/` 的可借鉴功能集成进 `inp_tool/`

- **创建日期:** 2026-06-14
- **状态:** 待用户确认(未开始)
- **目标版本:** v0.15.0(分阶段合并,每阶段一个 PR)
- **关联文件:**
  - `reference/code/CFDPlus_V4.py`(1392 行)
  - `reference/code/CFDPlus_setup.py`(242 行)
  - `reference/code/CFDPlus_extract.py`(790 行)
  - `inp_tool/inp_tool/{parser,writer,model,diff,sweep,equations,pbs,cluster,batch,monitor,wizard,repl,api,cli}.py`
  - `inp_tool/inp_tool_gui/`(PyQt 桌面)

---

## 1. 背景与目标

### 1.1 背景

`reference/code/` 下三份脚本是 `inp_tool` 项目早期整理时的"参照实现"——形态是三份独立的 PyInstaller `--onefile` 脚本,带 GUI 弹窗、argparse 多子命令,总 2424 行。其中后处理相关的能力(`mcfd.info1` 解析、气动力汇总、收敛性分析、Excel 输出)目前 **`inp_tool` 完全没有等价物**;而 setup、sbatch 批量提交、txt2xls(xlwt) 等老路已被 `inp_tool` 的 `sweep` / `cluster` / `batch` / `monitor` 远超,跳过不接。

**已做对比分析,结论:** 集成 6 项核心算法(🟢 必接) + 4 项可选增强(🟡 `[post]` extras),跳过 4 项等价或过时功能(🔴)。

### 1.2 目标交付物

| 产物 | 形态 | 阶段 |
|---|---|---|
| `inp_tool.postprocess.atmosphere` 模块 | US 1976 大气模型(纯 stdlib) | Phase 1 |
| `inp_tool.postprocess.aero_math` 模块 | 风轴↔体轴变换 + α/β↔u/v/w 互推(纯 stdlib + 可选 numpy) | Phase 1 |
| `inp_tool.postprocess.bc` 模块 | `mcfd.bc` 边界编号→名称解析(纯 stdlib) | Phase 2 |
| `inp_tool.postprocess.info1` 模块 | `mcfd.info1` 历程解析,每时间步×6 分量×3 类(纯 stdlib) | Phase 2 |
| `inp_tool.postprocess.convergence` 模块 | CV 变异系数判定(纯 stdlib) | Phase 3 |
| `inp_tool.postprocess.forces` 模块 | 力/矩汇总 + 系数 + 力矩中心换算(纯 stdlib) | Phase 3 |
| `inp_tool.postprocess.report` 模块 | Excel 多 Sheet 输出(openpyxl,`[post]`) | Phase 4 |
| `inp_tool.postprocess.plot` 模块 | 收敛曲线 png(matplotlib,`[post]`) | Phase 4 |
| `inp-tool post` CLI 子命令 | `extract` / `convergence` / `report` / `plot` / `all` | Phase 5 |
| GUI panel(可选) | `PostprocessPanel`:选 case 目录 → 一键提力 | Phase 6 |
| 用户手册 / 技术手册 | 新增 `postprocess` 章节并归并至 `docs/technical/` + `docs/user-manual/` | Phase 7 |

### 1.3 不在范围(显式不做)

- 跳过 `CFDPlus_setup.py` 的 `copy_base_case` / `modify_mcfd_alpha_beta` — `sweep` 模块已远超
- 跳过 `CFDPlus_V4.py` 的 `run-all / end-all / check-all` — `cluster.py` + `batch.py` + `monitor.py` 已覆盖(双调度器 + SSH 客户端 + SweepMonitor)
- 跳过 `txt2xls (xlwt)` — 用 `openpyxl`(`[post]` extras)
- 跳过 `BatchCaseSetting_para.txt` 行式配置 — 走 `sweep` 的 YAML/JSON/CSV
- 不引入 PyYAML / numpy / openpyxl / matplotlib 到 `inp_tool` 核心 — 全部走 `[post]` extras
- 不修改 `parser / writer / model / diff` 对外 API(向后兼容)
- 不修改 `inp_tool_gui` 的现有 widget API(向后兼容);Phase 6 新增 panel
- Phase 6(GUI)允许推迟到 v0.16

---

## 2. 涉及文件清单

### 2.1 新建文件

| 路径 | 阶段 | 说明 |
|---|---|---|
| `inp_tool/inp_tool/postprocess/__init__.py` | P1 | 公共 API export |
| `inp_tool/inp_tool/postprocess/atmosphere.py` | P1 | US 1976 分层大气模型 + Sutherland μ |
| `inp_tool/inp_tool/postprocess/aero_math.py` | P1 | A_bw 矩阵、α/β↔uvw 互推 |
| `inp_tool/inp_tool/postprocess/bc.py` | P2 | `mcfd.bc` 解析 → `{id: name}` |
| `inp_tool/inp_tool/postprocess/info1.py` | P2 | `mcfd.info1` 历程解析 |
| `inp_tool/inp_tool/postprocess/convergence.py` | P3 | CV 判定 + 文本报告 |
| `inp_tool/inp_tool/postprocess/forces.py` | P3 | 力/矩汇总 + 系数 + 力矩中心 |
| `inp_tool/inp_tool/postprocess/report.py` | P4 | Excel 多 Sheet(可选依赖) |
| `inp_tool/inp_tool/postprocess/plot.py` | P4 | matplotlib 收敛曲线(可选依赖) |
| `inp_tool/inp_tool/cli_post.py` | P5 | `inp-tool post` 子命令实现 |
| `inp_tool/inp_tool_gui/widgets/postprocess_panel.py` | P6 | GUI 面板(可选) |
| `inp_tool/inp_tool_gui/controllers/postprocess_controller.py` | P6 | GUI 控制器(可选) |
| `inp_tool/tests/test_atmosphere.py` | P1 | US 1976 + 边界 + Sutherland |
| `inp_tool/tests/test_aero_math.py` | P1 | A_bw 矩阵对称性、uvw 互推 |
| `inp_tool/tests/test_bc_parser.py` | P2 | `mcfd.bc` 解析 + 注释跳过 |
| `inp_tool/tests/test_info1_parser.py` | P2 | `mcfd.info1` 历程 + vis/inv 分流 |
| `inp_tool/tests/test_convergence.py` | P3 | CV 判定 + 窗口选择 + 文本报告 |
| `inp_tool/tests/test_forces.py` | P3 | 力矩中心换算 + 系数 + D/L |
| `inp_tool/tests/test_post_excel.py` | P4 | Excel 多 Sheet(若 `openpyxl` 已装) |
| `inp_tool/tests/test_post_plot.py` | P4 | matplotlib png(若 `matplotlib` 已装) |
| `inp_tool/tests/test_post_cli.py` | P5 | CLI 子命令集成 |
| `inp_tool/tests/fixtures/reference/info1_mini.txt` | P2 | 截取 `reference/full_case/Case/mcfd.info1` 前 80 行做 fixture |
| `inp_tool/tests/fixtures/reference/bc_mini.bc` | P2 | 截取 `mcfd.bc` 前 11 行 |
| `docs/technical/postprocess/01-overview.md` | P7 | 章节:整体架构、API 一览 |
| `docs/technical/postprocess/02-atmosphere-aero-math.md` | P7 | 大气模型 + 坐标系变换算法 |
| `docs/technical/postprocess/03-info1-bc-parsing.md` | P7 | info1/bc 文件格式 + 解析细节 |
| `docs/technical/postprocess/04-forces-convergence.md` | P7 | 力矩换算公式 + CV 收敛判据 |
| `docs/technical/postprocess/05-excel-plot-output.md` | P7 | Excel/plot 输出格式 + 依赖边界 |
| `docs/technical/postprocess/06-cli-gui.md` | P7 | CLI 子命令 + GUI 面板 |
| `docs/technical/postprocess/README.md` | P7 | 章节总览(含章节目录) |
| `docs/user-manual/postprocess/01-quickstart.md` | P7 | 用户手册:如何提力 + 收敛分析 |
| `docs/user-manual/postprocess/02-output-formats.md` | P7 | Excel/plot 输出说明 |
| `docs/user-manual/postprocess/README.md` | P7 | 用户手册总览 |

### 2.2 修改文件

| 路径 | 阶段 | 改动 |
|---|---|---|
| `inp_tool/pyproject.toml` | P1 / P4 | (a) 不动 `dependencies`(保持零依赖);(b) 新增 `post` extras:`openpyxl>=3.1,<4`、`matplotlib>=3.5,<3.8`、`numpy>=1.22,<2.0`;(c) `optional-dependencies` 注释解释三平台兼容上限 |
| `inp_tool/inp_tool/__init__.py` | P1 起 | 暴露 `postprocess` 子包公共 API(只暴露 stdlib 路径;`[post]` 功能走 lazy import) |
| `inp_tool/inp_tool/cli.py` | P5 | 新增 `post` 子命令(`post extract` / `post convergence` / `post report` / `post plot` / `post all`),接入 `main()` 的 subparsers;新增 shell 补全片段 |
| `inp_tool/inp_tool/api.py` | P5(可选) | 新增 `POST /api/postprocess/extract` / `/convergence` 两个端点(若 Pydantic 字段存在,严格用 `typing.List[Dict]`,不内建下标) |
| `inp_tool/inp_tool_gui/main_window.py` | P6(可选) | 注册 `PostprocessPanel` |
| `inp_tool/inp_tool_gui/widgets/__init__.py` | P6(可选) | 导出新 widget |
| `inp_tool/inp_tool_gui/controllers/__init__.py` | P6(可选) | 导出新 controller |
| `docs/INDEX.md` | P7 | 指向 `docs/technical/postprocess/` 与 `docs/user-manual/postprocess/` |
| `docs/technical/README.md` | P7 | 章节目录加 `postprocess/` |
| `docs/user-manual/README.md` | P7 | 章节目录加 `postprocess/` |
| `CHANGELOG.md` | 各 PR | 每次合 PR 时按 Keep a Changelog 加条目 |

### 2.3 不改文件(向后兼容)

`inp_tool/inp_tool/{parser,writer,model,diff,sweep,equations,pbs,cluster,batch,monitor}.py`、`repl.py`、`wizard.py`、`i18n.py`、`repl_*.py` — 任何 `postprocess` 算法都通过**新文件 + 新子包**实现,不动现有对外 API。

---

## 3. 技术方案

### 3.1 子包架构:`inp_tool.postprocess/`

```
inp_tool/postprocess/
├── __init__.py            # 公共 API,只暴露 stdlib 模块
├── atmosphere.py          # US 1976 大气模型 + Sutherland μ  (零依赖)
├── aero_math.py           # A_bw 矩阵 + α/β↔uvw              (零依赖,numpy 可选加速)
├── bc.py                  # mcfd.bc 解析                      (零依赖)
├── info1.py               # mcfd.info1 解析                   (零依赖)
├── forces.py              # 力/矩汇总 + 系数                  (零依赖)
├── convergence.py         # CV 收敛判定 + 文本报告            (零依赖)
├── report.py              # Excel 多 Sheet 输出                ([post] openpyxl)
└── plot.py                # matplotlib 收敛曲线               ([post] matplotlib)
```

**依赖边界硬约束:**

| 模块 | 核心 import | `[post]` import | 失败策略 |
|---|---|---|---|
| `atmosphere` | `math` | — | — |
| `aero_math` | `math` | `numpy`(函数体内部 try/except,失败 fallback 到 `math`) | soft fallback |
| `bc` | `re` | — | — |
| `info1` | `re`,`dataclasses` | — | — |
| `forces` | `math` | — | — |
| `convergence` | `math`,`dataclasses`,`time`(文本报告用) | — | — |
| `report` | — | `openpyxl` | `ImportError` 在 `import` 时,提示 `pip install inp-tool[post]` |
| `plot` | — | `matplotlib` | 同上 |

`__init__.py` 顶 `from .atmosphere import ...` / `from .aero_math import ...` / `from .bc import ...` / `from .info1 import ...` / `from .forces import ...` / `from .convergence import ...`;**不**顶层 import `report` / `plot`(避免无 `openpyxl` 时 `import inp_tool` 失败)。`report.write_excel(...)` / `plot.save_convergence_plot(...)` 由调用方按需 import。

### 3.2 数据流

```
mcfd.inp                mcfd.bc              mcfd.info1
   │                       │                     │
   ▼                       ▼                     ▼
parse_mcfd_inp()      parse_mcfd_bc()      read_info1_file()
   │ aero_ma/altid/etc   │ {id: name}         │ step[], time[], 
   │                     │                     │ formom{total/inv/vis}[step,6]
   ▼                     ▼                     ▼
build_runpara() + Atmosphere_US_1976()    选取最后 N 步
   │  → [Ma, H, alpha, beta, Q, Re,        │ 平均 / 末步值
   │     intyp, P, T]                        ▼
   ▼                                  force_summary()
A_bw(α,β) ─→ 风轴力 ─→ CD/CY/CL/Cm         │
                                            ▼
                            ┌───────────────┴───────────────┐
                            ▼                               ▼
                  convergence.py                    report.py (Excel)
                  CV 变异系数判定                    openpyxl 多 Sheet
                            │                       每 op 一 sheet × 3 块
                            ▼                       (合力 / 粘性 / 无黏)
                  文本报告 convergence_report.txt
                            │
                            ▼
                  plot.py (matplotlib png)
```

### 3.3 公共 API 设计

```python
# inp_tool/postprocess/__init__.py 暴露:
from .atmosphere import (
    AtmosphereResult,            # dataclass: T, P, rho, mu, a
    atmosphere_us_1976,          # 入口: h_km -> AtmosphereResult
    sutherland_mu,               # T -> mu
    reynolds_number,             # h_km, vel, p, T -> Re /m
)
from .aero_math import (
    alpha_beta_to_uvw,           # vel, alpha_rad, beta_rad -> (u, v, w)
    uvw_to_alpha_beta,           # (u, v, w) -> (alpha_deg, beta_deg)
    body_to_wind,                # body_vec, alpha_rad, beta_rad -> wind_vec
    wind_to_body,                # 同上反向
)
from .bc import (
    BcNameMap,                   # dict[int, str]
    parse_mcfd_bc,               # 入口: path -> BcNameMap
    op_label,                    # 辅助: [1, 2] + BcNameMap -> "Body+HCW"
)
from .info1 import (
    Info1Step,                   # dataclass: step, time, forces{total/inv/vis}[6]
    read_info1,                  # 入口: path, op_ibd -> list[Info1Step]
    find_total_force_file,       # 找 minfo1_e1(无 _inv/_vis 后缀)
    is_viscous,                  # helper
)
from .forces import (
    RunParams,                   # dataclass: Ma, H, alpha, beta, Q, Re, P, T, intyp
    ForceSample,                 # dataclass: Fx..Mz(6)
    ForceSection,                # dataclass: total/inv/vis: ForceSample
    ReferenceGeometry,           # Sref, Lref, Xref, Yref, Zref
    build_run_params,            # 入口: mcfd.inp 路径 -> RunParams
    shift_moment_to_ref,         # 入口: ForceSample + (X,Y,Z) -> ForceSample
    compute_coefficients,        # 入口: ForceSection, RunParams, RefGeom -> CoefficientRow
    summarize_forces,            # 高层: case_dirs + ctrpara -> ForceReport
)
from .convergence import (
    ConvergenceWindow,           # dataclass: n_total, n_window, cv[6], converged[6]
    DEFAULT_CV_THRESHOLD,        # 0.001
    compute_convergence,         # 入口: list[Info1Step] -> ConvergenceWindow | None
    format_convergence_report,   # 文本报告生成
)

# [post] 入口(显式 import,不在 __init__ 顶层):
# from inp_tool.postprocess.report import write_excel
# from inp_tool.postprocess.plot import save_convergence_plot
```

### 3.4 `[post]` extras 划分

```toml
# pyproject.toml
[project.optional-dependencies]
post = [
    "openpyxl>=3.1,<4",   # Win7 + Py3.8 兼容上限是 3.1.x
    "matplotlib>=3.5,<3.8",
    "numpy>=1.22,<2.0",   # numpy 2.x 弃 Py3.8
]
```

测试侧用 `pytest.importorskip("openpyxl")` / `importorskip("matplotlib")` 守卫;`numpy` 在 `aero_math` 中做 soft fallback,测试两种路径都覆盖。

### 3.5 CLI 子命令设计

```
inp-tool post <subcmd> [options]

Subcommands:
  extract       解析 mcfd.info1 + mcfd.bc + mcfd.inp,输出气动力系数(单算例 / 批量)
  convergence   跑 CV 收敛分析,输出 convergence_report.txt
  report        extract + 写 Excel(多 Sheet,需 [post])
  plot          extract + 画收敛曲线(需 [post])
  all           extract + convergence + report + plot 一条龙
```

**`inp-tool post extract` 用法:**

```
inp-tool post extract <case_dir>...
  --op, --operations "1,2,3"          # 积分边界 op 列表(逗号分隔)
                                       # 特殊 "0" 表示全边界(对应 nbd=0)
  --sref <m2> --lref <m>              # 参考面积 / 参考长度
  --xref <m> --yref <m> --zref <m>    # 参考矩心(默认 0,0,0)
  --output-format {json,txt,csv}      # 输出格式(默认 txt,模仿 reference)
  --out <file>                        # 输出路径(默认 stdout / work_dir)
  --quiet                             # 静默(脚本友好)
```

**`inp-tool post convergence` 用法:**

```
inp-tool post convergence <case_dir>...
  --cv-threshold 0.001                # CV 阈值(默认 0.001 = 0.1%)
  --window-fraction 0.1               # 窗口占总步比例
  --min-window 100                    # 最小窗口步数
  --out <dir>                         # 报告输出目录
  --plot                              # 顺手画 png(需 [post])
```

**`inp-tool post report` / `post plot` 用法:**

```
inp-tool post report <case_dir>...
  --op "1,2" --sref 1.0 --lref 1.0 ...
  --out <file.xlsx>                   # 默认 ./ForceReport.xlsx

inp-tool post plot <case_dir>...
  --out <file.png>                    # 默认 ./convergence_plot.png
```

实现:`inp_tool/inp_tool/cli_post.py` 提供 `cmd_post_extract / cmd_post_convergence / cmd_post_report / cmd_post_plot / cmd_post_all`,在 `cli.py::main()` 注册 `post` subparser + sub-subparsers(`dest='post_cmd'`)。

### 3.6 GUI 集成(Phase 6,可选)

新增 `PostprocessPanel`(`QWidget`),构造时接受 case_dir 列表与参考几何默认值;布局:

```
[选目录] [▶ 提取气动力]   [后处理: ☐ Excel ☐ 收敛图 ☐ 报告]
─────────────────────────────────────────────────────
Sref: [   ] m²   Lref: [   ] m
Xref: [   ] m    Yref: [   ] m    Zref: [   ] m
积分 op: [   ]   (空 = 全边界)
─────────────────────────────────────────────────────
[日志区:QPlainTextEdit,只读]
```

信号槽:
- 提取按钮 → `PostprocessController.extract(...)` → 后台 `QThread`(避免 GUI 卡死)
- 完成后 → `populate_table(ForceReport)`(用 `QTableView` + `QStandardItemModel`)+ 在日志区输出文本

**不在 Phase 1-5 范围**;Phase 6 单独一个 PR,允许延后到 v0.16。

### 3.7 算法要点

**US 1976 大气模型(`atmosphere.py`):**

| 高度 h(km) | 温度 t(K) | 压强比 pp |
|---|---|---|
| 0–11 | 288.15 − 6.5·h | (288.15/t)^(−k·6.5) |
| 11–20 | 216.65 | 0.22336·exp(−k·(h−11)/216.65) |
| 20–32 | 216.65 + (h−20) | 0.054032·(216.65/t)^k |
| 32–47 | 228.65 + 2.8·(h−32) | 0.0085666·(228.65/t)^(k·2.8) |
| 47–51 | 270.65 | 0.0010945·exp(−k·(h−47)/270.65) |
| 51–71 | 270.65 − 2.8·(h−51) | 0.00066063·(270.65/t)^(−k·2.8) |
| 71–84.852 | 214.65 − 2.0·(h−71) | 3.9046e-05·(214.65/t)^(−k·2.0) |

其中 `k = 34.163195`,地面对应 `T₀=288.15 K`,`P₀=101325 Pa`,`ρ₀=1.225 kg/m³`,`a₀=340.294 m/s`。几何高度 `h = 0.0003048·z / (1 + 0.0003048·z/6356.766)`,`z = altitude_km · 1000`(m)。

**力矩中心换算(`forces.py`):** CFD++ 输出取矩中心在 `(0,0,0)`,换到 `(Xref,Yref,Zref)`:
```
M_new = M_old + r × F
      = M_old + (Zref·Fy − Yref·Fz, Xref·Fz − Zref·Fx, Yref·Fx − Xref·Fy)
```

**CV 收敛判定(`convergence.py`):** 末 `n_window = max(100, n_total // 10)` 步,对 6 个分量(列 1–6)分别 `cv = std(ddof=1) / |mean|`,`cv < 0.001` (0.1%) 视为该分量收敛。

**`mcfd.info1` 解析(`info1.py`):**
- 行首 `nt` 开头:第 2 列为 step、第 6 列为 time;触发新 step 累积
- 行首 `nbc` 开头且第 7 列 = `dimensional`:第 3 列(剥末尾逗号)→ 边界 id 列表;若 `op_ibd ⊆ id_list` 则**累加**该 op 的力
- 跟 `nbc` 行后续 8 行:energy flux / mass flux / x force / y force / z force / x moment / y moment / z moment,每行第 2/3/4 列 = total / inviscid / viscous
- 之后 2 行 `areas` / `areamoments` 跳过

**`mcfd.bc` 解析(`bc.py`):** 注释行 `# Body` → 接下来第一个数字行 → `{int(parts[0]): "Body"}`,然后清空 `current_name` 等下一个注释。

---

## 4. 实施步骤

> 每个阶段对应一个独立 feature branch + PR。每阶段合并后立刻归档到 `docs/technical/postprocess/` 与 `docs/user-manual/postprocess/` 对应章节,并**更新本 plan** 的 checkbox。
> 分支命名规范见 `~/.claude/rules/common/feature-branch-workflow.md`。

### Phase 1:大气模型 + 风轴体轴变换(纯 stdlib,TDD 优先)

**分支:** `feat/postprocess-atmosphere-aeromath`
**目标:** `inp_tool.postprocess.atmosphere` + `aero_math` 模块就位,测试覆盖 ≥ 80%,核心零依赖。

- [ ] 建分支:`git switch -c feat/postprocess-atmosphere-aeromath`
- [ ] 新建 `inp_tool/inp_tool/postprocess/__init__.py`(本阶段不暴露 API,等 Phase 2 一起)
- [ ] 新建 `inp_tool/inp_tool/postprocess/atmosphere.py`
  - [ ] `dataclass AtmosphereResult(T, P, rho, mu, a)` — 纯 stdlib
  - [ ] `atmosphere_us_1976(h_km: float) -> AtmosphereResult` — 7 段函数 + 几何高度修正
  - [ ] `sutherland_mu(T: float) -> float` — `1.458e-6 · T^1.5 / (T + 110.4)`
  - [ ] `reynolds_number(h_km, vel, p, T) -> float` — `density·vel/mu`
  - [ ] h > 84.852 时抛 `ValueError`(不 `sys.exit`)
- [ ] 新建 `inp_tool/inp_tool/postprocess/aero_math.py`
  - [ ] `alpha_beta_to_uvw(vel, alpha_rad, beta_rad) -> (u, v, w)`
  - [ ] `uvw_to_alpha_beta(u, v, w) -> (alpha_deg, beta_deg)` — 含 `vel < 1e-12` 与 `|cos β| < 1e-12` 边界
  - [ ] `body_to_wind(body_vec, alpha_rad, beta_rad) -> wind_vec` — A_bw @ body
  - [ ] `wind_to_body(wind_vec, alpha_rad, beta_rad) -> body_vec` — A_bw.T @ wind
  - [ ] 可选 `numpy` 加速:函数体 `try: import numpy` → 用 `np.dot`;失败 fallback 到纯 `math`
- [ ] 新建 `inp_tool/tests/test_atmosphere.py`(TDD:先写 RED)
  - [ ] NASA 标准表格对照:0 km → T=288.15, P=101325, ρ=1.225, a=340.294
  - [ ] 11/20/32/47/51/71/84.852 km 边界各一个 case
  - [ ] h > 84.852 抛 `ValueError`
  - [ ] `sutherland_mu(288.15) ≈ 1.7894e-5`
  - [ ] 几何高度 h≈0 时 round-trip:`h_geom(0)=0`
- [ ] 新建 `inp_tool/tests/test_aero_math.py`
  - [ ] `body_to_wind([V,0,0], α=0, β=0) == [V,0,0]`
  - [ ] `body_to_wind` 与 `wind_to_body` 互为逆(随机 α/β 抽样,误差 < 1e-9)
  - [ ] `alpha_beta_to_uvw(1, 0, 0) == (1, 0, 0)`
  - [ ] `alpha_beta_to_uvw` 与 `uvw_to_alpha_beta` 互逆
  - [ ] 边界:`vel=0` 时 `uvw_to_alpha_beta → (0, 0)`
  - [ ] soft numpy fallback:`monkeypatch` 屏蔽 numpy,断言仍走 `math` 路径
- [ ] 更新 `inp_tool/inp_tool/__init__.py`:`from .postprocess import atmosphere, aero_math`
- [ ] 跑 `conda run -n cfdchanger pytest tests/test_atmosphere.py tests/test_aero_math.py -v --cov=inp_tool.postprocess.atmosphere --cov=inp_tool.postprocess.aero_math --cov-report=term-missing`,覆盖率 ≥ 80%
- [ ] 跑 `conda run -n cfdchanger ruff check inp_tool/postprocess/`
- [ ] commit + push + 开 PR,等 CI 绿
- [ ] **本阶段不更新文档**(章节在 Phase 7 一起写)

### Phase 2:mcfd.info1 / mcfd.bc 解析(纯 stdlib)

**分支:** `feat/postprocess-info1-bc`

- [ ] 建分支:`git switch -c feat/postprocess-info1-bc`
- [ ] 新建 `inp_tool/inp_tool/postprocess/bc.py`
  - [ ] `parse_mcfd_bc(path) -> dict[int, str]`
  - [ ] `op_label(op_ibd, bc_names) -> str`
  - [ ] 跳过 `#BC` 前缀注释
- [ ] 新建 `inp_tool/inp_tool/postprocess/info1.py`
  - [ ] `dataclass Info1Step(step, time, total, inv, vis)`
  - [ ] `read_info1(path, op_ibd) -> list[Info1Step]` — 状态机解析
  - [ ] `find_total_force_file(case_dir) -> Optional[Path]`
  - [ ] `is_viscous(steps) -> bool`
  - [ ] 防御性:文件不存在 → 抛 `FileNotFoundError`;`nt` 行格式损坏 → 跳过该 step
- [ ] 准备 fixture:
  - [ ] `inp_tool/tests/fixtures/reference/info1_mini.txt`(80 行)
  - [ ] `inp_tool/tests/fixtures/reference/bc_mini.bc`(11 行)
- [ ] 新建 `inp_tool/tests/test_bc_parser.py`
  - [ ] `parse_mcfd_bc(fixture) == {1: "Body", 2: "HCW", ...}`
  - [ ] `op_label([1, 2], names) == "Body+HCW"`
  - [ ] `op_label([99], names) == "99"`
  - [ ] 文件不存在 → `FileNotFoundError`
- [ ] 新建 `inp_tool/tests/test_info1_parser.py`
  - [ ] `read_info1(fixture, op_ibd=[1])` → 数值与 fixture 一致(容差 1e-6)
  - [ ] `is_viscous` 全零 False;任一非零 True
  - [ ] `find_total_force_file` 排除 `_inviscid` / `_viscous` 后缀
  - [ ] 损坏文件 → 返回空 list
  - [ ] `nbc` 段 `nondimensional` 行被跳过
- [ ] 更新 `inp_tool/inp_tool/__init__.py`:补 `bc`、`info1` 导出
- [ ] 跑测试,覆盖率 ≥ 80%
- [ ] commit + push + 开 PR,等 CI 绿

### Phase 3:力/矩汇总 + 收敛性分析(纯 stdlib)

**分支:** `feat/postprocess-forces-convergence`

- [ ] 建分支:`git switch -c feat/postprocess-forces-convergence`
- [ ] 新建 `inp_tool/inp_tool/postprocess/forces.py`
  - [ ] 6 个 dataclass(`RunParams`/`ForceSample`/`ForceSection`/`ReferenceGeometry`/`CoefficientRow`/`ForceReport`)
  - [ ] `build_run_params(inp_path) -> RunParams` — 用 `inp_tool.parser.parse_file` 读 `aero_*`
  - [ ] `shift_moment_to_ref(force, ref_geom) -> ForceSample`
  - [ ] `compute_coefficients(force_section, run_params, ref_geom) -> CoefficientRow`
  - [ ] `summarize_forces(case_dirs, op_ibd, ref_geom) -> ForceReport`
- [ ] 新建 `inp_tool/inp_tool/postprocess/convergence.py`
  - [ ] `dataclass ConvergenceWindow(...)`
  - [ ] `DEFAULT_CV_THRESHOLD = 0.001`,`DEFAULT_WINDOW_FRACTION = 0.1`,`DEFAULT_MIN_WINDOW = 100`
  - [ ] `compute_convergence(steps, ...) -> Optional[ConvergenceWindow]`
  - [ ] `format_convergence_report(results) -> str` — 中文 UTF-8
- [ ] 新建 `inp_tool/tests/test_forces.py`
  - [ ] `shift_moment_to_ref(零力, ref=(0,0,0))` 不变
  - [ ] **用 `reference/full_case/Case/mcfd.info1` + mcfd.inp 跑,与 reference `Force_all_cases.xlsx` 对照关键 cell(容差 1%)**
  - [ ] `Q < 1e-12` 时返回零系数
  - [ ] `|D|/|Fz| < 1e-10` 时 LD/Xcp 返回 0
- [ ] 新建 `inp_tool/tests/test_convergence.py`
  - [ ] 100 步常量 → `cv=0` 全部收敛
  - [ ] 100 步线性递增 → `cv > 0.001`
  - [ ] 50 步 → 返回 `None`
  - [ ] 中文 UTF-8 sanity 检查
- [ ] 更新 `inp_tool/inp_tool/__init__.py`:补 `forces`、`convergence` 导出
- [ ] 跑测试,覆盖率 ≥ 80%
- [ ] commit + push + 开 PR,等 CI 绿

### Phase 4:Excel/plot 输出(`[post]` extras)

**分支:** `feat/postprocess-excel-plot`

- [ ] 建分支:`git switch -c feat/postprocess-excel-plot`
- [ ] 修改 `inp_tool/pyproject.toml`:`[project.optional-dependencies]` 新增 `post`
- [ ] 新建 `inp_tool/inp_tool/postprocess/report.py`
  - [ ] **顶层不 import openpyxl**;函数内 `import openpyxl`,未装则 `raise ImportError`
  - [ ] `write_excel(out_path, ops, op_labels, headers, case_data_per_op, *, sheet_names=None) -> Path`
- [ ] 新建 `inp_tool/inp_tool/postprocess/plot.py`
  - [ ] **顶层不 import matplotlib**
  - [ ] `save_convergence_plot(out_path, results) -> Path`
  - [ ] 2×3 subplot,DPI 150
- [ ] 新建 `inp_tool/tests/test_post_excel.py`
  - [ ] `pytest.importorskip("openpyxl")` 守卫
  - [ ] 多 op 校验 sheet
- [ ] 新建 `inp_tool/tests/test_post_plot.py`
  - [ ] `pytest.importorskip("matplotlib")` 守卫
  - [ ] `matplotlib.use("Agg")`
- [ ] 不在 `inp_tool/__init__.py` 顶层暴露 `report` / `plot`
- [ ] 跑 `pip install -e ".[post,dev]"` → 全测试 → 卸载 `[post]` → 核心测试仍全绿
- [ ] commit + push + 开 PR,等 CI 绿

### Phase 5:CLI 子命令 `inp-tool post`

**分支:** `feat/postprocess-cli`

- [ ] 建分支:`git switch -c feat/postprocess-cli`
- [ ] 新建 `inp_tool/inp_tool/cli_post.py`
  - [ ] `cmd_post_extract / convergence / report / plot / all`
  - [ ] `_register_post_subparser(sub)`
- [ ] 修改 `inp_tool/inp_tool/cli.py::main()`:
  - [ ] `spost = sub.add_parser('post', ...)`,5 个 sub-subparser
  - [ ] shell 补全补 `post` 子树
- [ ] 新建 `inp_tool/tests/test_post_cli.py`
  - [ ] `inp-tool post extract <case>` 返回 0
  - [ ] `inp-tool post convergence <case>` 生成 `convergence_report.txt`
  - [ ] 缺参 → 退出码 2
  - [ ] 无 openpyxl → stderr 提示安装
- [ ] 跑测试,覆盖率 ≥ 80%
- [ ] commit + push + 开 PR,等 CI 绿

### Phase 6:GUI 集成(可选,允许推迟到 v0.16)

**分支:** `feat/postprocess-gui-panel`

- [ ] 建分支:`git switch -c feat/postprocess-gui-panel`
- [ ] 新建 `inp_tool/inp_tool_gui/widgets/postprocess_panel.py`
- [ ] 新建 `inp_tool/inp_tool_gui/controllers/postprocess_controller.py`
- [ ] 修改 `main_window.py` / `widgets/__init__.py` / `controllers/__init__.py`
- [ ] 新建 `tests/test_gui_postprocess_panel.py` + `test_gui_postprocess_controller.py`
  - [ ] smoke 测试 + 信号槽连通性
  - [ ] `QT_QPA_PLATFORM=offscreen`
- [ ] 跑测试,覆盖率 ≥ 80%
- [ ] commit + push + 开 PR,等 CI 绿

### Phase 7:文档归档

**分支:** `docs/postprocess-handbook`

- [ ] 建分支:`git switch -c docs/postprocess-handbook`
- [ ] 新建 `docs/technical/postprocess/README.md` + `01-overview.md` + `02-atmosphere-aero-math.md` + `03-info1-bc-parsing.md` + `04-forces-convergence.md` + `05-excel-plot-output.md` + `06-cli-gui.md`
- [ ] 新建 `docs/user-manual/postprocess/README.md` + `01-quickstart.md` + `02-output-formats.md`
- [ ] 修改 `docs/technical/README.md`、`docs/user-manual/README.md`、`docs/INDEX.md` 章节目录
- [ ] `git rm docs/plans/2026-06-14_postprocess-borrow.md`(plan 完成即删)
- [ ] commit + push + 开 PR,等 CI 绿 → merge → 删本地 + 远程分支
- [ ] 更新 `CHANGELOG.md`:`[v0.15.0]` 段加 postprocess Added 条目

---

## 5. 测试策略

### 5.1 覆盖率目标

- 每阶段单测覆盖率 ≥ 80%
- 整体 `inp_tool.postprocess` ≥ 85%
- 端到端集成测试:`test_post_cli.py` 跑 `reference/full_case/Case`

### 5.2 基准数据

| 测试 | 数据源 | 预期来源 |
|---|---|---|
| US 1976 大气模型 | NASA 1976 标准表(0/11/20/32/47/51/71/84.852 km) | NASA 公开表 |
| mcfd.info1 解析 | `reference/full_case/Case/mcfd.info1` 前 80 行 fixture | 该 fixture |
| mcfd.bc 解析 | `reference/full_case/Case/mcfd.bc` fixture | 该 fixture |
| 力矩换算 | 人工推算 | 数学公式 |
| 力系数 | reference V4.py `extract-all` 输出 | `Force_all_cases.xlsx`(容差 1%) |
| 收敛 CV | 合成数据 + reference | 合成 + reference |

### 5.3 TDD 顺序

1. 写测试 → RED
2. 最小实现 → GREEN
3. 重构 → IMPROVE
4. `pytest --cov` ≥ 80%
5. ruff/mypy 静态检查
6. commit → push → PR

### 5.4 平台兼容性

- Win7(若可达)/ Win10 / Linux
- 无 `numpy` 时 core 测试仍全绿(monkeypatch 覆盖)
- Python 3.8 兼容性:`from __future__ import annotations` + `typing.List[Dict]` 老式构造

### 5.5 性能 sanity

| 用例 | 期望 |
|---|---|
| 1000 步 × 6 分量 CV 计算(纯 stdlib) | < 0.1s |
| 100 case × 5 op Excel 写出 | < 5s |
| 100 case × 6 分量 matplotlib png | < 10s |

---

## 6. 风险评估

| # | 风险 | 概率 | 影响 | 缓解动作 |
|---|---|---|---|---|
| R1 | `openpyxl / matplotlib / numpy` 是新依赖,污染零依赖核心 | 高 | 中 | 走 `[post]` extras;`report/plot.py` 顶层不 import;`importorskip` 守卫;`dependencies=[]` 不动 |
| R2 | Win7 + Py3.8 上版本钉死 | 中 | 中 | `pyproject.toml` 用 `>=X,<Y` 卡上限;CI 在 Win7 runner 上跑;Phase 4 跑 `pip install -e ".[post,dev]"` 验证 |
| R3 | 力矩中心换算公式与 reference 偏差 | 中 | 高 | `reference/full_case/Case/mcfd.info1` + `Force_all_cases.xlsx` 做对照 TDD,容差 1% |
| R4 | US 1976 几何高度修正 | 低 | 低 | 测试覆盖 h=0 时 h_geom≈0;文档解释"几何 vs 大地高度" |
| R5 | `mcfd.info1` 不同 CFD++ 版本字段数变化 | 中 | 中 | `len(parts) > 5` 守卫;容错跳损坏 step;补"空文件 + 文件不存在"测试 |
| R6 | `mcfd.bc` 注释行格式多样 | 中 | 中 | 跳过 `#BC`;空白注释行忽略;`op_label` 未知名回退到数字 |
| R7 | matplotlib 在 Win7 上 DLL 加载失败 | 中 | 中 | 显式 `matplotlib.use("Agg")`;GUI 集成推迟到 Phase 6 |
| R8 | GUI QThread 与子包 import 顺序冲突 | 低 | 中 | Phase 6 单独 PR;controller 走 lib 路径不走 cli_post |
| R9 | `inp_tool_gui` 主窗口布局冲突 | 低 | 低 | Phase 6 前做布局 review;tab 或 dock widget 二选一 |
| R10 | 7 阶段 PR 节奏长,reference 输出格式变化 | 低 | 中 | Phase 3 完成即锁 reference 数据为 fixture |
| R11 | `cli.py` 已 1669 行,继续膨胀 | 中 | 低 | Phase 5 抽到 `cli_post.py`;`cli.py::main()` 只调注册函数 |
| R12 | 文档归档阶段误留 plan 文件 | 低 | 低 | Phase 7 末尾显式 `git rm docs/plans/2026-06-14_postprocess-borrow.md` |

---

## 7. 成功标准

- [ ] 7 个阶段全部合并,`inp_tool.postprocess` 子包就位
- [ ] 每阶段覆盖率 ≥ 80%,整体 ≥ 85%
- [ ] `inp-tool post --help` / `inp-tool post extract <reference>` / `inp-tool post convergence <reference>` 跑通
- [ ] `reference/full_case/Case` 用本工具跑出的 `ForceReport.xlsx` 与 reference `Force_all_cases.xlsx` 关键 cell 偏差 < 1%
- [ ] CI 7 个 PR 全部绿(Win10 + Linux;Win7 若可达)
- [ ] `inp_tool` 核心 `dependencies=[]` 仍为空,`pip install inp-tool` 不带 `[post]` 时无 `import openpyxl` 错误
- [ ] 文档归档完成:`docs/technical/postprocess/` + `docs/user-manual/postprocess/` 章节目录就位;`docs/plans/2026-06-14_postprocess-borrow.md` 已删
- [ ] `CHANGELOG.md` v0.15.0 段加 postprocess 条目

---

## 8. 时间估算

| 阶段 | 代码量 | 测试代码量 | 估时 |
|---|---|---|---|
| Phase 1 | ~250 行 | ~200 行 | 0.5d |
| Phase 2 | ~350 行 | ~250 行 | 0.5d |
| Phase 3 | ~400 行 | ~300 行 | 1d |
| Phase 4 | ~300 行 | ~150 行 | 0.5d |
| Phase 5 | ~250 行 | ~150 行 | 0.5d |
| Phase 6(可选) | ~300 行 | ~150 行 | 0.5d |
| Phase 7 | ~600 行 markdown | — | 0.5d |
| **合计** | ~2450 行 | ~1200 行 | **~4d**(Phase 6 选做则 ~3.5d) |

---

## 9. 参考

- `reference/code/CFDPlus_V4.py` 第 65-83 行(风轴↔体轴)、131-176 行(US 1976)、437-452 行(bc 解析)、483-544 行(info1 解析)、838-976 行(力汇总)
- `reference/code/CFDPlus_extract.py` 第 600-632 行(CV 收敛)
- `reference/code/CFDPlus_setup.py` 全部跳过
- `inp_tool/inp_tool/cli.py` 第 1259-1430 行(subparsers 注册模式)
- `inp_tool/inp_tool/monitor.py`(零依赖子包范式参考)
- NASA 1976 US Standard Atmosphere
- `~/.claude/rules/common/feature-branch-workflow.md`(分支策略)
- `~/.claude/rules/common/testing.md`(覆盖率要求)
- `~/.claude/rules/common/cicd-workflow.md`(CI/CD 流程)
- `~/.claude/rules/common/code-review.md`(code review 触发)
