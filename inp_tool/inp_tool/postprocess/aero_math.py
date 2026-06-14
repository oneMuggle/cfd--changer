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

    单独抽函数是为了让 monkeypatch 在测试中能屏蔽 numpy
    (``sys.modules['numpy'] = None``)。
    """
    try:
        import numpy as np  # type: ignore
        return np
    except (ImportError, AttributeError):
        # AttributeError 出现在 monkeypatch 将 sys.modules['numpy']=None 后
        # 的极端情况(import None 不抛但访问属性时抛)
        return None


def _build_abw_matrix_math(alpha_rad: float, beta_rad: float):
    """构造 A_bw 矩阵(纯 math 路径,3×3 嵌套 list)。"""
    cos_a = math.cos(alpha_rad)
    sin_a = math.sin(alpha_rad)
    cos_b = math.cos(beta_rad)
    sin_b = math.sin(beta_rad)
    return [
        [cos_a * cos_b,  sin_b,   sin_a * cos_b],
        [-sin_b * cos_a, cos_b,  -sin_a * sin_b],
        [-sin_a,         0.0,     cos_a        ],
    ]


def _mat3_vec3_dot(mat, vec) -> Vec3:
    """3×3 矩阵 · 3 向量(纯 math 路径)。"""
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

    numpy 可用时走 ``np.dot``(更适合大批量调用);否则纯 math 实现。
    """
    np = _try_import_numpy()
    if np is not None:
        abw = np.array(_build_abw_matrix_math(alpha_rad, beta_rad))
        wind = np.dot(abw, np.array(body_vec, dtype=float))
        return (float(wind[0]), float(wind[1]), float(wind[2]))
    mat = _build_abw_matrix_math(alpha_rad, beta_rad)
    return _mat3_vec3_dot(mat, body_vec)


def wind_to_body(wind_vec: Sequence[float], alpha_rad: float, beta_rad: float) -> Vec3:
    """风轴向量变换到体轴坐标系:body = A_bw^T · wind。

    参数:
    - ``wind_vec``:长度 3 序列
    - ``alpha_rad`` / ``beta_rad``:弧度

    返回:长度 3 tuple ``(body_x, body_y, body_z)``。
    """
    np = _try_import_numpy()
    if np is not None:
        abw = np.array(_build_abw_matrix_math(alpha_rad, beta_rad))
        awb = abw.T
        body = np.dot(awb, np.array(wind_vec, dtype=float))
        return (float(body[0]), float(body[1]), float(body[2]))
    mat = _build_abw_matrix_math(alpha_rad, beta_rad)
    mat_t = _mat3_transpose(mat)
    return _mat3_vec3_dot(mat_t, wind_vec)
