"""VarSpec 数据类测试。"""
from inp_tool_gui.widgets.sweep_var_combo import VarSpec


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
