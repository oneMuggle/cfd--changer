"""
mcfd.inp sweep 批量算例生成器 — Phase 1 RED

测试目标:
- SweepSpec: 笛卡尔积展开
- FreestreamPreset: alpha/beta/Ma → aero_u/v/w 几何分解 + refvel
- 命名模板: Python str.format(**params) 风格
- CaseResult / SweepReport 数据结构
"""
from __future__ import annotations
import math
import pytest

from inp_tool.sweep import (
    SweepSpec,
    expand_cartesian,
    FreestreamPreset,
    render_case_name,
    CaseResult,
    SweepReport,
)


# ======================================================================
# SweepSpec / 笛卡尔积展开
# ======================================================================
class TestSweepSpecCartesian:
    def test_single_axis_two_values_yields_two_cases(self):
        spec = SweepSpec(values={"alpha": [0, 4]})
        cases = expand_cartesian(spec)
        assert cases == [{"alpha": 0}, {"alpha": 4}]

    def test_two_axes_yields_cartesian_product(self):
        spec = SweepSpec(values={"alpha": [0, 4], "beta": [-2, 0, 2]})
        cases = expand_cartesian(spec)
        assert len(cases) == 6
        # 检查所有组合都出现
        keys = {(c["alpha"], c["beta"]) for c in cases}
        assert keys == {(0, -2), (0, 0), (0, 2), (4, -2), (4, 0), (4, 2)}

    def test_three_axes_yields_full_product(self):
        spec = SweepSpec(values={"alpha": [0, 2, 4], "beta": [0], "mach": [0.6, 0.8]})
        cases = expand_cartesian(spec)
        assert len(cases) == 6  # 3 * 1 * 2

    def test_scalar_value_treated_as_single_element_list(self):
        # 用户可能写 "mach: 0.6" 而非 "mach: [0.6]"
        spec = SweepSpec(values={"mach": 0.6})
        cases = expand_cartesian(spec)
        assert cases == [{"mach": 0.6}]

    def test_empty_sweep_raises(self):
        spec = SweepSpec(values={})
        with pytest.raises(ValueError, match="at least one sweep axis"):
            expand_cartesian(spec)

    def test_empty_axis_list_raises(self):
        spec = SweepSpec(values={"alpha": []})
        with pytest.raises(ValueError, match="empty list"):
            expand_cartesian(spec)


