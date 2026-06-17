"""Sweep v2 condition 原语单测(纯 Python, 无 PySide2)。"""
import pytest

# 推迟到 Task 1.2 后再 from 真实符号
# from inp_tool.sweep import ConditionPredicate


def test_condition_predicate_str_op_int():
    """ConditionPredicate 持有 (key, op, value) 三元组。"""
    # 当模块未实现时这行会 ImportError,实现后应 pass
    from inp_tool.sweep import ConditionPredicate
    p = ConditionPredicate(key="mach", op="<", value=1)
    assert (p.key, p.op, p.value) == ("mach", "<", 1)


def test_condition_predicate_is_frozen():
    """ConditionPredicate 不可变。"""
    from inp_tool.sweep import ConditionPredicate
    p = ConditionPredicate(key="x", op="==", value=0)
    with pytest.raises((AttributeError, Exception)):
        p.key = "y"  # frozen dataclass 禁止赋值


def test_parse_condition_single_predicate():
    """parse_condition: {'mach': '<1'} → 1 个 predicate。"""
    from inp_tool.sweep import parse_condition, ConditionWhen, ConditionPredicate
    w = parse_condition({"mach": "<1"})
    assert isinstance(w, ConditionWhen)
    assert w.predicates == (ConditionPredicate("mach", "<", 1),)


def test_parse_condition_multiple_predicates():
    """多键 AND。"""
    from inp_tool.sweep import parse_condition, ConditionPredicate
    w = parse_condition({"mach": "<1", "reynolds": ">=1e6"})
    assert ConditionPredicate("mach", "<", 1) in w.predicates
    assert ConditionPredicate("reynolds", ">=", 1e6) in w.predicates
    assert len(w.predicates) == 2


def test_parse_condition_value_types():
    """value 类型按字面量推断(int/float/str/bool)。"""
    from inp_tool.sweep import parse_condition, ConditionPredicate
    w = parse_condition({"a": "==42", "b": "<3.14", "c": "!=foo", "d": "==true"})
    pred_map = {p.key: p for p in w.predicates}
    assert pred_map["a"].value == 42 and isinstance(pred_map["a"].value, int)
    assert pred_map["b"].value == 3.14 and isinstance(pred_map["b"].value, float)
    assert pred_map["c"].value == "foo" and isinstance(pred_map["c"].value, str)
    assert pred_map["d"].value is True


def test_parse_condition_unknown_op_raises():
    """未知 op 抛 ValueError。"""
    from inp_tool.sweep import parse_condition
    with pytest.raises(ValueError, match="unknown operator"):
        parse_condition({"x": "@@1"})


def test_evaluate_condition_true_when_empty():
    """空 predicates → 永真。"""
    from inp_tool.sweep import evaluate_condition, ConditionWhen
    assert evaluate_condition(ConditionWhen(), {"mach": 0.5}) is True


def test_evaluate_condition_and_semantics():
    """多 predicate 全部 AND。"""
    from inp_tool.sweep import parse_condition, evaluate_condition
    w = parse_condition({"mach": "<1", "reynolds": ">=1e6"})
    assert evaluate_condition(w, {"mach": 0.5, "reynolds": 2e6}) is True
    assert evaluate_condition(w, {"mach": 0.5, "reynolds": 5e5}) is False  # reynolds 不达标
    assert evaluate_condition(w, {"mach": 1.5, "reynolds": 2e6}) is False  # mach 不达标


def test_evaluate_condition_missing_key_returns_false():
    """case 缺 key → predicate 不成立。"""
    from inp_tool.sweep import parse_condition, evaluate_condition
    w = parse_condition({"mach": "<1"})
    assert evaluate_condition(w, {}) is False


def test_conditional_rule_dataclass():
    """ConditionalRule 持有 (when, then)。"""
    from inp_tool.sweep import (
        ConditionalRule, ConditionThen, parse_condition,
    )
    w = parse_condition({"mach": "<1"})
    t = ConditionThen(disable_axes=("turbulence",))
    rule = ConditionalRule(when=w, then=t)
    assert rule.then.disable_axes == ("turbulence",)


def test_expand_with_conditions_no_condition_returns_all():
    """无 conditions 时等价于笛卡尔积(全保留,无 extras)。"""
    from inp_tool.sweep import expand_with_conditions, SweepSpec, ConditionalRule
    spec = SweepSpec(values={"a": [1, 2], "b": [10, 20]})
    cases = expand_with_conditions(spec, conditions=())
    assert len(cases) == 4
    assert all(c.extras == () for c in cases)


def test_expand_with_conditions_filters_by_when():
    """first-match-wins:a=1 命中 rule,带 extras;a=2,3 不命中 → 保留但不带 extras。"""
    from inp_tool.sweep import (
        expand_with_conditions, SweepSpec, ConditionalRule,
        ConditionThen, parse_condition,
    )
    spec = SweepSpec(values={"a": [1, 2, 3]})
    rule = ConditionalRule(
        when=parse_condition({"a": "<2"}),
        then=ConditionThen(set_extra=(("flag", "yes"),)),
    )
    cases = expand_with_conditions(spec, conditions=(rule,))
    # a=1,2,3 全部保留(miss→keep)
    assert len(cases) == 3
    # a=1 命中 → 带 extras
    a1 = next(c for c in cases if c.values["a"] == 1)
    assert a1.extras == (("flag", "yes"),)
    # a=2,3 不命中 → 不带 extras,values 原样
    for v in (2, 3):
        c = next(c for c in cases if c.values["a"] == v)
        assert c.extras == ()
        assert c.values == {"a": v}


def test_expand_with_conditions_disable_axes_filters_value():
    """disable_axes:该 case 跳过该轴的值(从 case.values 删除)。"""
    from inp_tool.sweep import (
        expand_with_conditions, SweepSpec, ConditionalRule,
        ConditionThen, parse_condition,
    )
    spec = SweepSpec(values={"a": [1, 2], "b": [10, 20]})
    rule = ConditionalRule(
        when=parse_condition({"a": "<2"}),  # a=1 命中
        then=ConditionThen(disable_axes=("b",)),
    )
    cases = expand_with_conditions(spec, conditions=(rule,))
    # a=1 命中 → disable b → case.values 不含 b
    assert cases[0].values == {"a": 1}
    # a=2 不命中 → b 保留
    assert {"a": 2, "b": 10} in [c.values for c in cases]
    assert {"a": 2, "b": 20} in [c.values for c in cases]
