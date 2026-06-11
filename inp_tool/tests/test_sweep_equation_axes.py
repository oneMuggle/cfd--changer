"""
v0.10.0:sweep 枚举轴识别 + per-case 覆盖 集成测试
"""
from __future__ import annotations
from pathlib import Path
import pytest
from inp_tool.sweep import (
    CaseSweep, SweepSpec, _normalize_axis_value,
    _ENUM_AXES,  # v0.10.0 新增导出
)
from inp_tool.equations import (
    TurbulenceModel, EnergyModel, GasModel,
)


class TestNormalizeAxisValue:
    def test_turbulence_str_mapped_to_enum(self):
        """turbulence: 'sst' → [TurbulenceModel.SST_KW]。"""
        result = _normalize_axis_value("turbulence", "sst")
        assert result == [TurbulenceModel.SST_KW]

    def test_turbulence_enum_passes_through(self):
        """turbulence: [TurbulenceModel.SST_KW] → [TurbulenceModel.SST_KW] (list 形式)。"""
        result = _normalize_axis_value("turbulence", [TurbulenceModel.SST_KW])
        assert result == [TurbulenceModel.SST_KW]

    def test_unknown_value_raises(self):
        """turbulence: 'foo' → ValueError。"""
        with pytest.raises(ValueError, match="unknown axis value 'foo'"):
            _normalize_axis_value("turbulence", "foo")

    def test_non_enum_key_passes_through(self):
        """alpha: 5 → [5] (老逻辑)。"""
        result = _normalize_axis_value("alpha", 5)
        assert result == [5]

    def test_unknown_str_for_non_enum_key_passes_through(self):
        """alpha: 'foo' → ['foo'](不视作枚举,保留字符串)。"""
        result = _normalize_axis_value("alpha", "foo")
        assert result == ["foo"]


class TestCartesianWithEnumAxes:
    def test_turbulence_axis_expands(self):
        """sweeps.turbulence=[sst, sa] × mach=[0.6, 0.8] → 4 cases。"""
        from inp_tool.sweep import expand_cartesian
        spec = SweepSpec(values={
            "mach": [0.6, 0.8],
            "turbulence": [TurbulenceModel.SST_KW, TurbulenceModel.SPALART_ALLMARAS],
        })
        cases = expand_cartesian(spec)
        assert len(cases) == 4
        turbs = {c["turbulence"] for c in cases}
        assert turbs == {TurbulenceModel.SST_KW, TurbulenceModel.SPALART_ALLMARAS}


class TestEnumAliasTable:
    """v0.10.0:Pin _ENUM_ALIASES 表面,防止未来 enum 扩展静默改语义。"""

    def test_turbulence_aliases_stable(self):
        from inp_tool.sweep import _ENUM_ALIASES
        expected = {"sst", "sa", "ke", "keps", "goldberg", "laminar"}
        assert set(_ENUM_ALIASES[TurbulenceModel].keys()) == expected

    def test_energy_aliases_stable(self):
        from inp_tool.sweep import _ENUM_ALIASES
        expected = {"2t", "3t", "none"}
        assert set(_ENUM_ALIASES[EnergyModel].keys()) == expected

    def test_gas_aliases_stable(self):
        from inp_tool.sweep import _ENUM_ALIASES
        expected = {"perfect", "real", "multi", "mixture"}
        assert set(_ENUM_ALIASES[GasModel].keys()) == expected


