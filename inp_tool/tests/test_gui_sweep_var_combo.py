"""VarSpec 数据类测试 + enumerate_vars 枚举轴部分。"""
from inp_tool_gui.widgets.sweep_var_combo import VarSpec, enumerate_vars


def test_varspec_creation_minimal():
    """最小字段:key/label/kind 能创建。"""
    v = VarSpec(key="turbulence", label="turbulence (枚举)", kind="enum")
    assert v.key == "turbulence"
    assert v.label == "turbulence (枚举)"
    assert v.kind == "enum"
    assert v.enum_values is None
    assert v.block is None
    assert v.keyword is None
    assert v.value_idx is None


def test_varspec_creation_full():
    """全字段:普通 .inp 变量。"""
    v = VarSpec(
        key="physics.reynolds[0]",
        label="physics.reynolds[0] [float] = 1.0e6",
        kind="float",
        enum_values=None,
        block="physics",
        keyword="reynolds",
        value_idx=0,
    )
    assert v.block == "physics"
    assert v.keyword == "reynolds"
    assert v.value_idx == 0


def test_varspec_is_frozen():
    """frozen=True:不能修改字段。"""
    import dataclasses
    v = VarSpec(key="turbulence", label="turbulence", kind="enum")
    try:
        v.key = "other"
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("expected FrozenInstanceError")


def test_varspec_kind_literal_values():
    """kind 只接受 enum/int/float/str(本设计不暴露 bool)。"""
    for k in ("enum", "int", "float", "str"):
        v = VarSpec(key="x", label="x", kind=k)
        assert v.kind == k


def test_enumerate_vars_none_template_returns_enum_only():
    """无模板路径:返回 3 个枚举轴,无 .inp 变量。"""
    specs = enumerate_vars(None)
    assert len(specs) == 3
    keys = {s.key for s in specs}
    assert keys == {"turbulence", "energy", "gas"}
    for s in specs:
        assert s.kind == "enum"
        assert s.enum_values is not None
        assert len(s.enum_values) >= 2
        assert s.block is None
        assert s.keyword is None
        assert s.value_idx is None


def test_enumerate_vars_none_template_enum_values_match_sweep_module():
    """3 个枚举轴的 enum_values 来自 inp_tool.sweep 的 _ENUM_AXES。"""
    from inp_tool.sweep import (
        TurbulenceModel, EnergyModel, GasModel,
    )
    specs = enumerate_vars(None)
    by_key = {s.key: s for s in specs}
    assert set(by_key["turbulence"].enum_values) == {
        e.value for e in TurbulenceModel
    }
    assert set(by_key["energy"].enum_values) == {
        e.value for e in EnergyModel
    }
    assert set(by_key["gas"].enum_values) == {
        e.value for e in GasModel
    }


def test_enumerate_vars_none_template_is_pure():
    """enumerate_vars(None) 是纯函数,无副作用(可重复调用)。"""
    a = enumerate_vars(None)
    b = enumerate_vars(None)
    assert a == b
