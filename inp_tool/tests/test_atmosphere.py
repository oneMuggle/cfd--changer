"""``inp_tool.postprocess.atmosphere`` 单元测试。

测试基准:NASA US Standard Atmosphere 1976 公开数据表
(https://ntrs.nasa.gov/citations/19770009539)。

设计要点:
- ``reference/code/CFDPlus_V4.py`` 中 ``Atmosphere_US_1976`` 的压强公式
  系数 ``k=34.163195`` 与 geopotential 转换有量纲错误,会在 h>0 处给出
  错误的 P/ρ。我们的实现按 NASA 公开数据 + 正确单位重做,在 h=0 处与
  reference 一致,在 h>0 处与 NASA 表格一致。
- ``reference`` 的 ``build_runpara_from_inp`` 直接用 ``aero_pres / aero_temp``,
  不走 ``Atmosphere_US_1976``,所以 reference 上层后处理不受这个 bug 影响。

NASA US 1976 标准值(允许 1% 相对误差吸收 g₀/M/R 常数差异):
| H(km) | T(K)    | P(Pa)        | ρ(kg/m³)   | a(m/s)  |
|-------|---------|--------------|------------|---------|
| 0     | 288.150 | 101325.00    | 1.22500    | 340.294 |
| 5     | 255.676 |  54019.91    | 0.73643    | 320.545 |
| 10    | 223.252 |  26499.88    | 0.41351    | 299.532 |
| 11    | 216.650 |  22632.06    | 0.36391    | 295.069 |
| 15    | 216.650 |  12044.57    | 0.19367    | 295.069 |
| 20    | 216.650 |   5474.89    | 0.08803    | 295.069 |
| 25    | 221.552 |   2511.02    | 0.03946    | 298.389 |
| 32    | 228.650 |    868.0167  | 0.01322    | 303.130 |
| 47    | 270.650 |    110.906   | 0.001427   | 329.799 |
| 71    | 214.650 |      3.9564  | 6.421e-5   | 293.704 |
"""
from __future__ import annotations

import math

import pytest

from inp_tool.postprocess.atmosphere import (
    AtmosphereResult,
    atmosphere_us_1976,
    reynolds_number,
    sutherland_mu,
)


# ============================================================================
# AtmosphereResult dataclass
# ============================================================================

class TestAtmosphereResult:
    """``AtmosphereResult`` 数据载体最低限度的形状校验。"""

    def test_field_order_T_P_rho_mu_a(self):
        result = AtmosphereResult(T=288.15, P=101325.0, rho=1.225, mu=1.789e-5, a=340.294)
        assert result.T == pytest.approx(288.15)
        assert result.P == pytest.approx(101325.0)
        assert result.rho == pytest.approx(1.225)
        assert result.mu == pytest.approx(1.789e-5)
        assert result.a == pytest.approx(340.294)


# ============================================================================
# atmosphere_us_1976 — NASA 标准对照
# ============================================================================

# (h_km, T_K, P_Pa, rho_kg_m3, a_m_s) — 容差吸收常数差异
NASA_REFERENCE_TABLE = [
    (0.0,    288.150, 101325.00,   1.22500,    340.294),
    (5.0,    255.676,  54019.91,   0.73643,    320.545),
    (10.0,   223.252,  26499.88,   0.41351,    299.532),
    (11.0,   216.650,  22632.06,   0.36391,    295.069),
    (15.0,   216.650,  12044.57,   0.19367,    295.069),
    (20.0,   216.650,   5474.89,   0.08803,    295.069),
    (25.0,   221.552,   2511.02,   0.03946,    298.389),
    (32.0,   228.650,    868.017,  0.01322,    303.130),
    (47.0,   270.650,    110.906,  0.001427,   329.799),
    (71.0,   214.650,      3.9564, 6.421e-5,   293.704),
]


