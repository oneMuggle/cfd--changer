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
