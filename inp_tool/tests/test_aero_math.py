"""``inp_tool.postprocess.aero_math`` 单元测试。

测试覆盖:
- ``alpha_beta_to_uvw`` / ``uvw_to_alpha_beta`` 互逆性
- ``body_to_wind`` / ``wind_to_body`` 互逆性
- 边界:零速度、|cos β| ≈ 0 的极端 sideslip
- numpy soft fallback:屏蔽 numpy 后纯 math 路径仍工作

参考实现:``reference/code/CFDPlus_V4.py:65-97``
- ``cal_uvw(vel, α_rad, β_rad)``:
  - u = V·cos α·cos β
  - v = V·sin β
  - w = V·sin α·cos β
- ``cal_alpha_beta_from_uvw(u, v, w)``: 反推,返回 **度** (不是弧度!)
- ``cal_var_b2w(body, α_rad, β_rad)``: A_bw·body
  A_bw = [[cα·cβ,  sβ,  sα·cβ],
          [-sβ·cα, cβ, -sα·sβ],
          [-sα,    0,   cα   ]]
- ``cal_var_w2b(wind, α_rad, β_rad)``: A_bw.T·wind(逆变换)
"""
from __future__ import annotations

import math
import sys

import pytest

from inp_tool.postprocess.aero_math import (
    alpha_beta_to_uvw,
    body_to_wind,
    uvw_to_alpha_beta,
    wind_to_body,
)


# ============================================================================
# alpha_beta_to_uvw — α/β → (u, v, w)
# ============================================================================

class TestAlphaBetaToUvw:
    """V·cos α·cos β / V·sin β / V·sin α·cos β。"""

    def test_zero_angles_returns_velocity_along_x(self):
        """α=0, β=0 → (V, 0, 0)。"""
        u, v, w = alpha_beta_to_uvw(100.0, 0.0, 0.0)
        assert u == pytest.approx(100.0)
        assert v == pytest.approx(0.0, abs=1e-12)
        assert w == pytest.approx(0.0, abs=1e-12)

    def test_pure_alpha_positive(self):
        """α=10°(rad=0.1745),β=0 → (V·cos α, 0, V·sin α)。"""
        alpha = math.radians(10.0)
        u, v, w = alpha_beta_to_uvw(100.0, alpha, 0.0)
        assert u == pytest.approx(100.0 * math.cos(alpha))
        assert v == pytest.approx(0.0, abs=1e-12)
        assert w == pytest.approx(100.0 * math.sin(alpha))

    def test_pure_beta_positive(self):
        """α=0, β=5° → (V·cos β, V·sin β, 0)。"""
        beta = math.radians(5.0)
        u, v, w = alpha_beta_to_uvw(100.0, 0.0, beta)
        assert u == pytest.approx(100.0 * math.cos(beta))
        assert v == pytest.approx(100.0 * math.sin(beta))
        assert w == pytest.approx(0.0, abs=1e-12)

    def test_combined_alpha_beta(self):
        """α=15°, β=8°,验证 u²+v²+w² = V²。"""
        alpha = math.radians(15.0)
        beta = math.radians(8.0)
        vel = 100.0
        u, v, w = alpha_beta_to_uvw(vel, alpha, beta)
        norm_squared = u * u + v * v + w * w
        assert norm_squared == pytest.approx(vel * vel, rel=1e-10)

    def test_zero_velocity_returns_zero_vector(self):
        u, v, w = alpha_beta_to_uvw(0.0, math.radians(10.0), math.radians(5.0))
        assert u == 0.0
        assert v == 0.0
        assert w == 0.0


# ============================================================================
# uvw_to_alpha_beta — (u, v, w) → α/β 度
# ============================================================================

