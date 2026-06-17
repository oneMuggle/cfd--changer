"""VariableTreeWidget 单元测试(共享组件 Task 4.1)。

覆盖:
- 空构造
- set_vars → 树构建 + 分组(枚举轴 / <top> / 块)
- 双击 + itemActivated → emit variable_picked(key)
- 搜索过滤 → 隐藏不匹配项
- set_template_path → 走 enumerate_vars
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide2.QtCore import Qt  # noqa: E402
from PySide2.QtWidgets import QApplication, QLineEdit, QTreeWidgetItem  # noqa: E402

from inp_tool_gui.widgets.sweep_var_combo import VarSpec  # noqa: E402
from inp_tool_gui.widgets.variable_tree_widget import (  # noqa: E402
    VariableTreeWidget,
    _GROUP_ENUM,
    _GROUP_TOP,
)


# ---- fixtures --------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    """整个模块共用一个 QApplication 实例。"""
    return QApplication.instance() or QApplication([])


def _find_leaf(w: VariableTreeWidget, contains: str) -> QTreeWidgetItem:
    """在树里找第 0 列文本包含 contains 的 leaf item。"""
    for i in range(w.tree.topLevelItemCount()):
        group = w.tree.topLevelItem(i)
        for j in range(group.childCount()):
            child = group.child(j)
            if contains in child.text(0):
                return child
    raise AssertionError("未找到包含 '{}' 的 leaf item".format(contains))


def _total_children(w: VariableTreeWidget) -> int:
    return sum(
        w.tree.topLevelItem(i).childCount()
        for i in range(w.tree.topLevelItemCount())
    )


# ---- 测试 ------------------------------------------------------------


def test_widget_creates_empty(qapp):
    """空构造:无 top-level item。"""
    w = VariableTreeWidget()
    assert w.tree.topLevelItemCount() == 0
    assert w._all_vars == []
    assert w._filtered_vars == []
    assert w._template_path is None
    # 搜索框存在
    assert isinstance(w.search_edit, QLineEdit)


def test_widget_set_vars_populates_tree(qapp):
    """set_vars → 树被填充,分组正确(枚举轴 / <top> / 块)。"""
    w = VariableTreeWidget()
    samples = [
        # 枚举轴(应归入 "(枚举轴)")
        VarSpec(key="turbulence", label="turbulence (枚举:sst,kw)", kind="enum",
                block=None, keyword=None, value_idx=None,
                enum_values=("sst", "kw")),
        # <top> 顶层
        VarSpec(key="mach[0]", label="mach[0] [int] = 1",
                kind="int", block="<top>", keyword="mach", value_idx=0),
        VarSpec(key="runtype[0]", label="runtype[0] [str] = default",
                kind="str", block="<top>", keyword="runtype", value_idx=0),
        # 块内
        VarSpec(key="physics.reynolds[0]",
                label="physics.reynolds[0] [float] = 1.0e6",
                kind="float", block="physics",
                keyword="reynolds", value_idx=0),
    ]
    w.set_vars(samples)

    # 顶层 group 顺序:(枚举轴) → <top> → 其他块名(字母序)
    g_names = [
        w.tree.topLevelItem(i).text(0)
        for i in range(w.tree.topLevelItemCount())
    ]
    assert g_names == [_GROUP_ENUM, _GROUP_TOP, "physics"]
    # 子项数
    assert w.tree.topLevelItem(0).childCount() == 1  # (枚举轴): turbulence
    assert w.tree.topLevelItem(1).childCount() == 2  # <top>: mach, runtype
    assert w.tree.topLevelItem(2).childCount() == 1  # physics: reynolds
    # 总数
    assert _total_children(w) == 4


def test_widget_picks_var_on_double_click(qapp):
    """双击一个变量 → emit variable_picked(key) 信号。"""
    w = VariableTreeWidget()
    samples = [
        VarSpec(key="mach", label="mach [int]", kind="int",
                block="<top>", keyword="mach", value_idx=0),
        VarSpec(key="turbulence", label="turbulence (枚举:sst,kw,sa)",
                kind="enum", block=None, keyword=None, value_idx=None,
                enum_values=("sst", "kw", "sa")),
    ]
    w.set_vars(samples)

    received: list = []
    w.variable_picked.connect(lambda k: received.append(k))

    # 找到代表 mach 的 tree item 并触发 itemDoubleClicked
    item = _find_leaf(w, "mach")
    item.setSelected(True)
    w.tree.itemDoubleClicked.emit(item, 0)
    assert "mach" in received

    # 清空,再双击 turbulence
    received.clear()
    item2 = _find_leaf(w, "turbulence")
    w.tree.itemDoubleClicked.emit(item2, 0)
    assert "turbulence" in received


def test_widget_picks_var_on_item_activated(qapp):
    """itemActivated(item, col) 同样触发拾取(键盘 Enter / 程序触发)。"""
    w = VariableTreeWidget()
    w.set_vars([
        VarSpec(key="mach", label="mach [int]", kind="int",
                block="<top>", keyword="mach", value_idx=0),
    ])
    received: list = []
    w.variable_picked.connect(lambda k: received.append(k))

    item = _find_leaf(w, "mach")
    w.tree.itemActivated.emit(item, 0)
    assert "mach" in received


def test_widget_double_click_group_does_not_emit(qapp):
    """双击 group 行(非 leaf)不应 emit signal。"""
    w = VariableTreeWidget()
    w.set_vars([
        VarSpec(key="mach", label="mach [int]", kind="int",
                block="<top>", keyword="mach", value_idx=0),
    ])
    received: list = []
    w.variable_picked.connect(lambda k: received.append(k))

    group = w.tree.topLevelItem(0)  # "<top>"
    w.tree.itemDoubleClicked.emit(group, 0)
    assert received == []


def test_search_filter_narrows_results(qapp):
    """搜索框输入 'mach' → 只显示 mach 相关变量。"""
    w = VariableTreeWidget()
    w.set_vars([
        VarSpec(key="mach", label="mach [int]", kind="int",
                block="<top>", keyword="mach", value_idx=0),
        VarSpec(key="reynolds", label="reynolds [float]", kind="float",
                block="physics", keyword="reynolds", value_idx=0),
        VarSpec(key="turbulence", label="turbulence (枚举:sst,kw)",
                kind="enum", enum_values=("sst", "kw")),
    ])
    # 初始: 3 个 leaf
    assert _total_children(w) == 3

    w.search_edit.setText("mach")
    # 触发 textChanged(QLineEdit.setText 自动触发)
    assert _total_children(w) == 1
    leaf = _find_leaf(w, "mach")
    assert leaf.text(0) == "mach [int]"


def test_search_filter_case_insensitive(qapp):
    """搜索大小写不敏感。"""
    w = VariableTreeWidget()
    w.set_vars([
        VarSpec(key="MAchin", label="Machin (case test)", kind="str",
                block="<top>", keyword="machin", value_idx=0),
    ])
    w.search_edit.setText("machin")
    assert _total_children(w) == 1
    w.search_edit.setText("MACHIN")
    assert _total_children(w) == 1


def test_search_filter_matches_label(qapp):
    """搜索命中 label 而非 key。"""
    w = VariableTreeWidget()
    w.set_vars([
        VarSpec(key="xyz", label="高度机密参数", kind="float",
                block="<top>", keyword="xyz", value_idx=0),
    ])
    w.search_edit.setText("高度")
    assert _total_children(w) == 1
    w.search_edit.setText("nothing-here")
    assert _total_children(w) == 0


def test_search_filter_clearing_restores_full(qapp):
    """清空搜索框 → 恢复完整列表。"""
    w = VariableTreeWidget()
    w.set_vars([
        VarSpec(key="a", label="a", kind="int",
                block="<top>", keyword="a", value_idx=0),
        VarSpec(key="b", label="b", kind="int",
                block="<top>", keyword="b", value_idx=0),
        VarSpec(key="c", label="c", kind="int",
                block="<top>", keyword="c", value_idx=0),
    ])
    assert _total_children(w) == 3
    w.search_edit.setText("a")
    assert _total_children(w) == 1
    w.search_edit.setText("")
    assert _total_children(w) == 3


def test_set_vars_empty_does_not_crash(qapp):
    """set_vars([]) → 清空树,不报错。"""
    w = VariableTreeWidget()
    w.set_vars([
        VarSpec(key="x", label="x", kind="int",
                block="<top>", keyword="x", value_idx=0),
    ])
    assert _total_children(w) == 1
    w.set_vars([])
    assert w.tree.topLevelItemCount() == 0
    assert w._all_vars == []
    assert w._filtered_vars == []


def test_set_template_path_uses_enumerate_vars(qapp, monkeypatch):
    """set_template_path 走 enumerate_vars,结果与直接调 enumerate_vars 一致。"""
    from inp_tool_gui.widgets import variable_tree_widget as mod

    called_with: list = []

    def fake_enum(path):
        called_with.append(path)
        return [VarSpec(key="fake_key", label="fake_label",
                        kind="str", block="<top>",
                        keyword="fake", value_idx=0)]

    monkeypatch.setattr(mod, "enumerate_vars", fake_enum)

    w = VariableTreeWidget()
    w.set_template_path("/some/path.inp")
    assert called_with == ["/some/path.inp"]
    assert w._template_path == "/some/path.inp"
    assert _total_children(w) == 1


def test_set_template_path_none_handled(qapp):
    """set_template_path(None) 不报错;真实 enumerate_vars(None) 返回 3 个枚举轴。"""
    w = VariableTreeWidget()
    w.set_template_path(None)
    assert w._template_path is None
    # 真实 enumerate_vars(None) 返回 3 个 enum,归入 "(枚举轴)" group
    assert w.tree.topLevelItemCount() == 1
    assert w.tree.topLevelItem(0).text(0) == _GROUP_ENUM
    assert w.tree.topLevelItem(0).childCount() == 3
