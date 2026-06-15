# 01 — 快速开始

> 5 分钟跑通第一份 CFD++ 后处理:从一个 case 目录 → 提取气动力 → 输出 Excel 报告。

---

## 1. 前置准备

你需要一个 CFD++ 算例目录,里面至少有:
- `mcfd.inp`(包含 `aero_*` 字段的来流参数 — 必需)
- `mcfd.info1`(CFD++ 写出的力/矩历程文件 — 必需)
- `mcfd.bc`(边界编号→名称映射 — 推荐但非必需)

可选依赖(Excel + plot 需要):
```bash
pip install inp-tool[post]
```

---

## 2. CLI(最简单)

### 2.1 提取气动力 + 系数(零依赖)

```bash
inp-tool post extract /path/to/case_01 --op 1
```

`--op 1` 表示积分边界 1(`mcfd.bc` 中的 boundary id)。多边界合并用 `--op 1,2,3`。

输出(stdout):
```
Extracted 1 case(s):

[Case: case_01]
  Ma = 9.887, H = 30.00 km, α = 0.000°, β = 0.000°
  Fx = 5.4916e+06 N, Fy = 9.5117e+06 N, Fz = -1.9460e+07 N
  Mx = 3.1770e+08 N·m, My = 1.2242e+09 N·m, Mz = 6.8474e+08 N·m
  D  = 5.4916e+06 N, L  = -1.9460e+07 N, L/D = -3.5439
  CD = 0.12345, CY = 0.21368, CL = -0.43742
  Cmx = 7.139e-01, Cmy = 2.750e+00, Cmz = 1.539e+00
  Q  = 3.217e+03 Pa, Re = 1.846e+06 /m, Xcp = -22.30 m
```

### 2.2 设参考几何

默认 `Sref=1.0 m²`,`Lref=1.0 m`,矩心 `(0,0,0)`。常用覆盖:

```bash
inp-tool post extract /path/to/case_01 \
    --op 1 \
    --sref 0.42 --lref 1.2 \
    --xref 0.6 --yref 0 --zref 0
```

### 2.3 批量算例

```bash
inp-tool post extract \
    /path/to/case_01 \
    /path/to/case_02 \
    /path/to/case_03 \
    --op 1
```

或用 shell glob:
```bash
inp-tool post extract /path/to/cases/*/ --op 1
```

### 2.4 收敛性分析

```bash
inp-tool post convergence /path/to/case_01 --op 1 --out ./reports
```

输出 `./reports/convergence_report.txt`(中文 UTF-8 报告)。

参数:
- `--cv-threshold 0.001`(CV < 0.1% 算收敛,默认)
- `--window-fraction 0.1`(末 10% 步,默认)
- `--min-window 100`(至少 100 步,默认)

### 2.5 Excel 报告(需 [post])

```bash
inp-tool post report /path/to/case_01 --op 1 --out ForceReport.xlsx
```

生成 28 列 Excel,详见 [02-output-formats.md](02-output-formats.md)。

### 2.6 收敛曲线图(需 [post])

```bash
inp-tool post plot /path/to/case_01 --op 1 --out conv.png
```

生成 2×3 subplot png(Fx/Fy/Fz/Mx/My/Mz)。

### 2.7 一站式

```bash
inp-tool post all /path/to/case_01 \
    --op 1 --sref 0.42 --lref 1.2 \
    --out-dir ./output
```

输出 4 个产物到 `./output/`:
- stdout 显示 extract 结果
- `convergence_report.txt`
- `ForceReport.xlsx`(需 [post])
- `convergence_plot.png`(需 [post])

---

## 3. Python API

```python
from pathlib import Path
from inp_tool.postprocess import (
    ReferenceGeometry,
    summarize_forces,
    compute_convergence,
    read_info1,
)

# 设参考几何
geom = ReferenceGeometry(
    Sref=0.42, Lref=1.2,
    Xref=0.6, Yref=0.0, Zref=0.0,
)

# 提取系数
report = summarize_forces(
    case_dirs=[Path("case_01"), Path("case_02")],
    op_ibd=[1],
    ref_geom=geom,
)
for row in report.rows:
    print(f"{row.case}: CD={row.CD:.5f}, CL={row.CL:.5f}, L/D={row.L_over_D:.4f}")

# 收敛性分析
steps = read_info1("case_01/mcfd.info1", op_ibd=[1])
window = compute_convergence(steps)
if window is None:
    print("数据不足(< 100 步)")
elif window.all_converged:
    print("全部收敛")
else:
    for axis, conv in zip(("Fx", "Fy", "Fz", "Mx", "My", "Mz"), window.converged):
        print(f"  {axis}: {'OK' if conv else '未收敛'}")

# Excel 输出(需 [post])
from inp_tool.postprocess.report import write_excel
write_excel(report, "ForceReport.xlsx")

# 收敛图(需 [post])
from inp_tool.postprocess.plot import save_convergence_plot
save_convergence_plot([("case_01", window, steps)], "conv.png")
```

---

## 4. GUI

启动桌面 GUI:

```bash
inp-tool-gui
```

或:

```bash
python -m inp_tool_gui
```

切到 **"后处理(&P)"** 标签:

1. 点 **"选目录..."** 添加 case 目录(可多选)
2. 在 **"参考几何 & 积分 op"** 框里设 Sref/Lref/Xref/Yref/Zref/Xcg/op
3. 点 5 个 action 按钮之一:
   - **"提取力"** — 系数打印到日志区
   - **"收敛分析"** — QFileDialog 选输出目录 → 写 txt
   - **"Excel"** — QFileDialog 选 xlsx 路径 → 写 Excel
   - **"收敛图"** — QFileDialog 选 png 路径 → 写 png
   - **"全部"** — QFileDialog 选输出目录 → 4 产物一起出

日志区显示每步的进度。如果缺 `[post]` 依赖,会弹 QMessageBox 提示装。

---

## 5. 常见问题

### 5.1 `Error: no valid cases found`

case_dir 缺 `mcfd.inp` 或 `mcfd.info1`。检查目录里是否有这两个文件。

### 5.2 `Warning: ImportError: openpyxl is required for write_excel`

没装 `[post]` extras。运行:
```bash
pip install inp-tool[post]
```

### 5.3 Q/Re 全是 0

`mcfd.inp` 里 `aero_pres` 或 `aero_temp` 是 0 或负值。`Q = 0.5·P/(R·T)·V²` 无法计算。检查 `mcfd.inp` 的 `aero_*` 字段。

### 5.4 收敛报告说"数据不足"

mcfd.info1 中 `nt` 行少于默认 100 步。两种办法:
- 跑更长(让 CFD++ 多迭代)
- 用 `--min-window 50` 放宽阈值(注:统计窗口越小越不可靠)

### 5.5 多边界合并怎么用

`--op 1,2` 表示把边界 1 和边界 2 的力**累加**当成一个积分操作。典型用法:身体 + 翼面 总力。

如果想分别看每个边界,**多次跑** `inp-tool post extract --op 1` 和 `--op 2`。

### 5.6 Xcg 和 Xref 区别

- `Xref / Yref / Zref`:**力矩中心**,用于平移力矩 `M_new = M_old + r × F`。物理意义。
- `Xcg`:**重心**,只填进输出列(`Xcg(m)`),**不参与计算**。仅作记录。

---

## 6. 下一步

- [02-output-formats.md](02-output-formats.md) — Excel 28 列各代表什么 + 收敛报告字段说明
- [技术手册](../../technical/postprocess/) — 算法细节、与 reference/code 的差异、API 完整参考
