"""InpTreeWidget 单元测试(Phase 3)。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless。

测试覆盖:
- populate 后顶层含 '顶层语句' 与 '块' 两个父节点
- block 下每条 stmt 一行,values 在 stmt 行下
- 双击 value 单元格触发 ``value_edit_requested`` signal
- refresh_row 修改显示文本
- empty input 不报错
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide2.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# --- fixture: 构造一个测试用 InpFile ------------------------------------


@pytest.fixture
def small_inp():
    """构造 2 个 top_stmt + 2 个 block 的 InpFile。

    top_stmts:
        title  = "Hello"
        runtype = "default"
    blocks:
        physics: reftem = 300.0, reynolds = 1.0e6
        chemistry (idx 0): model = "air5"
        chemistry (idx 1): model = "air7"
    """
    from inp_tool.model import Block, InpFile, Stmt, Value

    inp = InpFile()
    inp.top_stmts = [
        Stmt(keyword="title", values=[Value(raw="Hello")], line=1),
        Stmt(keyword="runtype", values=[Value(raw="default")], line=2),
    ]
    b1 = Block(name="physics", begin_line=10, end_line=20)
    b1.statements = [
        Stmt(keyword="reftem", values=[Value(raw="300.0")], line=11),
        Stmt(keyword="reynolds", values=[Value(raw="1.0e6")], line=12),
    ]
    b2 = Block(name="chemistry", begin_line=30, end_line=40)
    b2.statements = [Stmt(keyword="model", values=[Value(raw="air5")], line=31)]
    b3 = Block(name="chemistry", begin_line=50, end_line=60)
    b3.statements = [Stmt(keyword="model", values=[Value(raw="air7")], line=51)]
    inp.block_list = [b1, b2, b3]
    return inp


# --- populate --------------------------------------------------------


def test_populate_empty_no_error(qapp):
    """空 InpFile 不报错。"""
    from inp_tool.model import InpFile
    from inp_tool_gui.widgets.inp_tree import InpTreeWidget

    tree = InpTreeWidget()
    try:
        tree.populate(InpFile())  # 无 top_stmts / 无 block
        # 顶层有 '顶层语句' + '块' 两个节点(可能都空)
        labels = tree.top_level_labels()
        assert "顶层语句" in labels
        assert "块" in labels
    finally:
        tree.deleteLater()


def test_populate_top_stmts_appear(qapp, small_inp):
    """top_stmts 在 '顶层语句' 节点下。"""
    from inp_tool_gui.widgets.inp_tree import InpTreeWidget

    tree = InpTreeWidget()
    try:
        tree.populate(small_inp)
        top = tree.top_level_labels()
        # 顶层语句节点子项 = 2
        n = tree.child_count("顶层语句")
        assert n == 2
    finally:
        tree.deleteLater()


def test_populate_blocks_appear_with_index(qapp, small_inp):
    """同名块按 idx 区分,3 个 block 都在 '块' 节点下。"""
    from inp_tool_gui.widgets.inp_tree import InpTreeWidget

    tree = InpTreeWidget()
    try:
        tree.populate(small_inp)
        n = tree.child_count("块")
        assert n == 3  # physics + chemistry(idx 0) + chemistry(idx 1)
    finally:
        tree.deleteLater()


def test_populate_block_shows_stmts(qapp, small_inp):
    """block 下每条 stmt 一行。physics 有 2 条 stmt。"""
    from inp_tool_gui.widgets.inp_tree import InpTreeWidget

    tree = InpTreeWidget()
    try:
        tree.populate(small_inp)
        # block 'physics' 节点下有 2 条 stmt
        n = tree.child_count("physics")
        assert n == 2
    finally:
        tree.deleteLater()


# --- 信号 --------------------------------------------------------------


def test_double_click_value_emits_signal(qapp, small_inp):
    """双击 value 单元格触发 value_edit_requested signal(供 MainWindow 接)。"""
    from inp_tool_gui.widgets.inp_tree import InpTreeWidget

    tree = InpTreeWidget()
    try:
        tree.populate(small_inp)
        # 找到 'reftem' 行的第一个 value 子项
        value_item = tree.find_value_item(
            parent_label="physics", stmt_keyword="reftem", value_idx=0
        )
        assert value_item is not None
        captured = []

        def on_signal(block_idx, keyword, value_idx):
            captured.append((block_idx, keyword, value_idx))

        tree.value_edit_requested.connect(on_signal)
        # 直接触发编辑请求(模拟双击)
        tree.request_edit(value_item)
        assert len(captured) == 1
        block_idx, keyword, value_idx = captured[0]
        assert keyword == "reftem"
        assert value_idx == 0
        # physics 是 block_list 第一个,block_idx 应为 0
        assert block_idx == 0
    finally:
        tree.deleteLater()


def test_double_click_top_stmt_value_emits_signal(qapp, small_inp):
    """顶层语句的 value 双击也触发 signal(block_idx = -1 表示 top_stmt)。"""
    from inp_tool_gui.widgets.inp_tree import InpTreeWidget

    tree = InpTreeWidget()
    try:
        tree.populate(small_inp)
        value_item = tree.find_value_item(
            parent_label="顶层语句", stmt_keyword="title", value_idx=0
        )
        assert value_item is not None
        captured = []

        tree.value_edit_requested.connect(
            lambda block_idx, kw, vi: captured.append((block_idx, kw, vi))
        )
        tree.request_edit(value_item)
        assert captured == [(-1, "title", 0)]
    finally:
        tree.deleteLater()


# --- refresh_row ------------------------------------------------------


def test_refresh_row_updates_displayed_text(qapp, small_inp):
    """refresh_row 改 value 的 raw 显示文本。"""
    from inp_tool_gui.widgets.inp_tree import InpTreeWidget

    tree = InpTreeWidget()
    try:
        tree.populate(small_inp)
        # 修改 raw 后 refresh
        stmt = small_inp.block_list[0].statements[0]  # physics.reftem
        stmt.values[0].raw = "500.0"
        stmt.values[0].typed = 500.0
        tree.refresh_value("physics", "reftem", 0)
        value_item = tree.find_value_item(
            parent_label="physics", stmt_keyword="reftem", value_idx=0
        )
        assert value_item.text(0) == "500.0"
    finally:
        tree.deleteLater()