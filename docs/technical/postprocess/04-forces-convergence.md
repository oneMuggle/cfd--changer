# 04 — Forces + Convergence

> 气动力汇总 + 气动系数计算 + 力矩中心换算 + CV 收敛性判定。

---

## 1. 气动力汇总(`forces.py`)

### 1.1 6 个 dataclass

```python
@dataclass(frozen=True)
class RunParams:           # mcfd.inp 的 aero_* 字段提取 + 衍生
    Ma: float; H: float          # H 是 geopotential km
    alpha: float; beta: float    # 度(intyp=3 时从 uvw 反推)
    Q: float; Re: float          # 动压 Pa / 单位 Re /m
    P: float; T: float           # 来流 Pa / K
    intyp: int                   # 0 / 1 / 3(reference 约定)

@dataclass(frozen=True)
class ForceSample:         # 6 元 (Fx, Fy, Fz, Mx, My, Mz)
    Fx: float; Fy: float; Fz: float; Mx: float; My: float; Mz: float

@dataclass(frozen=True)
class ForceSection:        # total / inv / vis
    total: ForceSample; inv: ForceSample; vis: ForceSample

@dataclass(frozen=True)
class ReferenceGeometry:   # Sref/Lref + Xref/Yref/Zref(默认 0)
    Sref: float; Lref: float
    Xref: float = 0.0; Yref: float = 0.0; Zref: float = 0.0

@dataclass(frozen=True)
class CoefficientRow:      # 28 列对应 Excel 输出表头
    case: str
    Ma, H, alpha_deg, beta_deg: float
    Fx..Mz: float          # 已平移到 (Xref,Yref,Zref)
    D, L, CD, CY, CL, Cmx..Cmz, L_over_D, Xcp, Xcg: float
    Sref, Lref, Q, Re, P, T: float

@dataclass(frozen=True)
class ForceReport:
    rows: List[CoefficientRow]
```

### 1.2 `build_run_params(inp_path)`

从 mcfd.inp 的 `guiopts` block 读 11 个 aero_* 字段(实测 reference/full_case 路径)。规则:
- `intyp == 3` 时从 `(u, v, w)` 反推 alpha/beta(`uvw_to_alpha_beta`,**度**)
- 否则直接采纳 inp 中的 `aero_alpha` / `aero_beta`
- `Q = 0.5·ρ·V²`,`ρ = P/(R·T)`,`R = 287.0531 J/(kg·K)`(US 1976)
- `Re = ρ·V/μ`,`μ` 走 `sutherland_mu(T)`
- 缺字段用默认值(reference 行为)

### 1.3 力矩中心换算(`shift_moment_to_ref`)

CFD++ 输出取矩中心 `(0, 0, 0)`,要换到 `(Xref, Yref, Zref)`。用右手系叉乘 `M_new = M_old + r × F`:

```
Mx_new = Mx + Zref·Fy − Yref·Fz
My_new = My + Xref·Fz − Zref·Fx
Mz_new = Mz + Yref·Fx − Xref·Fy
```

力分量 (Fx, Fy, Fz) **不变**(力是向量,与中心无关)。

### 1.4 气动系数(`compute_coefficients`)

内部先调 `shift_moment_to_ref`,然后:

| 系数 | 公式 | 边界 |
|---|---|---|
| `CD` | `Fx / (Q·Sref)` | `Q·Sref < 1e-12` → 0 |
| `CY` | `Fy / (Q·Sref)` | 同上 |
| `CL` | `Fz / (Q·Sref)` | 同上 |
| `Cmx` | `Mx_shifted / (Q·Sref·Lref)` | `Q·Sref·Lref < 1e-12` → 0 |
| `Cmy/z` | 同上 | 同上 |
| `D` | `Fx·cos α + Fz·sin α` | — |
| `L` | `-Fx·sin α + Fz·cos α` | — |
| `L/D` | `L / D` | `|D| < 1e-10` → 0 |
| `Xcp` | `Xref - My_shifted / Fz` | `|Fz| < 1e-10` → 0 |

