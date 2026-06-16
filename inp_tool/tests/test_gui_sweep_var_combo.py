"""VarSpec 数据类测试 + enumerate_vars 枚举轴部分。"""
import os

import pytest

from inp_tool_gui.widgets.sweep_var_combo import VarSpec, enumerate_vars


# 共享 fixture:examples/mcfd.inp 的绝对路径
EXAMPLES_INP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "examples", "mcfd.inp",
)


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


def test_enumerate_vars_invalid_path_returns_enum_only():
    """无效路径:返回仅枚举轴,不抛异常。"""
    specs = enumerate_vars("/不/存在/的/路径.inp")
    assert len(specs) == 3
    assert {s.key for s in specs} == {"turbulence", "energy", "gas"}


@pytest.mark.skipif(
    not os.path.exists(EXAMPLES_INP),
    reason="examples/mcfd.inp 不存在(此环境缺 fixture)",
)
def test_enumerate_vars_real_inp_contains_enum_and_inp_vars():
    """真实 .inp 解析:返回枚举轴 + .inp 变量,key 格式为 block.keyword[idx]。"""
    specs = enumerate_vars(EXAMPLES_INP)
    keys = {s.key for s in specs}
    # 枚举轴必须在前 3
    enum_keys = {s.key for s in specs if s.kind == "enum"}
    assert enum_keys == {"turbulence", "energy", "gas"}
    # .inp 变量 key 格式: block.keyword 或 block.keyword[idx]
    for s in specs:
        if s.kind == "enum":
            continue
        assert "." in s.key, "非枚举轴 key 缺 block 路径: {}".format(s.key)
        # label 含 [kind] 信息
        assert "[" in s.label and "]" in s.label
        # block / keyword / value_idx 三件套齐全
        assert s.block is not None
        assert s.keyword is not None
        assert s.value_idx is not None
        # kind ∈ {int, float, str}
        assert s.kind in ("int", "float", "str")


@pytest.mark.skipif(
    not os.path.exists(EXAMPLES_INP),
    reason="examples/mcfd.inp 不存在(此环境缺 fixture)",
)
def test_enumerate_vars_real_inp_label_includes_template_value():
    """label 含模板当前值,如 'physics.reynolds[0] [float] = 1.0e6'。"""
    specs = enumerate_vars(EXAMPLES_INP)
    # 找任一 float 变量验证
    float_vars = [s for s in specs if s.kind == "float"]
    if not float_vars:
        pytest.skip("examples/mcfd.inp 不含 float 变量")
    s = float_vars[0]
    # label 末尾是 " = <value>"
    assert " = " in s.label
    # 切开后,右边就是模板当前值的字符串
    _, _, raw = s.label.rpartition(" = ")
    assert raw  # 非空
    # raw 应该能 round-trip 到 s.kind 对应的类型
    if s.kind == "float":
        float(raw.replace("d", "e").replace("D", "E"))
    elif s.kind == "int":
        int(raw)


@pytest.mark.skipif(
    not os.path.exists(EXAMPLES_INP),
    reason="examples/mcfd.inp 不存在(此环境缺 fixture)",
)
def test_enumerate_vars_real_inp_inferred_kind_order():
    """kind 推断顺序:本设计不暴露 bool(走 str)。"""
    specs = enumerate_vars(EXAMPLES_INP)
    for s in specs:
        if s.kind == "enum":
            continue
        # 不会返回 "bool"
        assert s.kind in ("int", "float", "str")