class TestAtmosphereUs1976NasaReference:
    """对照 NASA US 1976 公开数据表的标准值。"""

    @pytest.mark.parametrize("h_km, T, P, rho, a", NASA_REFERENCE_TABLE)
    def test_temperature_against_nasa(self, h_km, T, P, rho, a):
        result = atmosphere_us_1976(h_km)
        assert result.T == pytest.approx(T, rel=0.005), \
            f"T at h={h_km} km expected {T} K, got {result.T}"

    @pytest.mark.parametrize("h_km, T, P, rho, a", NASA_REFERENCE_TABLE)
    def test_pressure_against_nasa(self, h_km, T, P, rho, a):
        result = atmosphere_us_1976(h_km)
        assert result.P == pytest.approx(P, rel=0.01), \
            f"P at h={h_km} km expected {P} Pa, got {result.P}"

    @pytest.mark.parametrize("h_km, T, P, rho, a", NASA_REFERENCE_TABLE)
    def test_density_against_nasa(self, h_km, T, P, rho, a):
        result = atmosphere_us_1976(h_km)
        assert result.rho == pytest.approx(rho, rel=0.01), \
            f"rho at h={h_km} km expected {rho} kg/m^3, got {result.rho}"

    @pytest.mark.parametrize("h_km, T, P, rho, a", NASA_REFERENCE_TABLE)
    def test_sound_speed_against_nasa(self, h_km, T, P, rho, a):
        result = atmosphere_us_1976(h_km)
        assert result.a == pytest.approx(a, rel=0.005), \
            f"a at h={h_km} km expected {a} m/s, got {result.a}"


# ============================================================================
# atmosphere_us_1976 — 分层边界(每个 US 1976 段)
# ============================================================================

class TestAtmosphereLayerBoundaries:
    """每个温度分层边界的端点连续性。"""

    def test_h_0_km_sea_level_exact(self):
        """h=0 km 是 ICAO 标准海平面,T=288.15, P=101325, ρ=1.225, a=340.294。"""
        result = atmosphere_us_1976(0.0)
        assert result.T == pytest.approx(288.15, abs=0.01)
        assert result.P == pytest.approx(101325.0, abs=1.0)
        assert result.rho == pytest.approx(1.225, abs=0.001)
        assert result.a == pytest.approx(340.294, abs=0.1)

    def test_h_11_km_tropopause_temperature_constant(self):
        """11 km 是对流层顶,T=216.65 K(等温层起点)。"""
        result = atmosphere_us_1976(11.0)
        assert result.T == pytest.approx(216.65, abs=0.05)

    def test_h_20_km_lapse_starts_positive(self):
        """20 km 起 +1 K/km 升温,边界仍 T=216.65。"""
        result = atmosphere_us_1976(20.0)
        assert result.T == pytest.approx(216.65, abs=0.05)

    def test_h_32_km_lapse_changes_to_2p8(self):
        """32 km 起 +2.8 K/km,边界 T=228.65。"""
        result = atmosphere_us_1976(32.0)
        assert result.T == pytest.approx(228.65, abs=0.05)

    def test_h_47_km_stratopause_constant(self):
        """47 km 起平流层顶等温,T=270.65。"""
        result = atmosphere_us_1976(47.0)
        assert result.T == pytest.approx(270.65, abs=0.05)

    def test_h_51_km_lapse_changes_to_neg2p8(self):
        """51 km 起 -2.8 K/km,边界仍 T=270.65。"""
        result = atmosphere_us_1976(51.0)
        assert result.T == pytest.approx(270.65, abs=0.05)

    def test_h_71_km_lapse_changes_to_neg2p0(self):
        """71 km 起 -2.0 K/km,边界 T=214.65。"""
        result = atmosphere_us_1976(71.0)
        assert result.T == pytest.approx(214.65, abs=0.05)

    def test_h_84p852_km_upper_bound_still_valid(self):
        """84.852 km 是 US 1976 模型上限,T≈186.87,仍可计算。"""
        result = atmosphere_us_1976(84.852)
        assert result.T == pytest.approx(186.87, abs=0.5)


class TestAtmosphereLayerInterior:
    """每段内部"中点"温度,验证 lapse rate 应用正确。"""

    def test_h_5_5_km_troposphere_midpoint(self):
        """0-11 km 段 -6.5 K/km:h=5.5 时 T=288.15-6.5·5.5=252.40。"""
        result = atmosphere_us_1976(5.5)
        assert result.T == pytest.approx(252.40, abs=0.5)

    def test_h_15_km_tropopause_midpoint(self):
        """11-20 km 段等温:h=15 仍 T=216.65。"""
        result = atmosphere_us_1976(15.0)
        assert result.T == pytest.approx(216.65, abs=0.05)

    def test_h_26_km_strato_midpoint_plus_1_per_km(self):
        """20-32 km 段 +1 K/km:h=26 时 T=216.65+(26-20)=222.65。"""
        result = atmosphere_us_1976(26.0)
        assert result.T == pytest.approx(222.65, abs=0.05)

    def test_h_40_km_strato_midpoint_plus_2p8_per_km(self):
        """32-47 km 段 +2.8 K/km:h=40 时 T=228.65+2.8·(40-32)=251.05。"""
        result = atmosphere_us_1976(40.0)
        assert result.T == pytest.approx(251.05, abs=0.05)


