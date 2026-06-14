# 05 — Excel + Plot Output

> `[post]` extras 可选依赖模块:openpyxl 多 Sheet Excel + matplotlib 收敛曲线 png。

---

## 1. 依赖边界

```toml
# pyproject.toml
[project.optional-dependencies]
post = [
    "openpyxl>=3.1,<4",       # Py3.8 兼容上限 3.1.x
    "matplotlib>=3.5,<3.8",   # 3.8+ 弃 Py3.8
    "numpy>=1.22,<2.0",       # 2.0 弃 Py3.8
]
```

**核心硬约束:**
- `inp_tool.postprocess.__init__.py` **不导入** `report` / `plot` 模块
- `report.py` / `plot.py` 顶层 **不 import** openpyxl / matplotlib
- 函数体内 `try: import openpyxl ... except ImportError: raise ImportError("install [post]")`
- 用户须 `from inp_tool.postprocess.report import write_excel` 显式触发

**验证测试**(已纳入 CI):
```python
import sys
import inp_tool.postprocess as pp
assert 'openpyxl' not in sys.modules     # ✓
assert 'matplotlib' not in sys.modules   # ✓
```

---

## 2. Excel 输出(`report.py`)

### 2.1 API

```python
def write_excel(
    force_report: ForceReport,
    out_path: Union[str, Path],
    sheet_name: Optional[str] = None,    # 默认 "Forces"
) -> Path
```

### 2.2 输出格式

| 元素 | 设置 |
|---|---|
| Sheet 名 | 默认 "Forces",可通过 `sheet_name` 覆盖;> 31 字符自动截断(Excel 限制) |
| Header 行(第 1 行)| 28 列,Times New Roman 10pt 粗体居中 |
| Data 行(第 2 行起)| 一 case 一行,Times New Roman 10pt 右对齐 |
| 列宽 | `min(max_cell_str_len + 3, 25)` 自适应 |
| 字体颜色 | 默认黑色 |

### 2.3 28 列 header 定义

```python
HEADERS = [
    "Case", "Ma", "H(km)", "Alpha(deg)", "Beta(deg)",
    "Fx(N)", "Fy(N)", "Fz(N)",
    "Mx(N·m)", "My(N·m)", "Mz(N·m)",   # 已平移到 (Xref, Yref, Zref)
    "D(N)", "L(N)",
    "CD", "CY", "CL",
    "Cmx", "Cmy", "Cmz",
    "L/D", "Xcp(m)", "Xcg(m)",
    "Sref(m2)", "Lref(m)",
    "Q(Pa)", "Re(1/m)", "P(Pa)", "T(K)",
]
```

列顺序与 `CoefficientRow` dataclass 字段顺序一一对应。

### 2.4 与 reference 的差异

| 行为 | reference | 本实现 |
|---|---|---|
| Sheet 数量 | 多 sheet(每 op 一个,3 块合力/粘/无黏) | 单 sheet 一 case 一行 |
| 字段 | 多 sheet 共 ~84 列 | 单 sheet 28 列 |
| 依赖 | 顶层 import openpyxl + xlwt(双库) | lazy openpyxl |

**未来扩展(v0.16+):** 若需多 sheet 输出(按 op 拆分)可加新 API `write_excel_multi_sheet`。

---

## 3. matplotlib 收敛曲线(`plot.py`)

### 3.1 API

```python
PlotResultEntry = Tuple[
    str,                                  # case_name
    Optional[ConvergenceWindow],          # window(可 None,数据不足)
    Optional[Sequence[Info1Step]],        # steps(可 None,文件缺)
]

def save_convergence_plot(
    results: Sequence[PlotResultEntry],
    out_path: Union[str, Path],
) -> Path
```

### 3.2 输出格式

| 元素 | 设置 |
|---|---|
| 布局 | 2×3 subplot,6 个分量(Fx/Fy/Fz/Mx/My/Mz) |
| Figure size | 14×9 英寸 |
| DPI | 150 |
| 线宽 | 1.2pt |
| 颜色 | matplotlib 默认 cycle |
| 标题 | "CFD++ Aerodynamic Convergence"(suptitle 16pt 粗体) |
| 子图标题 | 12pt 粗体,X 轴 "nstep" |
| Grid | `alpha=0.3` |
| Legend | `loc="best"`,8pt;多 case (>1) 显示,单 case 不显示 |

### 3.3 后端

显式 `matplotlib.use("Agg", force=True)`,适合:
- CI / 无 GUI 服务器(没有 X11 / Wayland)
- Win7 / Windows Server(没有 DISPLAY env)
- Linux SSH 会话

**测试覆盖**:`monkeypatch.delenv("DISPLAY", raising=False)` 后仍能画(已纳入 CI)。

### 3.4 None 容错

当 `(case_name, None, None)`(无 mcfd.info1)或 `(case_name, window, None)`(只有 window 没原始 steps)时,该 case 在所有 subplot 中**跳过**,不抛错。

所有 case 都 None 时,**仍写空轴 png**(matplotlib 空 figure ≈ 50KB)。

---

## 4. 测试覆盖

| 文件 | 测试数 | 覆盖率 |
|---|---|---|
| `tests/test_post_excel.py` | 18 | 95% |
| `tests/test_post_plot.py` | 11 | 95% |

测试用 `pytest.importorskip("openpyxl")` / `importorskip("matplotlib")` 守卫,CI 通过 `pip install -e ".[post]"` 装这些依赖。
