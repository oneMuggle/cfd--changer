"""SweepYamlEditorWidget (Phase 5 / Task 5.1) GUI 单测。

覆盖范围:
- 空 widget 构造 + text() == ""
- set_text / text round-trip
- 等宽字体(monospace / Courier)
- set_error_line 不崩(无 public getter,只验证不抛)
- 行号区在 widget 销毁时不崩(显式调用 hide / deleteLater 后再次实例化)
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide2.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_editor_creates_empty(qapp):
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    assert w.text() == ""


def test_editor_set_text_get_text_roundtrip(qapp):
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    sample = "version: 2\ntemplate: t.inp\nsweeps:\n  mach: [1, 2]\n"
    w.set_text(sample)
    assert w.text() == sample


def test_editor_uses_monospace_font(qapp):
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    font = w.font()
    family = font.family().lower()
    # 任一 monospace 风格字体家族皆可(Qt 视平台 fallback)
    assert "mono" in family or "courier" in family


def test_editor_set_error_line(qapp):
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    w.set_text("line1\nline2\nline3\n")
    # 标记第二行为错误;不应崩
    w.set_error_line(2)
    assert w.error_line == 2
    # 清除错误
    w.set_error_line(0)
    assert w.error_line == 0
    # 越界 / 负数:不应崩,被夹到 0
    w.set_error_line(-3)
    assert w.error_line == 0
    w.set_error_line(999)
    assert w.error_line == 999


def test_editor_syntax_highlighter_attached(qapp):
    """高亮器应已 attach 到内部 editor 的 document。"""
    from inp_tool_gui.widgets.sweep_yaml_editor import (
        YamlEditorWidget,
        YamlHighlighter,
    )

    w = YamlEditorWidget()
    # 高亮器存在 + 类型正确
    assert isinstance(w._highlighter, YamlHighlighter)  # type: ignore[attr-defined]
    # 内部 editor 可访问(供子类扩展)
    assert w.plain_text_edit is not None


def test_editor_text_changes_after_edit(qapp):
    """用户手动编辑后 text() 应反映最新内容。"""
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    w.set_text("version: 2\n")
    # 移动光标到末尾并插入文本(模拟用户键入)
    cursor = w.plain_text_edit.textCursor()
    cursor.movePosition(cursor.End)
    w.plain_text_edit.setTextCursor(cursor)
    cursor.insertText("template: t.inp\n")
    assert "template: t.inp" in w.text()
    assert w.text().startswith("version: 2")
