"""US 1976 标准大气模型 + Sutherland 粘度 + Reynolds 数。

零运行时依赖,纯 Python stdlib(``math`` + ``dataclasses``)。

物理常数(US 1976 / NIST):
- ``T0 = 288.15 K`` (15°C 标准海平面温度)
- ``P0 = 101325.0 Pa`` (标准海平面压强)
- ``rho0 = 1.22500 kg/m^3`` (标准海平面密度)
- ``a0 = 340.294 m/s`` (标准海平面声速)
- ``R_specific_dry_air = 287.0531 J/(kg·K)`` (US 1976 标准)
- ``g0 = 9.80665 m/s^2`` (重力加速度)
- ``M_air = 0.0289644 kg/mol`` (空气摩尔质量)
- ``r_earth = 6356.766 km`` (地球有效半径)
- ``gamma = 1.4`` (空气比热比)
- ``B = 1.458e-6 kg/(m·s·K^0.5)`` (Sutherland 系数)
- ``S = 110.4 K`` (Sutherland 温度)

分层 lapse rate(geopotential height):
| 段(km)        | T 公式                  | 段顶 T(K) |
|---------------|------------------------|-----------|
| 0    – 11.0   | T = 288.15 - 6.5·h      | 216.65    |
| 11   – 20.0   | T = 216.65              | 216.65    |
| 20   – 32.0   | T = 216.65 + 1·(h-20)   | 228.65    |
| 32   – 47.0   | T = 228.65 + 2.8·(h-32) | 270.65    |
| 47   – 51.0   | T = 270.65              | 270.65    |
| 51   – 71.0   | T = 270.65 - 2.8·(h-51) | 214.65    |
| 71   – 84.852 | T = 214.65 - 2.0·(h-71) | 186.946   |

实现细节(与 reference 的差异):
- ``reference/code/CFDPlus_V4.py:Atmosphere_US_1976`` 的压强常数
  ``k=34.163195`` 与 geopotential 转换有量纲错误,在 h>0 处给出错误的
  P/ρ。本实现遵循 NASA 公开数据,在 h=0 处与 reference 一致(海平面
  Identity),在 h>0 处与 NASA 表格一致。
- ``reference`` 现代后处理路径 ``build_runpara_from_inp`` 直接用
  ``aero_pres / aero_temp``,**不依赖**这个函数,所以 reference 上层
  输出不受 bug 影响。本模块为新版后处理 ``forces.py`` 在 ``intyp=1``
  (Ma-H 模式)时使用。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# ============================================================================
# 物理常数
# ============================================================================

# 标准海平面
_T0 = 288.15           # K
_P0 = 101325.0         # Pa

# 物性
_R_SPECIFIC = 287.0531   # J/(kg·K) — 干空气比气体常数(US 1976)
_GAMMA = 1.4             # 比热比
_G0 = 9.80665            # m/s^2
_M_AIR = 0.0289644       # kg/mol
_R_UNIV = 8.31447        # J/(mol·K)
_R_EARTH_KM = 6356.766   # 地球有效半径(km)

# Sutherland 公式
_SUTHERLAND_B = 1.458e-6  # kg/(m·s·K^0.5)
_SUTHERLAND_S = 110.4     # K

# US 1976 模型上限
_H_MAX_KM = 84.852

# 分层断点(geopotential height in km)
_LAYER_BREAKS = (0.0, 11.0, 20.0, 32.0, 47.0, 51.0, 71.0, _H_MAX_KM)

# 每层 lapse rate(K/km)
_LAPSE_RATES = (-6.5, 0.0, +1.0, +2.8, 0.0, -2.8, -2.0)


def _build_base_temperatures() -> tuple:
    """从 _T0=288.15 起逐段累积每个分层断点的温度(段顶=下段起点)。"""
    temps = [_T0]
    for i in range(len(_LAPSE_RATES)):
        h_bottom = _LAYER_BREAKS[i]
        h_top = _LAYER_BREAKS[i + 1]
        temps.append(temps[-1] + _LAPSE_RATES[i] * (h_top - h_bottom))
    return tuple(temps)


_BASE_TEMPS = _build_base_temperatures()  # 长度 = len(_LAYER_BREAKS)


# ============================================================================
# AtmosphereResult dataclass
# ============================================================================

@dataclass(frozen=True)
class AtmosphereResult:
    """US 1976 大气模型在给定高度的状态。

    所有字段单位 SI:
    - ``T`` (K): 温度
    - ``P`` (Pa): 压强
    - ``rho`` (kg/m^3): 密度
    - ``mu`` (Pa·s): 动力粘度(由 Sutherland 公式)
    - ``a`` (m/s): 声速 = sqrt(γ·R·T)
    """
    T: float
    P: float
    rho: float
    mu: float
    a: float


# ============================================================================
# 内部工具
# ============================================================================

def _geometric_to_geopotential_km(z_km: float) -> float:
    """几何高度 z(km) → geopotential 高度 H(km)。

    H = r·z / (r + z) ,其中 r = 6356.766 km(US 1976)。
    在 z < 100 km 时差异极小(z=11 时 H≈10.981,差 0.17%)。
    """
    return _R_EARTH_KM * z_km / (_R_EARTH_KM + z_km)


def _find_layer_index(h_km: float) -> int:
    """根据 geopotential 高度 h(km)找到所在层索引(0..6)。

    ``h=11.0`` 属于第 1 层(11–20 km),边界归"上层"。
    """
    if h_km < 0.0:
        raise ValueError(
            f"altitude {h_km} km is below sea level (model starts at 0)"
        )
    if h_km > _H_MAX_KM:
        raise ValueError(
            f"altitude {h_km} km is above US 1976 model upper limit ({_H_MAX_KM} km)"
        )
    for i in range(len(_LAPSE_RATES)):
        if h_km <= _LAYER_BREAKS[i + 1]:
            return i
    return len(_LAPSE_RATES) - 1  # 不应到达,_H_MAX_KM 上限已守护


def _temperature_at(h_km: float, layer_idx: int) -> float:
    """在给定层内插出温度(geopotential)。"""
    h_bottom = _LAYER_BREAKS[layer_idx]
    T_bottom = _BASE_TEMPS[layer_idx]
    lapse = _LAPSE_RATES[layer_idx]
    return T_bottom + lapse * (h_km - h_bottom)


def _pressure_at(h_km: float, layer_idx: int, T: float) -> float:
    """在给定层内积分得到压强(标准大气压强公式)。

    从 h=0 起逐层累积层底压强,然后在当前层内从 h_bottom 积分到 h:
    - lapse ≠ 0: P = P_bottom · (T_bottom / T) ^ (g0·M / (R·L_m))
    - lapse = 0(等温): P = P_bottom · exp(-g0·M·(h - h_bottom)·1000 / (R·T))

    注意 ``lapse`` 单位 K/km,公式里需换 K/m: ``L_m = lapse / 1000``。
    """
    P_at = _P0
    for i in range(layer_idx):
        h_lo = _LAYER_BREAKS[i]
        h_hi = _LAYER_BREAKS[i + 1]
        T_lo = _BASE_TEMPS[i]
        T_hi = _BASE_TEMPS[i + 1]
        lapse = _LAPSE_RATES[i]
        if abs(lapse) < 1e-12:
            # 等温段
            P_at *= math.exp(
                -_G0 * _M_AIR * (h_hi - h_lo) * 1000.0 / (_R_UNIV * T_lo)
            )
        else:
            # 线性递降/升温段
            L_m = lapse / 1000.0
            P_at *= (T_lo / T_hi) ** (_G0 * _M_AIR / (_R_UNIV * L_m))

    # 在当前层内从 h_bottom 积分到 h_km
    h_bottom = _LAYER_BREAKS[layer_idx]
    T_bottom = _BASE_TEMPS[layer_idx]
    lapse = _LAPSE_RATES[layer_idx]
    if abs(lapse) < 1e-12:
        return P_at * math.exp(
            -_G0 * _M_AIR * (h_km - h_bottom) * 1000.0 / (_R_UNIV * T_bottom)
        )
    L_m = lapse / 1000.0
    return P_at * (T_bottom / T) ** (_G0 * _M_AIR / (_R_UNIV * L_m))


# ============================================================================
# 公共 API
# ============================================================================

def atmosphere_us_1976(altitude_km: float) -> AtmosphereResult:
    """US 1976 标准大气模型。

    输入 ``altitude_km`` 是 **geopotential 高度**(km,US 1976 标准基准量)。
    若手头是几何高度,先用 :func:`geometric_to_geopotential_km` 转一下。

    返回温度 / 压强 / 密度 / 粘度 / 声速。

    范围:0 ≤ altitude_km ≤ 84.852(geopotential)。超出抛 ``ValueError``。

    几何 vs geopotential:
    - 在常用 CFD 高度(0–30 km)差异 < 0.5%,可互换使用
    - 至 71 km 差异约 1%(geometric 71 km ≈ geopotential 70.22 km)
    - US 1976 标准表本身用 geopotential 高度,本函数保持一致
    """
    layer_idx = _find_layer_index(altitude_km)
    T = _temperature_at(altitude_km, layer_idx)
    P = _pressure_at(altitude_km, layer_idx, T)
    rho = P / (_R_SPECIFIC * T)
    mu = sutherland_mu(T)
    a = math.sqrt(_GAMMA * _R_SPECIFIC * T)
    return AtmosphereResult(T=T, P=P, rho=rho, mu=mu, a=a)


def geometric_to_geopotential_km(z_km: float) -> float:
    """几何高度 z(km) → geopotential 高度 H(km)。

    H = r·z / (r + z),其中 r = 6356.766 km(US 1976 标准)。
    在 z < 30 km 时差异 < 0.5%,在 z = 71 km 时差异约 1%。

    用法::

        H = geometric_to_geopotential_km(11.0)   # ≈ 10.981
        result = atmosphere_us_1976(H)            # T=216.65 at H=11
    """
    return _geometric_to_geopotential_km(z_km)


def sutherland_mu(T: float) -> float:
    """Sutherland 公式动力粘度 μ(T) (Pa·s)。

    μ = B·T^1.5 / (T + S),空气:B=1.458e-6, S=110.4 K。

    T=0 K 物理无效,抛 ``ValueError``。
    """
    if T <= 0.0:
        raise ValueError(f"temperature {T} K must be positive")
    return _SUTHERLAND_B * (T ** 1.5) / (T + _SUTHERLAND_S)


def reynolds_number(altitude_km: float, velocity_ms: float,
                    pressure_pa: float, temperature_k: float) -> float:
    """单位 Reynolds 数 Re/m = ρ·V/μ。

    使用 ``pressure_pa / temperature_k`` 直接算 ρ(理想气体);
    ``altitude_km`` 参数当前未使用,保留是为了 API 一致性(后续若按
    ``intyp=1`` 走完整 atmosphere 模式时方便扩展)。
    """
    if velocity_ms == 0.0:
        return 0.0
    rho = pressure_pa / (_R_SPECIFIC * temperature_k)
    mu = sutherland_mu(temperature_k)
    return rho * velocity_ms / mu