class TestUvwToAlphaBeta:
    """注意返回值是 **度**,非弧度。"""

    def test_pure_x_velocity_returns_zero(self):
        """(V, 0, 0) → α=0, β=0。"""
        alpha_deg, beta_deg = uvw_to_alpha_beta(100.0, 0.0, 0.0)
        assert alpha_deg == pytest.approx(0.0, abs=1e-9)
        assert beta_deg == pytest.approx(0.0, abs=1e-9)

    def test_pure_z_velocity_alpha_90(self):
        """(0, 0, V) → α=90°, β=0。"""
        alpha_deg, beta_deg = uvw_to_alpha_beta(0.0, 0.0, 100.0)
        assert alpha_deg == pytest.approx(90.0, abs=1e-6)
        assert beta_deg == pytest.approx(0.0, abs=1e-9)

    def test_pure_neg_z_velocity_alpha_neg_90(self):
        """(0, 0, -V) → α=-90°, β=0。"""
        alpha_deg, beta_deg = uvw_to_alpha_beta(0.0, 0.0, -100.0)
        assert alpha_deg == pytest.approx(-90.0, abs=1e-6)
        assert beta_deg == pytest.approx(0.0, abs=1e-9)

    def test_pure_y_velocity_beta_90(self):
        """(0, V, 0) → β=90°(全 sideslip)。"""
        alpha_deg, beta_deg = uvw_to_alpha_beta(0.0, 100.0, 0.0)
        assert beta_deg == pytest.approx(90.0, abs=1e-6)

    def test_zero_velocity_returns_zero(self):
        """V≈0 → 返回 (0, 0)(避免 0 除)。"""
        alpha_deg, beta_deg = uvw_to_alpha_beta(0.0, 0.0, 0.0)
        assert alpha_deg == 0.0
        assert beta_deg == 0.0

    def test_tiny_velocity_returns_zero(self):
        """V < 1e-12 → 也返回 (0, 0)。"""
        alpha_deg, beta_deg = uvw_to_alpha_beta(1e-15, 1e-15, 1e-15)
        assert alpha_deg == 0.0
        assert beta_deg == 0.0


# ============================================================================
# alpha_beta_to_uvw <-> uvw_to_alpha_beta 互逆
# ============================================================================

class TestUvwAlphaBetaRoundTrip:
    """α/β → uvw → α/β 应当回到原值(在正常工作范围内)。"""

    @pytest.mark.parametrize(
        "alpha_deg, beta_deg",
        [
            (0.0, 0.0),
            (5.0, 0.0),
            (-5.0, 0.0),
            (15.0, 3.0),
            (-15.0, -3.0),
            (30.0, 10.0),
            (-30.0, 10.0),
            (45.0, 15.0),
            (60.0, 20.0),
            (89.0, 5.0),  # 接近但不到 ±90°
        ],
    )
    def test_round_trip(self, alpha_deg, beta_deg):
        """α/β → uvw → α/β,误差应 < 1e-9。"""
        vel = 250.0
        alpha_rad = math.radians(alpha_deg)
        beta_rad = math.radians(beta_deg)
        u, v, w = alpha_beta_to_uvw(vel, alpha_rad, beta_rad)
        alpha_back, beta_back = uvw_to_alpha_beta(u, v, w)
        assert alpha_back == pytest.approx(alpha_deg, abs=1e-9)
        assert beta_back == pytest.approx(beta_deg, abs=1e-9)


# ============================================================================
# body_to_wind — A_bw 矩阵
# ============================================================================

class TestBodyToWind:
    """A_bw·body_vec → wind_vec。"""

    def test_zero_angles_is_identity(self):
        """α=0, β=0 时 A_bw = I,body == wind。"""
        body = (1.0, 2.0, 3.0)
        wind = body_to_wind(body, 0.0, 0.0)
        assert wind[0] == pytest.approx(1.0)
        assert wind[1] == pytest.approx(2.0)
        assert wind[2] == pytest.approx(3.0)

    def test_pure_x_body_unit(self):
        """body=(1, 0, 0), α=10°, β=0 → wind = (cos α, 0, -sin α)。"""
        alpha = math.radians(10.0)
        wind = body_to_wind((1.0, 0.0, 0.0), alpha, 0.0)
        assert wind[0] == pytest.approx(math.cos(alpha))
        assert wind[1] == pytest.approx(0.0, abs=1e-12)
        assert wind[2] == pytest.approx(-math.sin(alpha))

    def test_returns_length_3_sequence(self):
        """body_to_wind 必须返回长度 3 的可索引序列。"""
        wind = body_to_wind((1.0, 0.0, 0.0), 0.0, 0.0)
        assert len(wind) == 3
        _ = wind[0], wind[1], wind[2]


