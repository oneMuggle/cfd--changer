"""ConfigStore 模型层单测(纯 Python)。"""
import pytest


def test_axis_spec_enum_subset_creation():
    from inp_tool_gui.models.config_store import AxisSpec
    spec = AxisSpec(kind="enum_subset", values=("sst", "kw"))
    assert spec.kind == "enum_subset"
    assert spec.values == ("sst", "kw")


def test_axis_spec_is_frozen():
    from inp_tool_gui.models.config_store import AxisSpec
    spec = AxisSpec(kind="explicit_list", values=(1, 2, 3))
    with pytest.raises((AttributeError, Exception)):
        spec.kind = "range"


def test_axis_spec_range_form():
    from inp_tool_gui.models.config_store import AxisSpec
    spec = AxisSpec(kind="range", range_min=0.0, range_max=1.0, range_step=0.1)
    assert spec.range_min == 0.0
    assert spec.range_max == 1.0
    assert spec.range_step == 0.1