class TestEquationSwitches:
    def _cs(self, **kwargs) -> "CaseSweep":
        return CaseSweep(
            template="reference/inp_example/compare/可压缩理想气体+2方程SST mcfd.inp",
            output_dir="/tmp/cs_out",
            sweeps=SweepSpec(values=kwargs.pop("sweeps", {})),
            **{k: v for k, v in kwargs.items() if k != "sweeps"},
        )

    def test_default_all_true(self):
        """不传 equation_switches → 三个开关全 True。"""
        from inp_tool.sweep import EquationSwitches
        cs = self._cs()
        assert cs.equation_switches.turbulence is True
        assert cs.equation_switches.energy is True
        assert cs.equation_switches.gas is True

    def test_yaml_disable_turbulence(self):
        """from_dict: equation_switches.turbulence: false → 关。"""
        d = {
            "template": "reference/inp_example/compare/可压缩理想气体+2方程SST mcfd.inp",
            "output_dir": "/tmp/cs_out",
            "sweeps": {"turbulence": ["sst", "sa"]},
            "equation_switches": {"turbulence": False, "energy": True, "gas": True},
        }
        cs = CaseSweep.from_dict(d)
        assert cs.equation_switches.turbulence is False
        assert cs.equation_switches.energy is True
        assert cs.equation_switches.gas is True

    def test_yaml_partial(self):
        """只传 turbulence 开关 → 其他走默认 True。"""
        d = {
            "template": "reference/inp_example/compare/可压缩理想气体+2方程SST mcfd.inp",
            "output_dir": "/tmp/cs_out",
            "sweeps": {"turbulence": ["sst"]},
            "equation_switches": {"turbulence": False},
        }
        cs = CaseSweep.from_dict(d)
        assert cs.equation_switches.turbulence is False
        assert cs.equation_switches.energy is True
        assert cs.equation_switches.gas is True


class TestTurbInitOverride:
    def test_resolve_sst_override(self):
        """sst 模型用 overrides.sst 的 I/L/U_ref,不用顶层默认。"""
        from inp_tool.sweep import _resolve_turb_init, TurbulenceInit
        cs = CaseSweep(
            template="reference/inp_example/compare/可压缩理想气体+2方程SST mcfd.inp",
            output_dir="/tmp/cs_out",
            sweeps=SweepSpec(values={}),
            turbulence=None,  # 实际用 overrides
        )
        # 手动塞 overrides(模拟 from_dict 后的状态)
        cs.turbulence = TurbulenceInit(
            I=0.01, L=0.01, U_ref=204.0,
            overrides={
                "sst": TurbulenceInit(I=0.005, L=0.02, U_ref=250.0),
                "sa":  TurbulenceInit(I=0.03, L=0.005, U_ref=100.0),
            },
        )
        init = _resolve_turb_init(TurbulenceModel.SST_KW, cs)
        assert init.I == 0.005
        assert init.L == 0.02
        assert init.U_ref == 250.0

    def test_resolve_sa_uses_top_level_default(self):
        """sa 模型(无 overrides.sa)用顶层默认。"""
        from inp_tool.sweep import _resolve_turb_init, TurbulenceInit
        cs = CaseSweep(
            template="reference/inp_example/compare/可压缩理想气体+2方程SST mcfd.inp",
            output_dir="/tmp/cs_out",
            sweeps=SweepSpec(values={}),
        )
        cs.turbulence = TurbulenceInit(I=0.01, L=0.01, U_ref=204.0)
        init = _resolve_turb_init(TurbulenceModel.SPALART_ALLMARAS, cs)
        assert init.I == 0.01
        assert init.L == 0.01
        assert init.U_ref == 204.0

    def test_resolve_laminar_no_init(self):
        """LAMINAR 模型不需要 I/L/U,返回 None。"""
        from inp_tool.sweep import _resolve_turb_init
        cs = CaseSweep(
            template="reference/inp_example/compare/可压缩理想气体+2方程SST mcfd.inp",
            output_dir="/tmp/cs_out",
            sweeps=SweepSpec(values={}),
            turbulence=None,
        )
        init = _resolve_turb_init(TurbulenceModel.LAMINAR, cs)
        assert init is None


# ============================================================
# v0.10.0:generate() 末尾循环中切模型 + 动态 preset
# (Task 9)
# ============================================================
SST_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "compare"
    / "可压缩理想气体+2方程SST mcfd.inp"
)