# ======================================================================
# FreestreamPreset 公式
# ======================================================================
class TestFreestreamPreset:
    """几何分解:
       a = sqrt(gamma * R * T_inf)
       U = Ma * a * cos(alpha) * cos(beta)
       V = Ma * a * sin(beta)
       W = Ma * a * sin(alpha) * cos(beta)
       refvel = sqrt(U^2 + V^2 + W^2) = Ma * a (模长守恒)
    """

    def test_zero_alpha_beta_gives_pure_x_velocity(self):
        # Ma=0.8, alpha=0, beta=0, T=300K, gamma=1.4, R=287.05
        # a = sqrt(1.4 * 287.05 * 300) ≈ 347.22 m/s
        # U = 0.8 * 347.22 ≈ 277.78
        preset = FreestreamPreset(gamma=1.4, R=287.05)
        params = {"alpha": 0.0, "beta": 0.0, "mach": 0.8, "T_inf": 300.0}
        uvw = preset.compute_uvw(params)
        assert math.isclose(uvw["U"], 277.78, rel_tol=1e-3)
        assert math.isclose(uvw["V"], 0.0, abs_tol=1e-6)
        assert math.isclose(uvw["W"], 0.0, abs_tol=1e-6)

    def test_pure_alpha_2deg_gives_u_and_w_no_v(self):
        # alpha=2deg, beta=0
        # W = Ma*a*sin(2°), U = Ma*a*cos(2°), V = 0
        preset = FreestreamPreset(gamma=1.4, R=287.05)
        params = {"alpha": 2.0, "beta": 0.0, "mach": 0.8, "T_inf": 300.0}
        uvw = preset.compute_uvw(params)
        a = math.sqrt(1.4 * 287.05 * 300.0)
        expected_U = 0.8 * a * math.cos(math.radians(2.0))
        expected_W = 0.8 * a * math.sin(math.radians(2.0))
        assert math.isclose(uvw["U"], expected_U, rel_tol=1e-9)
        assert math.isclose(uvw["V"], 0.0, abs_tol=1e-9)
        assert math.isclose(uvw["W"], expected_W, rel_tol=1e-9)

    def test_pure_beta_3deg_gives_u_and_v_no_w(self):
        preset = FreestreamPreset(gamma=1.4, R=287.05)
        params = {"alpha": 0.0, "beta": 3.0, "mach": 0.6, "T_inf": 288.15}
        uvw = preset.compute_uvw(params)
        a = math.sqrt(1.4 * 287.05 * 288.15)
        expected_U = 0.6 * a * math.cos(math.radians(3.0)) * math.cos(0.0)
        expected_V = 0.6 * a * math.sin(math.radians(3.0))
        assert math.isclose(uvw["U"], expected_U, rel_tol=1e-9)
        assert math.isclose(uvw["V"], expected_V, rel_tol=1e-9)
        assert math.isclose(uvw["W"], 0.0, abs_tol=1e-9)

    def test_refvel_is_mach_times_speed_of_sound(self):
        # 不论 alpha/beta 怎么转,refvel = sqrt(U^2+V^2+W^2) = Ma*a
        preset = FreestreamPreset(gamma=1.4, R=287.05)
        for alpha, beta in [(0, 0), (5, 3), (10, -4), (-2, 2)]:
            params = {"alpha": alpha, "beta": beta, "mach": 0.7, "T_inf": 300.0}
            uvw = preset.compute_uvw(params)
            a = math.sqrt(1.4 * 287.05 * 300.0)
            refvel = math.sqrt(uvw["U"] ** 2 + uvw["V"] ** 2 + uvw["W"] ** 2)
            assert math.isclose(refvel, 0.7 * a, rel_tol=1e-9), (
                f"alpha={alpha} beta={beta}"
            )

    def test_speed_of_sound_explicit_overrides_computation(self):
        preset = FreestreamPreset(gamma=1.4, R=287.05, speed_of_sound=340.0)
        params = {"alpha": 0.0, "beta": 0.0, "mach": 1.0, "T_inf": 300.0}
        uvw = preset.compute_uvw(params)
        assert math.isclose(uvw["U"], 340.0, rel_tol=1e-9)

    def test_apply_to_inp_writes_aero_u_v_w(self, tmp_path):
        """apply() 实际写入 InpFile 的 guiopts 块"""
        from inp_tool import parse_file, write
        sample = tmp_path / "template.inp"
        sample.write_text(
            "guiopts begin\n"
            "aero_alpha 0.0\n"
            "aero_beta 0.0\n"
            "aero_ma 0.0\n"
            "aero_u 0.0\n"
            "aero_v 0.0\n"
            "aero_w 0.0\n"
            "guiopts end\n"
        )
        inp = parse_file(str(sample))
        preset = FreestreamPreset(gamma=1.4, R=287.05)
        params = {"alpha": 4.0, "beta": 2.0, "mach": 0.85, "T_inf": 300.0}
        preset.apply(inp, params)
        assert inp.get("guiopts", "aero_alpha") == 4.0
        assert inp.get("guiopts", "aero_beta") == 2.0
        assert inp.get("guiopts", "aero_ma") == 0.85
        # 验证 aero_u/v/w 是被分解出来的(非零)
        assert abs(inp.get("guiopts", "aero_u")) > 1.0
        assert abs(inp.get("guiopts", "aero_v")) > 0.01
        assert abs(inp.get("guiopts", "aero_w")) > 1.0

    def test_apply_updates_physics_refvel_and_reftem(self, tmp_path):
        from inp_tool import parse_file
        sample = tmp_path / "template.inp"
        sample.write_text(
            "physics begin\n"
            "refvel 0.0\n"
            "reftem 288.15\n"
            "refpre 101325.0\n"
            "physics end\n"
        )
        inp = parse_file(str(sample))
        preset = FreestreamPreset(gamma=1.4, R=287.05)
        params = {"alpha": 0.0, "beta": 0.0, "mach": 0.8, "T_inf": 300.0, "p_inf": 101325.0}
        preset.apply(inp, params)
        # refvel = Ma * a = 0.8 * 347.22 ≈ 277.78
        assert math.isclose(inp.get("physics", "refvel"), 277.78, rel_tol=1e-3)
        assert inp.get("physics", "reftem") == 300.0
        assert inp.get("physics", "refpre") == 101325.0

    def test_apply_warns_when_guiopts_block_missing(self, tmp_path, capsys):
        from inp_tool import parse_file
        sample = tmp_path / "no_guiopts.inp"
        sample.write_text("physics begin\nrefvel 0.0\nphysics end\n")
        inp = parse_file(str(sample))
        preset = FreestreamPreset(gamma=1.4, R=287.05)
        params = {"alpha": 0.0, "beta": 0.0, "mach": 0.8, "T_inf": 300.0}
        # 不应抛异常,只是 warn
        preset.apply(inp, params)
        captured = capsys.readouterr()
        # 警告消息写到 stderr
        assert "guiopts" in captured.err.lower() or "warn" in captured.err.lower()


