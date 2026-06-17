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


def test_config_store_minimal_creation():
    from inp_tool_gui.models.config_store import ConfigStore
    s = ConfigStore(
        template="/t.inp",
        output_dir="/out",
        naming="case",
        preset_ref=None,
        sweeps={},
        conditions=(),
    )
    assert s.template == "/t.inp"
    assert s.case_count == 0


def test_config_store_is_frozen():
    from inp_tool_gui.models.config_store import ConfigStore
    s = ConfigStore(template="t", output_dir="o", naming="case",
                     preset_ref=None, sweeps={}, conditions=())
    with pytest.raises((AttributeError, Exception)):
        s.template = "other"


def test_config_store_replace_returns_new_instance():
    """replace 不可变:返回新 ConfigStore,原实例不变。"""
    from inp_tool_gui.models.config_store import ConfigStore, AxisSpec
    s1 = ConfigStore(template="t1", output_dir="o", naming="case",
                     preset_ref=None, sweeps={}, conditions=())
    s2 = s1.replace(template="t2")
    assert s1.template == "t1"  # 原不变
    assert s2.template == "t2"  # 新实例
    assert s1 is not s2


def test_config_store_replace_with_sweep():
    from inp_tool_gui.models.config_store import ConfigStore, AxisSpec
    s1 = ConfigStore(template="t", output_dir="o", naming="case",
                     preset_ref=None, sweeps={}, conditions=())
    s2 = s1.replace_sweep("mach", AxisSpec(kind="range", range_min=0, range_max=2, range_step=1))
    assert "mach" in s2.sweeps
    assert "mach" not in s1.sweeps  # 不可变