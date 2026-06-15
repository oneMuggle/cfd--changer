# 01 — Overview

> `inp_tool.postprocess` 子包的总体架构、数据流、依赖边界、3 种入口。

---

## 1. 子包结构

```
inp_tool/postprocess/
├── __init__.py            # 公共 API(38 个符号),只导出零依赖模块
├── atmosphere.py          # US 1976 大气模型 + Sutherland μ  (stdlib)
├── aero_math.py           # 风轴/体轴变换 + α/β↔uvw 互推    (stdlib,numpy 可选)
├── bc.py                  # mcfd.bc 解析                    (stdlib)
├── info1.py               # mcfd.info1 历程解析             (stdlib)
├── forces.py              # 力/矩汇总 + 气动系数            (stdlib)
├── convergence.py         # CV 收敛判定 + 文本报告          (stdlib)
├── report.py              # Excel 多 sheet 输出              ([post] openpyxl)
└── plot.py                # matplotlib 收敛曲线 png         ([post] matplotlib)
```

**核心硬约束:**
- 6 个核心模块 **零运行时依赖**,只用 Python stdlib
- `report` / `plot` 走 `[post]` extras(`openpyxl` / `matplotlib` / `numpy`)
- 顶层不 import 可选依赖,`__init__.py` 不暴露 `report` / `plot`
- 用户须 `from inp_tool.postprocess.report import write_excel` 显式触发,缺包给清晰 ImportError

---

## 2. 数据流

```
mcfd.inp                 mcfd.bc              mcfd.info1
   │                        │                      │
   ▼                        ▼                      ▼
build_run_params      parse_mcfd_bc         read_info1(op_ibd)
   │ RunParams(9)        │ BcNameMap         │ list[Info1Step]
   │                     │                   │ 取末步 [-1]
   ▼                     ▼                   ▼
              shift_moment_to_ref + compute_coefficients
                              │
                              ▼
                       CoefficientRow / ForceReport
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
   convergence (CV)    report.py (xlsx)   plot.py (png)
   compute_convergence write_excel         save_convergence_plot
   format_convergence  [post] openpyxl     [post] matplotlib
   _report
```

---

## 3. 3 种入口

| 入口 | 适用场景 | 实现 |
|---|---|---|
| **Python API** | 脚本 / 自动化 / Jupyter | `from inp_tool.postprocess import ...` |
| **CLI** | shell / SSH 远程 / 流水线 | `inp-tool post {extract,convergence,report,plot,all}` |
| **GUI tab** | 桌面交互式 | "后处理(&P)" 标签(PySide2) |

3 种入口共享同一套底层算法,**只是 UI 包装不同**。

### 3.1 Python API 示例

```python
from inp_tool.postprocess import (
    ReferenceGeometry, summarize_forces, compute_convergence, read_info1,
)

# 提取气动力
ref_geom = ReferenceGeometry(Sref=1.0, Lref=1.0, Xref=0.5)
report = summarize_forces(
    case_dirs=["case_01", "case_02"],
    op_ibd=[1, 2],
    ref_geom=ref_geom,
)
for row in report.rows:
    print(f"{row.case}: CD={row.CD:.5f}, CL={row.CL:.5f}")

# 收敛分析
steps = read_info1("case_01/mcfd.info1", op_ibd=[1])
window = compute_convergence(steps)
if window:
    print(f"all converged: {window.all_converged}")

# Excel + plot(需 [post])
from inp_tool.postprocess.report import write_excel
from inp_tool.postprocess.plot import save_convergence_plot
write_excel(report, "ForceReport.xlsx")
save_convergence_plot([("case_01", window, steps)], "conv.png")
```

### 3.2 CLI 示例

```bash
# 提取系数(零依赖)
inp-tool post extract case_01 case_02 --op 1,2 --sref 1.0 --lref 1.0

# 收敛分析(零依赖)
inp-tool post convergence case_01 --op 1 --out ./out

# Excel(需 [post])
inp-tool post report case_01 --op 1 --out ForceReport.xlsx

# 一站式(需 [post])
inp-tool post all case_01 case_02 --op 1 --out-dir ./out
```

### 3.3 GUI 示例

启动 `inp-tool-gui`,切到 "后处理(&P)" tab:
1. 点 "选目录..." 添加 case 目录(可多选)
2. 设 Sref / Lref / Xref / Yref / Zref / Xcg / op
3. 点 "提取力" / "收敛分析" / "Excel" / "收敛图" / "全部"
4. 日志区显示进度,QFileDialog 选输出路径

---

## 4. 依赖边界硬约束

| 模块 | 核心 import | `[post]` import | 失败策略 |
|---|---|---|---|
| `atmosphere` | `math`,`dataclasses` | — | — |
| `aero_math` | `math`,`typing` | `numpy`(函数内 soft fallback) | 退化到纯 math |
| `bc` | `pathlib`,`typing` | — | — |
| `info1` | `dataclasses`,`pathlib`,`typing` | — | — |
| `forces` | `math`,`dataclasses`,`pathlib` | — | — |
| `convergence` | `math`,`time`,`dataclasses` | — | — |
| `report` | (顶层不 import openpyxl) | `openpyxl` | `ImportError("install [post]")` |
| `plot` | (顶层不 import matplotlib) | `matplotlib` | 同上 |

**验证方式**(已纳入 CI 测试):
```python
import sys, inp_tool.postprocess
assert "openpyxl" not in sys.modules
assert "matplotlib" not in sys.modules
```

---

## 5. 子目录其余章节

- [02-atmosphere-aero-math.md](02-atmosphere-aero-math.md) — US 1976 公式 + A_bw 矩阵
- [03-info1-bc-parsing.md](03-info1-bc-parsing.md) — 文件格式 + 状态机
- [04-forces-convergence.md](04-forces-convergence.md) — 力矩换算 + 系数 + CV
- [05-excel-plot-output.md](05-excel-plot-output.md) — `[post]` extras 输出
- [06-cli-gui.md](06-cli-gui.md) — CLI 子命令 + GUI panel