### 1.5 `summarize_forces` 高层 API

```python
def summarize_forces(
    case_dirs: Sequence[Union[str, Path]],
    op_ibd: Sequence[int],
    ref_geom: ReferenceGeometry,
    xcg: float = 0.0,
) -> ForceReport
```

对每个 case_dir:
1. 读 `mcfd.inp` → `build_run_params`
2. 读 `mcfd.info1` → `read_info1(op_ibd)`
3. 取末步 `steps[-1].total` 作为 ForceSample
4. `compute_coefficients` → CoefficientRow
5. 累加到 `ForceReport.rows`

缺 inp/info1 的目录**跳过**(不抛错)。

---

## 2. CV 收敛性分析(`convergence.py`)

### 2.1 算法

对一个 case 的 `list[Info1Step]`:

```python
n_window = max(min_window, int(n_total * fraction))
n_window = min(n_window, n_total)

window = steps[-n_window:]
for axis in range(6):
    vals = [s.total[axis] for s in window]
    mean = sum(vals) / len(vals)
    std  = sqrt(sum((v - mean)^2) / (n - 1))   # ddof=1 样本标准差
    cv   = abs(std / mean) if abs(mean) > 1e-30 else 0.0
    converged[axis] = (cv < threshold)

all_converged = all(converged)
```

默认常量:
- `DEFAULT_CV_THRESHOLD = 0.001`(CV < 0.1% 收敛)
- `DEFAULT_WINDOW_FRACTION = 0.1`(末 10% 步)
- `DEFAULT_MIN_WINDOW = 100`

### 2.2 边界

- `n_total < min_window` → 返回 `None`(数据不足)
- `mean ≈ 0` → 约定 `CV = 0`(物理上 0 力是稳定均值,不视为不收敛)
- `n < 2` → ddof=1 std 退化为 0(`_sample_std` 返回 0)

### 2.3 公共 API

```python
@dataclass(frozen=True)
class ConvergenceWindow:
    n_total: int
    n_window: int
    cv: tuple[float, ...]          # 6 元
    converged: tuple[bool, ...]    # 6 元
    all_converged: bool

def compute_convergence(steps, threshold=..., fraction=..., min_window=...
                       ) -> Optional[ConvergenceWindow]: ...

def format_convergence_report(
    results: Sequence[tuple[str, Optional[ConvergenceWindow]]],
    threshold=..., fraction=...,
) -> str: ...    # 中文 UTF-8 报告
```

### 2.4 报告格式(中文 UTF-8)

```
======================================================================
  CFD++ 气动力收敛性分析报告
======================================================================

收敛判定标准: 各分量变异系数 CV < 0.10%
收敛窗口: 末 10% 迭代步(至少 100 步)

======================================================================
  算例: case_01
======================================================================

  总迭代步: 1500
  收敛窗口: 末 150 步

  -------------------------------------------------------
  分量    CV(%)            收敛状态
  -------------------------------------------------------
  Fx      0.0123           收敛
  Fy      0.0089           收敛
  Fz      0.0456           收敛
  Mx      0.0876           收敛
  My      0.1234           未收敛
  Mz      0.0234           收敛
  -------------------------------------------------------
  综合判定: 未全部收敛
```

---

## 3. 已知风险

| 风险 | 缓解 |
|---|---|
| `intyp == 1` 模式(Ma-H)未走 `atmosphere_us_1976` | reference 现代路径 `build_runpara_from_inp` 直接用 `aero_pres / aero_temp`,本实现一致;若需走 Ma-H,用户自行调 `reynolds_number_at_altitude` |
| `aero_pres` / `aero_temp` 在 mcfd.inp 中可能是无意义占位 | `build_run_params` 用 `T > 0 and P > 0` 守卫,否则 Q/Re = 0 |
| reference fixture P=47 Pa, T=43 K | 非物理但内部一致;Q ≈ 3217 Pa, Re ≈ 1.85e6 |
