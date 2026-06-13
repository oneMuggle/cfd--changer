"""DetectPanel + PresetDialog 单元测试(v0.13 升级版)。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless。

v0.13:DetectPanel 跑真实 :func:`detect_equations`,PresetDialog 调真实
``make_turbulence_preset`` / ``TwoTemperaturePreset`` / ``SpeciesPreset``。
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
    """含 physics + guiopts + 顶层 seq.# eqnset_define(SST k-ω 2T 算例)。"""
    inp = InpFile()
    pb = Block(name="physics", begin_line=1, end_line=20)
    pb.statements = [
        Stmt(keyword="reftem", values=[Value(raw="300.0")], line=1),
        Stmt(keyword="reynolds", values=[Value(raw="1.0e6")], line=2),
        Stmt(keyword="turbi", values=[Value(raw="0.01")], line=3),
        Stmt(keyword="tnoneq_numeqns", values=[Value(raw="0")], line=4),
    ]
    gb = Block(name="guiopts", begin_line=30, end_line=40)
    gb.statements = [
        Stmt(keyword="turbi_lev", values=[Value(raw="0.0")], line=31),
    ]
    inp.block_list = [pb, gb]

    # 顶层 seq.# eqnset_define(SST k-ω):家族 2 + 码 3 + 气体 v6=0
    inp.top_stmts = [
        Stmt(
            keyword="seq.#",
            values=[Value(raw="1")],
            line=100,
            children=[
                Stmt(keyword="values", values=[Value(raw="101"), Value(raw="1"), Value(raw="1"), Value(raw="2"), Value(raw="3")], line=101),
                Stmt(keyword="values", values=[Value(raw="0"), Value(raw="0"), Value(raw="1"), Value(raw="1"), Value(raw="1")], line=102),
            ],
        ),
    ]
    return inp


# --- DetectPanel ---------------------------------------------------------


def test_panel_run_populates_summary(qapp, controllers, physics_inp):
    """run 后摘要标签更新为真实 EquationSystemReport 格式。"""
    _fc, ec, dc = controllers
    from inp_tool_gui.widgets.detect_panel import DetectPanel

    panel = DetectPanel(dc, ec)
    try:
        rep = panel.run(physics_inp)
        s = panel._summary_lbl.text()
        # v0.13 摘要含 '湍流=' 和 '能量=' 前缀
        assert "湍流=" in s
        assert "能量=" in s
        assert rep.has_reftem is True
        assert rep.has_reynolds is True
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


def test_panel_apply_recommended_writes_value(qapp, controllers, physics_inp):
    """点推荐字段的'应用' → EditController.set_value 被调(用 SST 算例触发 recommended_fields)。"""
    fc, ec, dc = controllers
    fc._inp = physics_inp
    fc._path = "test.inp"

    from inp_tool_gui.widgets.detect_panel import DetectPanel

    panel = DetectPanel(dc, ec)
    try:
        panel.run(physics_inp)
        # SST_KW 算例应有 turbi_lev/turbi_len/turbi_tlev/turbi_tlen 推荐字段
        assert any("turbi" in f[1] for f in dc.last_report.recommended_fields)
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

# PresetDialog 测试在子任务 #2(PresetDialog 升级)中重写,届时用真实 preset.apply() API。
# 当前保留 placeholder:
def test_preset_dialog_pending_v013(qapp, controllers):
    """v0.13:PresetDialog 真实 preset 行为测试在子任务 #2 重写后补上。"""
    pass


# --- v0.13 新增:DetectPanel 显示 EquationSystemReport 枚举 ------------------


def test_panel_shows_energy_turbulence_gas_labels(qapp, controllers, physics_inp):
    """v0.13:DetectPanel 新增 能量/湍流/气体 3 个 enum 标签。"""
    _fc, ec, dc = controllers
    from inp_tool_gui.widgets.detect_panel import DetectPanel

    panel = DetectPanel(dc, ec)
    try:
        panel.run(physics_inp)
        # SST_KW 算例,energy=none,gas=perfect-gas
        assert panel._lbl_energy.text() == "none"
        assert panel._lbl_turbulence_model.text() == "k-omega-sst"
        assert panel._lbl_gas.text() == "perfect-gas"
    finally:
        panel.deleteLater()


def test_panel_run_with_intended_axes(qapp, controllers, physics_inp):
    """v0.13:DetectPanel.run(inp, intended_axes=...) 透传到 controller。

    模板 tnoneq=0 但 wizard 选 energy=2T → 应触发 sweeps_equation_warnings。
    """
    _fc, ec, dc = controllers
    from inp_tool_gui.widgets.detect_panel import DetectPanel

    panel = DetectPanel(dc, ec)
    try:
        panel.run(physics_inp, intended_axes={"energy": "2T"})
        text = panel._sweep_warn_view.toPlainText()
        # 应含 2T 或 tnoneq 关键字
        assert "2T" in text or "tnoneq" in text
    finally:
        panel.deleteLater()


def test_panel_separate_warning_views(qapp, controllers, physics_inp):
    """v0.13:notes 与 sweeps_equation_warnings 是两个独立视图。"""
    _fc, ec, dc = controllers
    from inp_tool_gui.widgets.detect_panel import DetectPanel

    panel = DetectPanel(dc, ec)
    try:
        panel.run(physics_inp)
        # 两个视图独立存在
        assert panel._notes_view is not panel._sweep_warn_view
    finally:
        panel.deleteLater()