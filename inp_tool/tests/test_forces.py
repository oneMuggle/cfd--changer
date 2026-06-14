"""``inp_tool.postprocess.forces`` 单元测试。

测试覆盖:
- 6 个 dataclass 形状(RunParams / ForceSample / ForceSection /
  ReferenceGeometry / CoefficientRow / ForceReport)
- ``build_run_params(inp_path)`` 从 mcfd.inp 读 aero_* 字段
  - 走 ``guiopts`` block(reference/full_case/Case 实测)
  - intyp=3 时从 (u, v, w) 反推 alpha / beta(reference 行为)
  - Q = 0.5·ρ·V²,Re = ρ·V/μ,ρ = P/(R·T)
- ``shift_moment_to_ref`` 力矩中心从 (0,0,0) 平移到 (Xref,Yref,Zref)
- ``compute_coefficients`` 计算 CD/CY/CL/Cm/D/L/L_over_D/Xcp
- ``summarize_forces`` 高层 API:遍历 case 目录 → 末步 → 系数

参考实现:reference/code/CFDPlus_V4.py:838-976 + reference/code/CFDPlus_extract.py
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from inp_tool.postprocess.forces import (
    CoefficientRow,
    ForceReport,
    ForceSample,
    ForceSection,
    ReferenceGeometry,
    RunParams,
    build_run_params,
    compute_coefficients,
    shift_moment_to_ref,
    summarize_forces,
)

REFERENCE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures" / "reference" / "case"
)
REFERENCE_INP = REFERENCE_DIR / "mcfd.inp"


# ============================================================================
# Dataclass 形状校验
# ============================================================================

class TestDataclassShapes:
    def test_run_params_fields(self):
        p = RunParams(Ma=2.5, H=10.0, alpha=5.0, beta=1.0,
                      Q=50000.0, Re=1.0e7, P=20000.0, T=240.0, intyp=1)
        assert p.Ma == pytest.approx(2.5)
        assert p.H == pytest.approx(10.0)
        assert p.alpha == pytest.approx(5.0)
        assert p.beta == pytest.approx(1.0)
        assert p.Q == pytest.approx(50000.0)
        assert p.Re == pytest.approx(1.0e7)
        assert p.P == pytest.approx(20000.0)
        assert p.T == pytest.approx(240.0)
        assert p.intyp == 1

    def test_force_sample_fields(self):
        f = ForceSample(Fx=1.0, Fy=2.0, Fz=3.0, Mx=4.0, My=5.0, Mz=6.0)
        assert f.Fx == 1.0
        assert f.Mz == 6.0

    def test_force_section_fields(self):
        z = ForceSample(0, 0, 0, 0, 0, 0)
        s = ForceSection(total=z, inv=z, vis=z)
        assert s.total is z
        assert s.inv is z
        assert s.vis is z

    def test_reference_geometry_defaults(self):
        g = ReferenceGeometry(Sref=1.0, Lref=2.0)
        assert g.Xref == 0.0
        assert g.Yref == 0.0
        assert g.Zref == 0.0

    def test_reference_geometry_full(self):
        g = ReferenceGeometry(Sref=1.0, Lref=2.0, Xref=3.0, Yref=4.0, Zref=5.0)
        assert g.Sref == 1.0
        assert g.Xref == 3.0


# ============================================================================
# build_run_params — 从 mcfd.inp 读 aero_* 字段
# ============================================================================

class TestBuildRunParamsFromReference:
    """对照 reference/full_case/Case/mcfd.inp(intyp=3, Ma=9.887, u=1300)。"""

    def test_returns_run_params_dataclass(self):
        p = build_run_params(REFERENCE_INP)
        assert isinstance(p, RunParams)

    def test_aero_ma_value(self):
        p = build_run_params(REFERENCE_INP)
        assert p.Ma == pytest.approx(9.886999, rel=1e-6)

    def test_aero_altid_value(self):
        p = build_run_params(REFERENCE_INP)
        assert p.H == pytest.approx(30.0)

    def test_aero_intyp_value(self):
        p = build_run_params(REFERENCE_INP)
        assert p.intyp == 3

    def test_intyp_3_alpha_beta_derived_from_uvw(self):
        """intyp=3 + (u=1300, v=0, w=0) → α=0, β=0 (沿 x 轴)。"""
        p = build_run_params(REFERENCE_INP)
        assert p.alpha == pytest.approx(0.0, abs=1e-9)
        assert p.beta == pytest.approx(0.0, abs=1e-9)

    def test_pressure_and_temperature_values(self):
        p = build_run_params(REFERENCE_INP)
        assert p.P == pytest.approx(47.0)
        assert p.T == pytest.approx(43.0)

    def test_dynamic_pressure_consistent(self):
        """Q = 0.5·ρ·V² where ρ = P/(R·T), V = sqrt(u²+v²+w²)。

        reference inp: P=47, T=43, V=1300, R=287.0531 → ρ ≈ 0.003807,
        Q = 0.5·0.003807·1300² ≈ 3217 Pa
        """
        p = build_run_params(REFERENCE_INP)
        expected_Q = 0.5 * (47.0 / (287.0531 * 43.0)) * 1300.0 ** 2
        assert p.Q == pytest.approx(expected_Q, rel=0.01)

    def test_reynolds_per_meter_consistent(self):
        """Re/m = ρ·V/μ(T),μ 走 Sutherland。"""
        p = build_run_params(REFERENCE_INP)
        rho = 47.0 / (287.0531 * 43.0)
        mu = 1.458e-6 * 43.0 ** 1.5 / (43.0 + 110.4)
        expected_Re = rho * 1300.0 / mu
        assert p.Re == pytest.approx(expected_Re, rel=0.01)


class TestBuildRunParamsIntypNot3:
    """intyp != 3 时 alpha / beta 直接取 inp 中的值,不反推。"""

    def test_intyp_1_uses_inp_alpha_beta(self, tmp_path):
        inp_file = tmp_path / "mcfd.inp"
        inp_file.write_text(
            "guiopts begin\n"
            "aero_intyp 1\n"
            "aero_ma 0.8\n"
            "aero_altid 5.0\n"
            "aero_alpha 5.0\n"
            "aero_beta 2.0\n"
            "aero_pres 54000.0\n"
            "aero_temp 256.0\n"
            "aero_u 0.0\n"
            "aero_v 0.0\n"
            "aero_w 0.0\n"
            "aero_re 0.0\n"
            "guiopts end\n",
            encoding="utf-8",
        )
        p = build_run_params(inp_file)
        assert p.intyp == 1
        assert p.alpha == pytest.approx(5.0)
        assert p.beta == pytest.approx(2.0)

    def test_intyp_0_default(self, tmp_path):
        """缺 aero_intyp → 默认 0(reference 行为)。"""
        inp_file = tmp_path / "mcfd.inp"
        inp_file.write_text(
            "guiopts begin\n"
            "aero_ma 0.5\n"
            "aero_altid 0.0\n"
            "aero_alpha 3.0\n"
            "aero_beta 0.0\n"
            "aero_pres 101325.0\n"
            "aero_temp 288.15\n"
            "aero_u 0.0\n"
            "aero_v 0.0\n"
            "aero_w 0.0\n"
            "guiopts end\n",
            encoding="utf-8",
        )
        p = build_run_params(inp_file)
        assert p.intyp == 0
        assert p.alpha == pytest.approx(3.0)


class TestBuildRunParamsErrors:
    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            build_run_params(tmp_path / "missing.inp")


# ============================================================================
# shift_moment_to_ref — 力矩中心 (0,0,0) → (Xref,Yref,Zref)
# ============================================================================

class TestShiftMomentToRef:
    """``M_new = M_old + r × F`` (r=(Xref,Yref,Zref) - (0,0,0))。

    展开:
    - Mx_new = Mx + Zref·Fy − Yref·Fz
    - My_new = My + Xref·Fz − Zref·Fx
    - Mz_new = Mz + Yref·Fx − Xref·Fy
    """

    def test_zero_ref_unchanged(self):
        f = ForceSample(1, 2, 3, 4, 5, 6)
        g = ReferenceGeometry(Sref=1.0, Lref=1.0)
        result = shift_moment_to_ref(f, g)
        assert result.Mx == pytest.approx(4)
        assert result.My == pytest.approx(5)
        assert result.Mz == pytest.approx(6)

    def test_force_part_unchanged(self):
        f = ForceSample(1, 2, 3, 4, 5, 6)
        g = ReferenceGeometry(Sref=1.0, Lref=1.0, Xref=10.0, Yref=20.0, Zref=30.0)
        result = shift_moment_to_ref(f, g)
        assert result.Fx == pytest.approx(1)
        assert result.Fy == pytest.approx(2)
        assert result.Fz == pytest.approx(3)

    def test_pure_xref_only_my_mz_changed(self):
        f = ForceSample(Fx=1, Fy=2, Fz=3, Mx=0, My=0, Mz=0)
        g = ReferenceGeometry(Sref=1, Lref=1, Xref=10.0)
        result = shift_moment_to_ref(f, g)
        # Mx_new = 0 + 0·Fy - 0·Fz = 0
        # My_new = 0 + 10·Fz - 0·Fx = 30
        # Mz_new = 0 + 0·Fx - 10·Fy = -20
        assert result.Mx == pytest.approx(0)
        assert result.My == pytest.approx(30)
        assert result.Mz == pytest.approx(-20)

    def test_pure_zref_only_mx_my_changed(self):
        f = ForceSample(Fx=1, Fy=2, Fz=3, Mx=0, My=0, Mz=0)
        g = ReferenceGeometry(Sref=1, Lref=1, Zref=5.0)
        result = shift_moment_to_ref(f, g)
        # Mx_new = 0 + 5·2 - 0·3 = 10
        # My_new = 0 + 0·3 - 5·1 = -5
        # Mz_new = 0 + 0·1 - 0·2 = 0
        assert result.Mx == pytest.approx(10)
        assert result.My == pytest.approx(-5)
        assert result.Mz == pytest.approx(0)

    def test_full_ref_all_three_moments_change(self):
        f = ForceSample(Fx=2.0, Fy=3.0, Fz=5.0, Mx=10.0, My=20.0, Mz=30.0)
        g = ReferenceGeometry(Sref=1, Lref=1, Xref=1.0, Yref=2.0, Zref=4.0)
        result = shift_moment_to_ref(f, g)
        # Mx_new = 10 + 4·3 - 2·5 = 10 + 12 - 10 = 12
        # My_new = 20 + 1·5 - 4·2 = 20 + 5 - 8 = 17
        # Mz_new = 30 + 2·2 - 1·3 = 30 + 4 - 3 = 31
        assert result.Mx == pytest.approx(12)
        assert result.My == pytest.approx(17)
        assert result.Mz == pytest.approx(31)


# ============================================================================
# compute_coefficients — CD/CY/CL/Cm/D/L/L_over_D/Xcp
# ============================================================================

class TestComputeCoefficientsBasic:
    """基础公式校验。"""

    def test_zero_alpha_drag_equals_fx(self):
        """α=0 → D = Fx·1 + Fz·0 = Fx。"""
        force = ForceSample(Fx=1000.0, Fy=0.0, Fz=200.0, Mx=0, My=0, Mz=0)
        params = RunParams(Ma=0.5, H=0, alpha=0.0, beta=0.0,
                           Q=50000.0, Re=1e7, P=101325.0, T=288.15, intyp=0)
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        row = compute_coefficients(force, params, geom, case_name="test")
        assert row.D == pytest.approx(1000.0)
        assert row.L == pytest.approx(200.0)

    def test_45_deg_alpha_drag_lift(self):
        """α=45°,Fx=Fz=1 → D = √2,L = 0。"""
        force = ForceSample(Fx=1.0, Fy=0.0, Fz=1.0, Mx=0, My=0, Mz=0)
        params = RunParams(Ma=0.5, H=0, alpha=45.0, beta=0.0,
                           Q=1.0, Re=1e7, P=101325.0, T=288.15, intyp=0)
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        row = compute_coefficients(force, params, geom, case_name="t")
        assert row.D == pytest.approx(math.sqrt(2.0), rel=1e-9)
        assert row.L == pytest.approx(0.0, abs=1e-9)

    def test_cd_cy_cl_division(self):
        Q = 100.0
        Sref = 2.0
        force = ForceSample(Fx=200.0, Fy=400.0, Fz=600.0, Mx=0, My=0, Mz=0)
        params = RunParams(Ma=0.5, H=0, alpha=0.0, beta=0.0,
                           Q=Q, Re=1e7, P=101325.0, T=288.15, intyp=0)
        geom = ReferenceGeometry(Sref=Sref, Lref=1.0)
        row = compute_coefficients(force, params, geom, case_name="t")
        assert row.CD == pytest.approx(200.0 / (Q * Sref))
        assert row.CY == pytest.approx(400.0 / (Q * Sref))
        assert row.CL == pytest.approx(600.0 / (Q * Sref))

    def test_cm_division(self):
        Q = 100.0
        Sref = 2.0
        Lref = 3.0
        force = ForceSample(Fx=0, Fy=0, Fz=0, Mx=10.0, My=20.0, Mz=30.0)
        params = RunParams(Ma=0.5, H=0, alpha=0.0, beta=0.0,
                           Q=Q, Re=1e7, P=101325.0, T=288.15, intyp=0)
        geom = ReferenceGeometry(Sref=Sref, Lref=Lref)
        row = compute_coefficients(force, params, geom, case_name="t")
        assert row.Cmx == pytest.approx(10.0 / (Q * Sref * Lref))
        assert row.Cmy == pytest.approx(20.0 / (Q * Sref * Lref))
        assert row.Cmz == pytest.approx(30.0 / (Q * Sref * Lref))


class TestComputeCoefficientsEdgeCases:
    """除零保护。"""

    def test_zero_Q_returns_zero_coefficients(self):
        force = ForceSample(Fx=100, Fy=200, Fz=300, Mx=0, My=0, Mz=0)
        params = RunParams(Ma=0.5, H=0, alpha=0.0, beta=0.0,
                           Q=0.0, Re=1e7, P=0.0, T=288.15, intyp=0)
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        row = compute_coefficients(force, params, geom, case_name="t")
        assert row.CD == 0.0
        assert row.CY == 0.0
        assert row.CL == 0.0
        assert row.Cmx == 0.0
        assert row.Cmy == 0.0
        assert row.Cmz == 0.0

    def test_zero_Fz_xcp_zero(self):
        force = ForceSample(Fx=100, Fy=0, Fz=0, Mx=0, My=50, Mz=0)
        params = RunParams(Ma=0.5, H=0, alpha=0.0, beta=0.0,
                           Q=100.0, Re=1e7, P=0.0, T=288.15, intyp=0)
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        row = compute_coefficients(force, params, geom, case_name="t")
        assert row.Xcp == 0.0

    def test_zero_D_lift_drag_ratio_zero(self):
        force = ForceSample(Fx=0, Fy=0, Fz=0, Mx=0, My=0, Mz=0)
        params = RunParams(Ma=0.5, H=0, alpha=0.0, beta=0.0,
                           Q=100.0, Re=1e7, P=0.0, T=288.15, intyp=0)
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        row = compute_coefficients(force, params, geom, case_name="t")
        assert row.L_over_D == 0.0

    def test_xcp_formula(self):
        """Xcp = Xref - My_shifted / Fz(在 |Fz| > 1e-10 时)。

        注意:My_shifted 是平移后的力矩,即
            My_new = My_raw + Xref·Fz - Zref·Fx
        所以本例:My_raw=20, Xref=5, Fz=10, Fx=0, Zref=0
            My_new = 20 + 5·10 - 0·0 = 70
            Xcp = 5 - 70/10 = -2
        """
        force = ForceSample(Fx=0, Fy=0, Fz=10.0, Mx=0, My=20.0, Mz=0)
        params = RunParams(Ma=0.5, H=0, alpha=0.0, beta=0.0,
                           Q=100.0, Re=1e7, P=0.0, T=288.15, intyp=0)
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0, Xref=5.0)
        row = compute_coefficients(force, params, geom, case_name="t")
        assert row.Xcp == pytest.approx(-2.0)

    def test_xcp_formula_no_shift(self):
        """ref=(0,0,0) 时不平移,Xcp = 0 - My/Fz = -My/Fz。"""
        force = ForceSample(Fx=0, Fy=0, Fz=10.0, Mx=0, My=20.0, Mz=0)
        params = RunParams(Ma=0.5, H=0, alpha=0.0, beta=0.0,
                           Q=100.0, Re=1e7, P=0.0, T=288.15, intyp=0)
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)  # Xref=0
        row = compute_coefficients(force, params, geom, case_name="t")
        # Xcp = 0 - 20/10 = -2
        assert row.Xcp == pytest.approx(-2.0)


class TestComputeCoefficientsXcg:
    def test_xcg_default(self):
        force = ForceSample(Fx=0, Fy=0, Fz=0, Mx=0, My=0, Mz=0)
        params = RunParams(Ma=0.5, H=0, alpha=0.0, beta=0.0,
                           Q=100.0, Re=1e7, P=0.0, T=288.15, intyp=0)
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        row = compute_coefficients(force, params, geom, case_name="t")
        assert row.Xcg == 0.0

    def test_xcg_set(self):
        force = ForceSample(Fx=0, Fy=0, Fz=0, Mx=0, My=0, Mz=0)
        params = RunParams(Ma=0.5, H=0, alpha=0.0, beta=0.0,
                           Q=100.0, Re=1e7, P=0.0, T=288.15, intyp=0)
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        row = compute_coefficients(force, params, geom, case_name="t", xcg=2.5)
        assert row.Xcg == pytest.approx(2.5)


# ============================================================================
# summarize_forces — 高层 API
# ============================================================================

class TestSummarizeForces:
    """端到端集成测试。"""

    def test_returns_force_report(self):
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        report = summarize_forces([REFERENCE_DIR], op_ibd=[1], ref_geom=geom)
        assert isinstance(report, ForceReport)

    def test_report_has_one_row(self):
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        report = summarize_forces([REFERENCE_DIR], op_ibd=[1], ref_geom=geom)
        assert len(report.rows) == 1

    def test_row_case_name_is_dir_basename(self):
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        report = summarize_forces([REFERENCE_DIR], op_ibd=[1], ref_geom=geom)
        assert report.rows[0].case == "case"

    def test_row_ma_matches_inp(self):
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        report = summarize_forces([REFERENCE_DIR], op_ibd=[1], ref_geom=geom)
        assert report.rows[0].Ma == pytest.approx(9.886999, rel=1e-6)

    def test_report_rows_non_empty_forces(self):
        """reference 算例数据非零,所以 row.Fx 应该非零。"""
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        report = summarize_forces([REFERENCE_DIR], op_ibd=[1], ref_geom=geom)
        assert abs(report.rows[0].Fx) > 1e5

    def test_missing_info1_skipped(self, tmp_path):
        bad_case = tmp_path / "bad_case"
        bad_case.mkdir()
        (bad_case / "mcfd.inp").write_text(
            "guiopts begin\naero_intyp 0\naero_ma 0.5\naero_altid 0\n"
            "aero_alpha 0\naero_beta 0\naero_pres 101325\naero_temp 288.15\n"
            "aero_u 0\naero_v 0\naero_w 0\nguiopts end\n",
            encoding="utf-8",
        )
        geom = ReferenceGeometry(Sref=1.0, Lref=1.0)
        report = summarize_forces([bad_case], op_ibd=[1], ref_geom=geom)
        assert len(report.rows) == 0


# ============================================================================
# ForceReport dataclass
# ============================================================================

class TestForceReport:
    def test_empty_report(self):
        report = ForceReport(rows=[])
        assert report.rows == []

    def test_report_with_one_row(self):
        row = CoefficientRow(
            case="Case_01",
            Ma=0.5, H=0.0, alpha_deg=0.0, beta_deg=0.0,
            Fx=1.0, Fy=2.0, Fz=3.0, Mx=4.0, My=5.0, Mz=6.0,
            D=1.0, L=3.0,
            CD=0.1, CY=0.2, CL=0.3,
            Cmx=0.01, Cmy=0.02, Cmz=0.03,
            L_over_D=3.0, Xcp=0.0, Xcg=0.0,
            Sref=1.0, Lref=1.0, Q=10.0, Re=1e6, P=101325.0, T=288.15,
        )
        report = ForceReport(rows=[row])
        assert report.rows[0].case == "Case_01"
        assert report.rows[0].CD == pytest.approx(0.1)
