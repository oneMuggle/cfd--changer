"""
v0.10.0:sweep 枚举轴识别 + per-case 覆盖 集成测试
"""
from __future__ import annotations
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
