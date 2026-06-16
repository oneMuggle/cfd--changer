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
