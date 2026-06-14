# 02 — Atmosphere + Aero Math

> US 1976 标准大气模型 + 风轴/体轴坐标系变换的公式与实现细节。

---

## 1. US 1976 大气模型(`atmosphere.py`)

### 1.1 公式与常量

US Standard Atmosphere 1976(NASA-TM-X-74335)分 7 个温度层(geopotential):

| h(km)         | T 公式                  | 段顶 T(K)  | lapse 类型 |
|---------------|------------------------|------------|-----------|
| 0    – 11.0   | T = 288.15 − 6.5·h      | 216.65     | 线性 -6.5 K/km |
| 11   – 20.0   | T = 216.65              | 216.65     | 等温 |
| 20   – 32.0   | T = 216.65 + 1·(h-20)   | 228.65     | 线性 +1 K/km |
| 32   – 47.0   | T = 228.65 + 2.8·(h-32) | 270.65     | 线性 +2.8 K/km |
| 47   – 51.0   | T = 270.65              | 270.65     | 等温 |
| 51   – 71.0   | T = 270.65 − 2.8·(h-51) | 214.65     | 线性 -2.8 K/km |
| 71   – 84.852 | T = 214.65 − 2.0·(h-71) | 186.946    | 线性 -2.0 K/km |

**物理常数(NIST):**
- `T0 = 288.15 K`, `P0 = 101325.0 Pa`, `ρ0 = 1.22500 kg/m³`, `a0 = 340.294 m/s`
- `R_specific_dry_air = 287.0531 J/(kg·K)` (US 1976 标准)
- `g0 = 9.80665 m/s²`, `M_air = 0.0289644 kg/mol`, `R_universal = 8.31447 J/(mol·K)`
- `gamma = 1.4`, `Earth_radius = 6356.766 km`(US 1976)
- Sutherland 系数:`B = 1.458e-6 kg/(m·s·K^0.5)`, `S = 110.4 K`

### 1.2 压强公式

对每个层分别积分:
- **线性 lapse 段** (β ≠ 0,β 单位 K/m):
  `P / P_bottom = (T_bottom / T)^(g0·M / (R*·β))`
  指数:`g0·M / R_universal / β = 0.034163 / (β/1000)`
- **等温段** (β = 0):
  `P / P_bottom = exp(-g0·M·(h - h_bottom)·1000 / (R*·T_bottom))`

### 1.3 与 reference 的差异(已修 bug)

reference `Atmosphere_US_1976` 用 `k = 34.163195`,然后 `pp = (T0/T)^(-k·6.5)`。展开:
- 标准指数应是 `g0·M / (R*·L) = 5.2561`(L=6.5e-3 K/m)
- reference 算成 `k·6.5 = 222.06`,**差 42 倍**

我们用正确的 `g0·M / R_universal = 0.034163 K^(-1)·m^(-1)`,各层 lapse 转 K/m 后用标准积分公式。**h=0 处巧合等价(0 次方 = 1),h>0 处与 NASA 表格匹配(容差 1%)**。

### 1.4 几何 vs geopotential 高度

`atmosphere_us_1976(altitude_km)` 接受 **geopotential** 高度。要从几何高度 z 转 geopotential H:

```
H = R_earth · z / (R_earth + z)
```

`geometric_to_geopotential_km(z_km)` 提供该转换。常用 CFD 高度(0–30 km)差异 < 0.5%。

### 1.5 公共 API

```python
@dataclass(frozen=True)
class AtmosphereResult:
    T: float   # K
    P: float   # Pa
    rho: float # kg/m^3
    mu: float  # Pa·s
    a: float   # m/s(声速)

def atmosphere_us_1976(altitude_km: float) -> AtmosphereResult: ...
def geometric_to_geopotential_km(z_km: float) -> float: ...
def sutherland_mu(T: float) -> float: ...  # Pa·s
def reynolds_number(velocity_ms, pressure_pa, temperature_k) -> float: ...  # /m
def reynolds_number_at_altitude(altitude_km, velocity_ms) -> float: ...     # /m
```

错误边界:
- `altitude_km < 0` 或 `> 84.852` → `ValueError`(不 `sys.exit`,库式)
- `T <= 0` → `sutherland_mu` 抛 `ValueError`
- `velocity_ms < 0` → `reynolds_number` 抛 `ValueError`

---

## 2. 风轴/体轴变换(`aero_math.py`)

### 2.1 矩阵定义

体轴 → 风轴变换矩阵(reference `CFDPlus_V4.py:cal_var_b2w`):

```
        | cos α·cos β   sin β    sin α·cos β |
A_bw  = | -sin β·cos α  cos β   -sin α·sin β |
        | -sin α        0        cos α       |
```

- `body_to_wind(body_vec, α_rad, β_rad)` = `A_bw · body_vec`
- `wind_to_body(wind_vec, α_rad, β_rad)` = `A_bw^T · wind_vec`

### 2.2 速度分量公式

```
u = V · cos α · cos β
v = V · sin β
w = V · sin α · cos β
```

反推(`uvw_to_alpha_beta` **返回度**,与 reference 一致):
```
V    = sqrt(u² + v² + w²)
β    = asin(v / V)
α    = atan2(w / cos β, u / cos β)
```

约定:
- `V < 1e-12` → 返回 `(α=0, β=0)`
- `|cos β| < 1e-12`(纯 sideslip,β=±π/2)→ `α = ±π/2` 取决于 `w` 符号

### 2.3 numpy soft fallback

`body_to_wind` / `wind_to_body` 在 `numpy` 可用时走 `np.asarray + @`(矩阵乘加速,大批量调用更快);否则纯 `math` 实现(`_mat3_vec3_dot` 展开 dot 不循环)。两路径浮点舍入顺序一致。

测试覆盖 `monkeypatch.setitem(sys.modules, "numpy", None)` 屏蔽 numpy 后纯 math 仍正确。

### 2.4 公共 API

```python
def alpha_beta_to_uvw(vel: float, alpha_rad: float, beta_rad: float) -> tuple[float, float, float]
def uvw_to_alpha_beta(u: float, v: float, w: float) -> tuple[float, float]  # 度!
def body_to_wind(body_vec, alpha_rad, beta_rad) -> tuple[float, float, float]
def wind_to_body(wind_vec, alpha_rad, beta_rad) -> tuple[float, float, float]
```

### 2.5 关键测试用例

| 测试 | 用例 | 期望 |
|---|---|---|
| `alpha_beta_to_uvw` 互逆 | 7 个 α/β 组合(0/5/15/30/45/60/89°) | round-trip 误差 < 1e-9 |
| `body_to_wind` 互逆 | 7 角度 × 6 向量 = 42 case | round-trip 误差 < 1e-9 |
| `body_to_wind(body=(1,0,0), α=0, β=0)` | 单位 x | `(1, 0, 0)` |
| `body_to_wind(body=(1,0,0), α=10°, β=0)` | 攻角 10° | `(cos 10°, 0, -sin 10°)` |
| `uvw_to_alpha_beta(0, V, 0)` | 纯 sideslip | `(_, 90°)` |
