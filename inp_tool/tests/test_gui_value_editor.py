"""ValueEditorDialog 单元测试(Phase 3)。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless。

测试覆盖:
- 构造后 line edit 含旧值
- accept 后 :attr:`new_value` 是按当前 typed 类型推断后的新值
- reject 后 :attr:`new_value` 为 None
- 类型校验:接受 int/float/str/bool 输入
"""
import os

# 在 import Qt 之前设 offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide2.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# --- 基础构造 ----------------------------------------------------------


def test_dialog_starts_with_current_raw(qapp):
    """构造时 line edit 文本 = 传入的 raw。"""
    from inp_tool_gui.widgets.value_editor import ValueEditorDialog

    dlg = ValueEditorDialog(current_raw="300.0", current_typed=300.0)
    try:
        assert dlg.findChild_text() == "300.0"
    finally:
        dlg.deleteLater()


def test_dialog_type_label_shows_inferred_type(qapp):
    """类型标签显示按 typed 推断的类型(int/float/str/bool)。"""
    from inp_tool_gui.widgets.value_editor import ValueEditorDialog

    for typed, label in [
        (300, "int"),
        (300.0, "float"),
        ("hello", "str"),
        (True, "bool"),
    ]:
        dlg = ValueEditorDialog(current_raw=str(typed), current_typed=typed)
        try:
            assert dlg.type_label() == label
        finally:
            dlg.deleteLater()


# --- accept / reject ----------------------------------------------------


def test_accept_returns_typed_value(qapp):
    """accept 后 new_value 是按 typed 类型推断的新值。"""
    from inp_tool_gui.widgets.value_editor import ValueEditorDialog

    dlg = ValueEditorDialog(current_raw="300.0", current_typed=300.0)
    try:
        dlg.set_text("450.5")
        dlg.accept()
        assert dlg.new_value == 450.5
        assert isinstance(dlg.new_value, float)
    finally:
        dlg.deleteLater()


def test_accept_int_input_returns_int(qapp):
    """raw=300 (int typed),改文本 450 → accept 后 new_value 是 int 450。"""
    from inp_tool_gui.widgets.value_editor import ValueEditorDialog

    dlg = ValueEditorDialog(current_raw="300", current_typed=300)
    try:
        dlg.set_text("450")
        dlg.accept()
        assert dlg.new_value == 450
        assert isinstance(dlg.new_value, int)
    finally:
        dlg.deleteLater()


def test_accept_string_input_returns_str(qapp):
    """raw='hello' (str typed),改文本 'world' → accept 后 new_value 是 str。"""
    from inp_tool_gui.widgets.value_editor import ValueEditorDialog

    dlg = ValueEditorDialog(current_raw="hello", current_typed="hello")
    try:
        dlg.set_text("world")
        dlg.accept()
        assert dlg.new_value == "world"
    finally:
        dlg.deleteLater()


def test_accept_bool_input_returns_bool(qapp):
    """raw='T' (bool typed),改文本 'F' → accept 后 new_value 是 False。"""
    from inp_tool_gui.widgets.value_editor import ValueEditorDialog

    dlg = ValueEditorDialog(current_raw="T", current_typed=True)
    try:
        dlg.set_text("F")
        dlg.accept()
        assert dlg.new_value is False
    finally:
        dlg.deleteLater()


def test_reject_returns_none(qapp):
    """reject 后 new_value 为 None。"""
    from inp_tool_gui.widgets.value_editor import ValueEditorDialog

    dlg = ValueEditorDialog(current_raw="300.0", current_typed=300.0)
    try:
        dlg.set_text("999")
        dlg.reject()
        assert dlg.new_value is None
    finally:
        dlg.deleteLater()


def test_accept_invalid_int_keeps_old(qapp):
    """int 类型时输入非数字 → accept 不通过,new_value 仍为旧值。"""
    from inp_tool_gui.widgets.value_editor import ValueEditorDialog

    dlg = ValueEditorDialog(current_raw="300", current_typed=300)
    try:
        dlg.set_text("not_a_number")
        dlg.accept()  # 校验失败,应保持 dialog 不被关
        # dialog 仍在或 result 未 accepted
        assert not dlg.result_accepted()
        # 不更新 new_value
        assert dlg.new_value is None
    finally:
        dlg.deleteLater()


def test_accept_empty_int_rejected(qapp):
    """int 类型时输入空串 → 拒绝。"""
    from inp_tool_gui.widgets.value_editor import ValueEditorDialog

    dlg = ValueEditorDialog(current_raw="300", current_typed=300)
    try:
        dlg.set_text("")
        dlg.accept()
        # 校验失败
        assert not dlg.result_accepted()
    finally:
        dlg.deleteLater()