class TestBodyWindRoundTrip:
    """body_to_wind → wind_to_body 应回到原向量。"""

    @pytest.mark.parametrize(
        "alpha_deg, beta_deg",
        [
            (0.0, 0.0),
            (5.0, 2.0),
            (-5.0, -2.0),
            (10.0, 5.0),
            (-30.0, 10.0),
            (45.0, 15.0),
            (60.0, -20.0),
        ],
    )
    @pytest.mark.parametrize(
        "body",
        [
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 2.0, 3.0),
            (-1.5, 2.5, -3.5),
            (100.0, -50.0, 25.0),
        ],
    )
    def test_round_trip(self, alpha_deg, beta_deg, body):
        """body → wind → body 误差 < 1e-9。"""
        alpha_rad = math.radians(alpha_deg)
        beta_rad = math.radians(beta_deg)
        wind = body_to_wind(body, alpha_rad, beta_rad)
        body_back = wind_to_body(wind, alpha_rad, beta_rad)
        for i in range(3):
            assert body_back[i] == pytest.approx(body[i], abs=1e-9), \
                f"axis {i}: orig={body[i]}, back={body_back[i]}"


# ============================================================================
# wind_to_body — 反向变换
# ============================================================================

class TestWindToBody:
    """A_bw.T·wind_vec → body_vec。"""

    def test_zero_angles_is_identity(self):
        wind = (10.0, 5.0, 2.0)
        body = wind_to_body(wind, 0.0, 0.0)
        assert body[0] == pytest.approx(10.0)
        assert body[1] == pytest.approx(5.0)
        assert body[2] == pytest.approx(2.0)


# ============================================================================
# numpy soft fallback — 在没有 numpy 时纯 math 也应工作
# ============================================================================

class TestNumpyFallback:
    """``aero_math`` 应在 numpy 不可用时退化到 ``math`` 路径。"""

    def test_alpha_beta_to_uvw_without_numpy(self, monkeypatch):
        """屏蔽 numpy 后 alpha_beta_to_uvw 仍正确。"""
        monkeypatch.setitem(sys.modules, "numpy", None)
        u, v, w = alpha_beta_to_uvw(100.0, math.radians(15.0), math.radians(5.0))
        norm_squared = u * u + v * v + w * w
        assert norm_squared == pytest.approx(100.0 * 100.0, rel=1e-10)

    def test_body_to_wind_without_numpy(self, monkeypatch):
        """屏蔽 numpy 后 body_to_wind 仍正确。"""
        monkeypatch.setitem(sys.modules, "numpy", None)
        wind = body_to_wind((1.0, 2.0, 3.0), 0.0, 0.0)
        assert wind[0] == pytest.approx(1.0)
        assert wind[1] == pytest.approx(2.0)
        assert wind[2] == pytest.approx(3.0)

    def test_round_trip_without_numpy(self, monkeypatch):
        """屏蔽 numpy 后 body↔wind 互逆性仍成立。"""
        monkeypatch.setitem(sys.modules, "numpy", None)
        alpha = math.radians(20.0)
        beta = math.radians(10.0)
        body = (1.0, 2.0, 3.0)
        wind = body_to_wind(body, alpha, beta)
        body_back = wind_to_body(wind, alpha, beta)
        for i in range(3):
            assert body_back[i] == pytest.approx(body[i], abs=1e-9)


# ============================================================================
# 与 reference 实现 sanity 对照
# ============================================================================

class TestReferenceSanity:
    """对照 ``reference/code/CFDPlus_V4.py:cal_uvw`` 经典用例。"""

    def test_reference_canonical_case(self):
        """reference 文档中常见用例:vel=300 m/s, α=10°, β=2°。

        手算:
        - cos α = 0.9848, sin α = 0.1736
        - cos β = 0.9994, sin β = 0.0349
        - u = 300 · 0.9848 · 0.9994 = 295.27
        - v = 300 · 0.0349 = 10.47
        - w = 300 · 0.1736 · 0.9994 = 52.05
        """
        u, v, w = alpha_beta_to_uvw(300.0, math.radians(10.0), math.radians(2.0))
        assert u == pytest.approx(295.27, abs=0.5)
        assert v == pytest.approx(10.47, abs=0.5)
        assert w == pytest.approx(52.05, abs=0.5)

    def test_reference_inp_intyp_3_recovery(self):
        """reference 中 ``aero_intyp==3`` 时从 (u, v, w) 反推 α/β,
        这是 ``parse_mcfd_inp`` 的关键路径(V4.py:122-126)。"""
        alpha_in = 15.0
        beta_in = 3.0
        u, v, w = alpha_beta_to_uvw(
            250.0, math.radians(alpha_in), math.radians(beta_in)
        )
        alpha_out, beta_out = uvw_to_alpha_beta(u, v, w)
        assert alpha_out == pytest.approx(alpha_in, abs=1e-9)
        assert beta_out == pytest.approx(beta_in, abs=1e-9)
