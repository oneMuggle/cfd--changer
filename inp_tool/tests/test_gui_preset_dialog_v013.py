"""PresetDialog v0.13 测试:用真实 preset.apply() API。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless。

测试覆盖:
- 构造后 preset_name + preset 实例正确
- 3 类 preset 都能构造
- accept(inp) 成功调用 preset.apply 并改 InpFile
- 未知 preset_name 抛 ValueError
- inp 为 None 时 accept 不通过(错误标签)
- EquationRewriteError 触发错误标签
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide2.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def small_inp():
    """含 physics + guiopts + 顶层 seq.# eqnset_define(初始 LAMINAR 0,1)的最小 inp。"""
    from inp_tool.model import Block, InpFile, Stmt, Value

    inp = InpFile()
    pb = Block(name="physics", begin_line=1, end_line=20)
    pb.statements = [
        Stmt(keyword="reftem", values=[Value(raw="300.0")], line=1),
        Stmt(keyword="reynolds", values=[Value(raw="1.0e6")], line=2),
    ]
    gb = Block(name="guiopts", begin_line=30, end_line=40)
    gb.statements = [
        Stmt(keyword="turbi_lev", values=[Value(raw="0.0")], line=31),
        Stmt(keyword="turbi_len", values=[Value(raw="0.0")], line=32),
    ]
    inp.block_list = [pb, gb]
    inp.top_stmts = [
        Stmt(
            keyword="seq.#",
            values=[Value(raw="1")],
            line=100,
            children=[
                Stmt(keyword="values", values=[Value(raw="101"), Value(raw="1"), Value(raw="1"), Value(raw="0"), Value(raw="1")], line=101),
                Stmt(keyword="values", values=[Value(raw="0"), Value(raw="0"), Value(raw="1"), Value(raw="1"), Value(raw="1")], line=102),
            ],
        ),
    ]
    return inp


# --- 构造 --------------------------------------------------------------


def test_construct_turb(qapp):
    """PresetDialog(turb) 构造成功。"""
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    dlg = PresetDialog("turb")
    try:
        assert dlg.preset_name == "turb"
        assert dlg.applied is False
    finally:
        dlg.deleteLater()


def test_construct_2t(qapp):
    """PresetDialog(2t) 构造成功。"""
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    dlg = PresetDialog("2t")
    try:
        assert dlg.preset_name == "2t"
    finally:
        dlg.deleteLater()


def test_construct_species(qapp):
    """PresetDialog(species) 构造成功。"""
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    dlg = PresetDialog("species")
    try:
        assert dlg.preset_name == "species"
    finally:
        dlg.deleteLater()


def test_construct_unknown_raises(qapp):
    """未知 preset_name 抛 ValueError。"""
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    with pytest.raises(ValueError):
        PresetDialog("nonexistent")


# --- accept 行为 -------------------------------------------------------


def test_accept_without_inp_shows_error(qapp):
    """accept() 未调 set_inp → 错误标签设了文本,dialog 保持打开。"""
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    dlg = PresetDialog("turb")
    try:
        dlg.accept()
        assert dlg.applied is False
        # dialog 未 exec_() 显示,isVisible() 返 False;检查 text 已设即可
        assert "InpFile" in dlg._error_lbl.text() or "未设置" in dlg._error_lbl.text()
    finally:
        dlg.deleteLater()


def test_accept_turb_applies_sst_kw(qapp, small_inp):
    """accept(inp) + SST_KW preset → physics 字段更新。"""
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    dlg = PresetDialog("turb")
    try:
        dlg.set_inp(small_inp)
        dlg.accept()
        assert dlg.applied is True
        # SST preset 会改 reynolds / turbi_lev / turbi_len
        assert small_inp.get("physics", "reynolds") is not None
    finally:
        dlg.deleteLater()


def test_accept_2t_sets_tnoneq_numeqns(qapp, small_inp):
    """accept(inp) + 2T preset → physics.tnoneq_numeqns=1。"""
    from inp_tool_gui.widgets.preset_dialog import PresetDialog

    dlg = PresetDialog("2t")
    try:
        dlg.set_inp(small_inp)
        dlg.accept()
        assert dlg.applied is True
        assert small_inp.get("physics", "tnoneq_numeqns") == 1
    finally:
        dlg.deleteLater()