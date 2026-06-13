"""DetectPanel + PresetDialog 单元测试(Phase 4)。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from inp_tool.model import Block, InpFile, Stmt, Value

from inp_tool_gui.controllers.detect_controller import DetectController
from inp_tool_gui.controllers.edit_controller import EditController
from inp_tool_gui.controllers.file_controller import FileController


# --- fixture -------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    from PySide2.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def controllers():
    fc = FileController()
    ec = EditController(fc)
    dc = DetectController()
    return fc, ec, dc


@pytest.fixture
def physics_inp():
    inp = InpFile()
    b = Block(name="physics", begin_line=1, end_line=10)
    b.statements = [
        Stmt(keyword="reftem", values=[Value(raw="300.0")], line=1),
        Stmt(keyword="reynolds", values=[Value(raw="1.0e6")], line=2),
        Stmt(keyword="turbi", values=[Value(raw="0.01")], line=3),
    ]
    inp.block_list = [b]
    return inp


# --- DetectPanel ---------------------------------------------------------


def test_panel_run_populates_summary(qapp, controllers, physics_inp):
    """run 后摘要标签更新。"""
    _fc, ec, dc = controllers
    from inp_tool_gui.widgets.detect_panel import DetectPanel

    panel = DetectPanel(dc, ec)
    try:
        rep = panel.run(physics_inp)
        assert "检测到" in panel._summary_lbl.text()
        assert rep.has_reftem is True
        assert panel._lbl_reftem.text() == "✓"
    finally:
        panel.deleteLater()


def test_panel_preset_signal_emits(qapp, controllers, physics_inp):
    """点 Preset 按钮 → preset_requested 信号带正确名字。"""
    _fc, ec, dc = controllers
    from inp_tool_gui.widgets.detect_panel import DetectPanel

    panel = DetectPanel(dc, ec)
    try:
        panel.run(physics_inp)
        captured = []
        panel.preset_requested.connect(lambda n: captured.append(n))
        panel._btn_preset_turb.click()
        panel._btn_preset_2t.click()
        panel._btn_preset_species.click()
        assert captured == ["turb", "2t", "species"]
    finally:
        panel.deleteLater()


def test_panel_apply_recommended_writes_value(qapp, controllers):
    """点推荐字段的'应用' → EditController.set_value 被调。"""
    fc, ec, dc = controllers
    inp = InpFile()
    b = Block(name="physics", begin_line=1, end_line=10)
    b.statements = [
        Stmt(keyword="reftem", values=[Value(raw="300")], line=1),
        Stmt(keyword="turbi", values=[Value(raw="0.01")], line=2),
    ]
    inp.block_list = [b]
    fc._inp = inp  # 直接注入
    fc._path = inp.path or "test.inp"

    from inp_tool_gui.widgets.detect_panel import DetectPanel

    panel = DetectPanel(dc, ec)
    try:
        panel.run(inp)
        assert ec.can_undo is False

        # 找推荐字段里的"应用"按钮
        from PySide2.QtWidgets import QPushButton
        btn = None
        for i in range(panel._rec_layout.count()):
            item = panel._rec_layout.itemAt(i)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                found = w.findChild(QPushButton)
                if found:
                    btn = found
                    break
        assert btn is not None, "未找到推荐字段的应用按钮"
        btn.click()
        assert ec.can_undo is True
    finally:
        panel.deleteLater()


# --- PresetDialog --------------------------------------------------------


def test_preset_dialog_turb_writes_values(qapp, controllers, physics_inp):
    """PresetDialog(turb).accept() → EditController 推 4 条 undo,InpFile 字段更新。"""
    fc, ec, _dc = controllers
    fc._inp = physics_inp
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    dlg = PresetDialog("turb", ec)
    try:
        assert dlg.op_count == 4
        dlg.accept()
        assert dlg.applied is True
        assert ec.undo_depth == 4
        assert fc.get_value("physics", "reynolds") == 1.0e6
        assert fc.get_value("physics", "turbi") == 0.01
    finally:
        dlg.deleteLater()


def test_preset_dialog_2t_writes_values(qapp, controllers, physics_inp):
    """PresetDialog(2t).accept() → reftem/vibtem/turbe 写入。"""
    fc, ec, _dc = controllers
    fc._inp = physics_inp
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    dlg = PresetDialog("2t", ec)
    try:
        assert dlg.op_count == 3
        dlg.accept()
        assert fc.get_value("physics", "vibtem") == 300.0
        assert fc.get_value("physics", "turbe") == 0
    finally:
        dlg.deleteLater()


def test_preset_dialog_reject_writes_nothing(qapp, controllers, physics_inp):
    """PresetDialog.reject() → 不写入,undo 栈空。"""
    fc, ec, _dc = controllers
    fc._inp = physics_inp
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    dlg = PresetDialog("turb", ec)
    try:
        dlg.reject()
        assert dlg.applied is False
        assert ec.undo_depth == 0
    finally:
        dlg.deleteLater()


def test_preset_dialog_unknown_raises(qapp, controllers):
    """未知 preset_name → ValueError。"""
    _fc, ec, _dc = controllers
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    with pytest.raises(ValueError):
        PresetDialog("nonexistent", ec)


def test_preset_dialog_species_is_placeholder(qapp, controllers):
    """species preset 当前是占位(op_count == 0)。"""
    _fc, ec, _dc = controllers
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    dlg = PresetDialog("species", ec)
    try:
        assert dlg.op_count == 0
    finally:
        dlg.deleteLater()