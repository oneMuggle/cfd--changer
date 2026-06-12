"""
v0.10.0+:EquationSystemReport.sweeps_equation_warnings 字段测试

Wizard step_4b/4c 在选 axis 后,把"sweeps 与 template 不兼容"的提示
存进 EquationSystemReport.sweeps_equation_warnings,供 step_4a_detect 消费。
"""
from __future__ import annotations
from inp_tool.equations import (
    EquationSystemReport, EnergyModel, TurbulenceModel, GasModel,
)


def _new_rep() -> EquationSystemReport:
    """构造最小有效 EquationSystemReport(3 个必要位置参数)。"""
    return EquationSystemReport(
        energy=EnergyModel.NONE,
        turbulence=TurbulenceModel.LAMINAR,
        gas=GasModel.PERFECT_GAS,
    )


class TestSweepsEquationWarningsField:
    """字段存在性 + 默认值。"""

    def test_field_exists(self):
        """EquationSystemReport 有 sweeps_equation_warnings 字段。"""
        rep = _new_rep()
        assert hasattr(rep, "sweeps_equation_warnings")

    def test_default_is_empty_list(self):
        """未传参 → 空 list(非 None,非 NoneType)。"""
        rep = _new_rep()
        assert rep.sweeps_equation_warnings == []
        assert isinstance(rep.sweeps_equation_warnings, list)

    def test_independent_per_instance(self):
        """default_factory=list → 每个实例独立(不共享可变默认)。"""
        a = _new_rep()
        b = _new_rep()
        a.sweeps_equation_warnings.append("foo")
        assert b.sweeps_equation_warnings == []

    def test_append_does_not_mutate_notes(self):
        """新字段独立于 notes,append 不影响 notes。"""
        rep = _new_rep()
        rep.sweeps_equation_warnings.append("axis clash")
        assert rep.notes == []