# ============================================================================
# atmosphere_us_1976 — 错误边界
# ============================================================================

class TestAtmosphereBoundaries:
    """非法输入边界行为:不 ``sys.exit``,而是 ``ValueError``(库式)。"""

    def test_h_above_84p852_raises_value_error(self):
        """超出 US 1976 模型上限 → ValueError(不要像 reference 那样 sys.exit)。"""
        with pytest.raises(ValueError, match="84.852"):
            atmosphere_us_1976(85.0)

    def test_h_far_above_raises_value_error(self):
        with pytest.raises(ValueError):
            atmosphere_us_1976(200.0)

    def test_h_negative_raises_value_error(self):
        """海平面以下不支持(US 1976 模型本身从 0 起算)。"""
        with pytest.raises(ValueError):
            atmosphere_us_1976(-1.0)


# ============================================================================
# sutherland_mu — Sutherland 公式 μ(T)
# ============================================================================

class TestSutherlandMu:
    """Sutherland 公式 μ(T) = 1.458e-6 · T^1.5 / (T + 110.4) Pa·s。"""

    def test_standard_sea_level_temperature(self):
        """T=288.15 K → μ≈1.7894e-5 Pa·s(空气动力粘度标准海平面值)。"""
        mu = sutherland_mu(288.15)
        assert mu == pytest.approx(1.7894e-5, rel=0.01)

    def test_t_216p65_stratosphere(self):
        """T=216.65 K(对流层顶)→ μ≈1.4216e-5 Pa·s。"""
        mu = sutherland_mu(216.65)
        assert mu == pytest.approx(1.4216e-5, rel=0.01)

    def test_t_500_hot(self):
        """T=500 K(高速气流)→ μ 应当大于海平面值。"""
        mu_hot = sutherland_mu(500.0)
        mu_sl = sutherland_mu(288.15)
        assert mu_hot > mu_sl

    def test_t_100_cold(self):
        """T=100 K → μ 应当小于海平面值。"""
        mu_cold = sutherland_mu(100.0)
        mu_sl = sutherland_mu(288.15)
        assert mu_cold < mu_sl

    def test_t_zero_raises(self):
        """T=0 K 物理上无效。"""
        with pytest.raises((ValueError, ZeroDivisionError)):
            sutherland_mu(0.0)


# ============================================================================
# reynolds_number — Re = ρ·V/μ
# ============================================================================

class TestReynoldsNumber:
    """单位 Reynolds 数 Re/m = ρ·V/μ。"""

    def test_sea_level_M0p5(self):
        """海平面 Ma=0.5,V=170.15 m/s,Re/m ≈ 1.16e7。"""
        h_km = 0.0
        vel = 0.5 * 340.294  # M=0.5 at sea level
        p = 101325.0
        T = 288.15
        Re = reynolds_number(h_km, vel, p, T)
        # ρ = P/(R·T) = 101325/(287.0531·288.15) ≈ 1.225
        # μ(288.15) = 1.789e-5
        # Re = 1.225 * 170.15 / 1.789e-5 ≈ 1.165e7
        assert Re == pytest.approx(1.165e7, rel=0.02)

    def test_zero_velocity(self):
        """V=0 → Re=0。"""
        Re = reynolds_number(0.0, 0.0, 101325.0, 288.15)
        assert Re == 0.0

    def test_positive_velocity_positive_re(self):
        Re = reynolds_number(10.0, 100.0, 26500.0, 223.25)
        assert Re > 0.0


# ============================================================================
# 集成 sanity
# ============================================================================

class TestIntegrationSanity:
    """跨函数最小集成测试。"""

    def test_sea_level_full_stack_consistent(self):
        """海平面 ρ = P/(R·T) 应与 atmosphere_us_1976 输出一致(R=287.0531)。"""
        result = atmosphere_us_1976(0.0)
        R_specific = 287.0531
        rho_derived = result.P / (R_specific * result.T)
        assert result.rho == pytest.approx(rho_derived, rel=0.005)

    def test_sound_speed_matches_gamma_R_T(self):
        """声速 a = sqrt(γ·R·T) where γ=1.4, R=287.0531。"""
        result = atmosphere_us_1976(0.0)
        gamma = 1.4
        R_specific = 287.0531
        a_derived = math.sqrt(gamma * R_specific * result.T)
        assert result.a == pytest.approx(a_derived, rel=0.005)
