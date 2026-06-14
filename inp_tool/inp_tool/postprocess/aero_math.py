"""气动坐标系数学:风轴 ↔ 体轴变换 + (α, β) ↔ (u, v, w) 互推。

零运行时依赖,纯 Python stdlib。``numpy`` 若已安装则用作矩阵加速;
未安装时退化到纯 ``math`` 路径,语义完全一致。

参考实现:``reference/code/CFDPlus_V4.py:65-97``
- 速度分解(:func:`alpha_beta_to_uvw`):
  - u = V · cos α · cos β
  - v = V · sin β
  - w = V · sin α · cos β
- 反推(:func:`uvw_to_alpha_beta`,**返回度**):
  - V = sqrt(u² + v² + w²)
  - β = asin(v / V)
  - α = atan2(w / cos β, u / cos β)
- 体轴 → 风轴矩阵 ``A_bw``::

    A_bw = | cos α·cos β   sin β    sin α·cos β |
           | -sin β·cos α  cos β   -sin α·sin β |
           | -sin α        0        cos α       |

  :func:`body_to_wind` = A_bw · body_vec
  :func:`wind_to_body` = A_bw^T · wind_vec
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

Vec3 = Tuple[float, float, float]

# ============================================================================
# 角度与速度互推
# ============================================================================

def alpha_beta_to_uvw(vel: float, alpha_rad: float, beta_rad: float) -> Vec3:
    """从攻角 α、侧滑角 β、合速度 V,算出体轴速度分量 (u, v, w)。

    - α、β 单位是 **弧度**
    - 返回 ``(u, v, w)`` 三元 tuple,单位与 ``vel`` 一致

    特殊情况:``vel == 0`` → 返回 ``(0, 0, 0)``。
    """
    if vel == 0.0:
        return (0.0, 0.0, 0.0)
    cos_a = math.cos(alpha_rad)
    sin_a = math.sin(alpha_rad)
    cos_b = math.cos(beta_rad)
    sin_b = math.sin(beta_rad)
    u = vel * cos_a * cos_b
    v = vel * sin_b
    w = vel * sin_a * cos_b
    return (u, v, w)


def uvw_to_alpha_beta(u: float, v: float, w: float) -> Tuple[float, float]:
    """从体轴速度分量 (u, v, w),反推攻角 α 与侧滑角 β。

    返回 ``(alpha_deg, beta_deg)`` 二元 tuple,**单位是度**(不是弧度!)。

    特殊情况:
    - ``V = sqrt(u² + v² + w²) < 1e-12`` → 返回 ``(0, 0)``
    - ``|cos β| < 1e-12``(纯 sideslip)→ α = ±90° 取决于 w 符号
    """
    vel = math.sqrt(u * u + v * v + w * w)
    if vel < 1e-12:
        return (0.0, 0.0)
    # 注意 clamp 到 [-1, 1] 避免数值噪声进 asin 域外
    sin_beta_clamped = max(-1.0, min(1.0, v / vel))
    beta = math.asin(sin_beta_clamped)
    cos_beta = math.cos(beta)
    if abs(cos_beta) < 1e-12:
        # β = ±π/2(纯侧滑),α 退化:沿 w 的方向取 ±π/2
        alpha = math.pi / 2.0 if w >= 0 else -math.pi / 2.0
    else:
        alpha = math.atan2(w / cos_beta, u / cos_beta)
    return (math.degrees(alpha), math.degrees(beta))


# ============================================================================
# 体轴 ↔ 风轴 坐标系变换
# ============================================================================

def _try_import_numpy():
    """soft import numpy:不可用就返回 None(支持 fallback)。

    用 ``sys.modules.get("numpy")`` 而非 ``import numpy`` 是为了让 monkeypatch
    在测试中能屏蔽 numpy(``sys.modules["numpy"] = None``),且避免在某些
    Python 解释器上 ``import None`` 触发 TypeError/AttributeError 的奇怪行为。
    """
    import sys
    mod = sys.modules.get("numpy")
    if mod is not None:
        return mod
    try:
        import numpy as np  # type: ignore
        return np
    except ImportError:
        return None


def _trig_components(alpha_rad: float, beta_rad: float):
    """一次性算出 (cos α, sin α, cos β, sin β),math 与 numpy 路径共享。"""
    return (
        math.cos(alpha_rad),
        math.sin(alpha_rad),
        math.cos(beta_rad),
        math.sin(beta_rad),
    )


def _abw_rows(ca: float, sa: float, cb: float, sb: float):
    """构造 A_bw 矩阵的 3 行嵌套 list(纯 math 路径直接 dot,numpy 路径
    一次 ``asarray`` 转 ndarray;两路径浮点舍入顺序完全一致)。"""
    return [
        [ca * cb,  sb,    sa * cb ],
        [-sb * ca, cb,   -sa * sb],
        [-sa,      0.0,   ca     ],
    ]


def _mat3_vec3_dot(mat, vec) -> Vec3:
    """3×3 矩阵 · 3 向量(纯 math 路径,显式展开避免循环开销)。"""
    return (
        mat[0][0] * vec[0] + mat[0][1] * vec[1] + mat[0][2] * vec[2],
        mat[1][0] * vec[0] + mat[1][1] * vec[1] + mat[1][2] * vec[2],
        mat[2][0] * vec[0] + mat[2][1] * vec[1] + mat[2][2] * vec[2],
    )


def _mat3_transpose(mat):
    """3×3 矩阵转置(纯 math 路径,新 list)。"""
    return [
        [mat[0][0], mat[1][0], mat[2][0]],
        [mat[0][1], mat[1][1], mat[2][1]],
        [mat[0][2], mat[1][2], mat[2][2]],
    ]


def body_to_wind(body_vec: Sequence[float], alpha_rad: float, beta_rad: float) -> Vec3:
    """体轴向量变换到风轴坐标系:wind = A_bw · body。

    参数:
    - ``body_vec``:长度 3 序列(可以是 tuple/list/np.ndarray)
    - ``alpha_rad`` / ``beta_rad``:弧度

    返回:长度 3 tuple ``(wind_x, wind_y, wind_z)``。

    numpy 可用时用 ``np.asarray + @`` 走加速;否则纯 math 实现。
    两路径共享同一组 ``_trig_components`` + ``_abw_rows``,浮点舍入顺序一致。
    """
    ca, sa, cb, sb = _trig_components(alpha_rad, beta_rad)
    rows = _abw_rows(ca, sa, cb, sb)
    np = _try_import_numpy()
    if np is not None:
        abw = np.asarray(rows, dtype=float)
        vec = np.asarray(body_vec, dtype=float)
        wind = abw @ vec
        return (float(wind[0]), float(wind[1]), float(wind[2]))
    return _mat3_vec3_dot(rows, body_vec)


def wind_to_body(wind_vec: Sequence[float], alpha_rad: float, beta_rad: float) -> Vec3:
    """风轴向量变换到体轴坐标系:body = A_bw^T · wind。

    参数:
    - ``wind_vec``:长度 3 序列
    - ``alpha_rad`` / ``beta_rad``:弧度

    返回:长度 3 tuple ``(body_x, body_y, body_z)``。
    """
    ca, sa, cb, sb = _trig_components(alpha_rad, beta_rad)
    rows = _abw_rows(ca, sa, cb, sb)
    np = _try_import_numpy()
    if np is not None:
        abw = np.asarray(rows, dtype=float)
        vec = np.asarray(wind_vec, dtype=float)
        body = abw.T @ vec
        return (float(body[0]), float(body[1]), float(body[2]))
    rows_t = _mat3_transpose(rows)
    return _mat3_vec3_dot(rows_t, wind_vec)