# ======================================================================
# 命名模板
# ======================================================================
class TestRenderCaseName:
    def test_simple_format(self):
        name = render_case_name("case_aoa{alpha:.0f}_b{beta:.0f}", {"alpha": 4, "beta": 0})
        assert name == "case_aoa4_b0"

    def test_format_with_sign(self):
        name = render_case_name("b{beta:+03d}", {"beta": -4})
        assert name == "b-04"

    def test_missing_placeholder_raises(self):
        with pytest.raises(KeyError):
            render_case_name("case_{alpha}_{beta}", {"alpha": 0})

    def test_extra_params_ignored(self):
        # 多余参数不报错(允许用户在配置里写其他字段)
        name = render_case_name("a{alpha}", {"alpha": 2, "beta": 0, "mach": 0.6})
        assert name == "a2"

    def test_appends_inp_extension(self):
        name = render_case_name(
            "case_{alpha}", {"alpha": 0}, ext=".inp"
        )
        assert name == "case_0.inp"


# ======================================================================
# CaseResult / SweepReport
# ======================================================================
class TestCaseResult:
    def test_construct_minimal(self):
        r = CaseResult(case_id="c1", path="/tmp/c1.inp", params={"alpha": 0})
        assert r.case_id == "c1"
        assert r.path == "/tmp/c1.inp"
        assert r.params == {"alpha": 0}
        assert r.applied == {}  # 默认空

    def test_to_dict_round_trip(self):
        r = CaseResult(
            case_id="c1",
            path="/tmp/c1.inp",
            params={"alpha": 4, "beta": 0},
            applied={"guiopts.aero_alpha": 4.0},
        )
        d = r.to_dict()
        assert d["case_id"] == "c1"
        assert d["params"] == {"alpha": 4, "beta": 0}
        assert d["applied"]["guiopts.aero_alpha"] == 4.0


class TestSweepReport:
    def test_construct_and_iter(self):
        cases = [
            CaseResult(case_id="c1", path="/tmp/c1.inp", params={"alpha": 0}),
            CaseResult(case_id="c2", path="/tmp/c2.inp", params={"alpha": 4}),
        ]
        report = SweepReport(template="/tmp/t.inp", cases=cases)
        assert report.total == 2
        ids = [r.case_id for r in report]
        assert ids == ["c1", "c2"]