class TestGenerateWithEquations:
    def test_sst_axis_switches_eqnset(self):
        """sweeps.turbulence=[sst, sa] → 2 cases,各自 eqnset_define v4/v5 不同。"""
        from inp_tool.sweep import generate, CaseSweep
        d = {
            "template": str(SST_FIXTURE),
            "output_dir": "/tmp/cs_out_gen1",
            "sweeps": {
                "turbulence": [TurbulenceModel.SST_KW, TurbulenceModel.SPALART_ALLMARAS],
            },
            "naming": "case_{turbulence}",
            "turbulence": {"I": 0.01, "L": 0.01, "U_ref": 204.0},
        }
        cs = CaseSweep.from_dict(d)
        rep = generate(cs, dry_run=True)
        assert rep.total == 2
        # 验每个 case_id 含正确模型名(默认 .inp 扩展)
        turbs = {c.case_id for c in rep.cases}
        assert "case_k-omega-sst.inp" in turbs
        assert "case_spalart-allmaras.inp" in turbs

    def test_equation_switches_turbulence_false_keeps_template(self):
        """equation_switches.turbulence=false → eqnset_define 不动。"""
        from inp_tool.sweep import generate, CaseSweep
        d = {
            "template": str(SST_FIXTURE),
            "output_dir": "/tmp/cs_out_gen2",
            "sweeps": {
                "turbulence": [TurbulenceModel.SST_KW, TurbulenceModel.SPALART_ALLMARAS],
            },
            "naming": "case_{turbulence}",
            "turbulence": {"I": 0.01, "L": 0.01, "U_ref": 204.0},
            "equation_switches": {"turbulence": False, "energy": True, "gas": True},
        }
        cs = CaseSweep.from_dict(d)
        rep = generate(cs, dry_run=True)
        for c in rep.cases:
            # 因 dry_run 没写盘,验 case.applied 不含 eqnset_define.v4_v5
            assert "eqnset_define.v4_v5" not in c.applied

    def test_energy_axis_two_temp_writes_numeqns(self):
        """sweeps.energy=[2t] → tnoneq_numeqns=1 + vibtem 写入。"""
        from inp_tool.sweep import generate, CaseSweep
        d = {
            "template": str(SST_FIXTURE),
            "output_dir": "/tmp/cs_out_gen3",
            "sweeps": {
                "energy": [EnergyModel.TWO_TEMP],
            },
            "naming": "case_{energy}",
            "energy_overrides": {
                "2T": {"T_trans": 300.0, "T_vib": 200.0},
            },
        }
        cs = CaseSweep.from_dict(d)
        rep = generate(cs, dry_run=True)
        for c in rep.cases:
            assert c.applied.get("physics.tnoneq_numeqns") == 1
            assert c.applied.get("physics.vibtem") == 200.0

    def test_unknown_axis_value_raises(self):
        """sweeps.turbulence=[sst, foo] → from_dict 抛 ValueError。"""
        from inp_tool.sweep import CaseSweep
        d = {
            "template": str(SST_FIXTURE),
            "output_dir": "/tmp/cs_out_gen4",
            "sweeps": {"turbulence": ["sst", "foo"]},
            "naming": "case_{turbulence}",
        }
        with pytest.raises(ValueError, match="unknown axis value 'foo'"):
            CaseSweep.from_dict(d)


class TestCliFlags:
    """v0.10.0:CLI 注册 4 个新 flag(--strict-equations + 3 个 --no-switch-*)。

    cli.py 实际用 argparse(不是 click),所以这里通过捕获 `sweep --help`
    的 stdout 来验 flag 已注册。等价于 click 的 `runner.invoke(cli, [...])`。
    """

    def _sweep_help_text(self) -> str:
        import io
        import contextlib
        from inp_tool.cli import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                main(["sweep", "--help"])
            except SystemExit:
                pass  # argparse 解析 --help 后正常 sys.exit
        return buf.getvalue()

    def test_strict_flag_passed_through(self):
        """--strict-equations 出现在 `sweep --help` 输出中。"""
        out = self._sweep_help_text()
        assert "--strict-equations" in out

    def test_no_switch_turbulence_flag(self):
        """--no-switch-turbulence 出现在 `sweep --help` 输出中。"""
        out = self._sweep_help_text()
        assert "--no-switch-turbulence" in out
