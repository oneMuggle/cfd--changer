"""EnumChecklistDialog 测试 — 枚举多选弹窗。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless。

测试覆盖:
- 构造传入 choices + selected,初始勾选状态正确
- 模拟用户勾选后,get_selected() 返回新集合
- 初始 selected 为空集时,所有项未勾选
- EnumChecklistDialog 是 QDialog 子类
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide2.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_enum_checklist_dialog_returns_selected(qapp):
    from PySide2.QtCore import Qt
    from inp_tool_gui.widgets.enum_checklist_dialog import EnumChecklistDialog
    dlg = EnumChecklistDialog(
        choices=["sst", "kw", "sa"],
        selected={"sst"},
        parent=None,
    )
    # 模拟用户勾选 kw(PySide2 需要 Qt.CheckState 枚举,不能用裸 int)
    dlg._list_widget.item(1).setCheckState(Qt.Checked)
    assert dlg.get_selected() == {"sst", "kw"}


def test_enum_checklist_initial_state_matches_selected(qapp):
    """传入 selected={'sst'} 时,第一项 checked,其余 unchecked。"""
    from inp_tool_gui.widgets.enum_checklist_dialog import EnumChecklistDialog
    dlg = EnumChecklistDialog(
        choices=["sst", "kw", "sa"],
        selected={"sst"},
        parent=None,
    )
    item0 = dlg._list_widget.item(0)
    item1 = dlg._list_widget.item(1)
    item2 = dlg._list_widget.item(2)
    assert item0.checkState() == 2  # Checked
    assert item1.checkState() == 0  # Unchecked
    assert item2.checkState() == 0  # Unchecked


def test_enum_checklist_empty_selected_means_all_unchecked(qapp):
    """selected 为空集时,所有项都未勾选。"""
    from inp_tool_gui.widgets.enum_checklist_dialog import EnumChecklistDialog
    dlg = EnumChecklistDialog(
        choices=["sst", "kw", "sa"],
        selected=set(),
        parent=None,
    )
    for i in range(3):
        assert dlg._list_widget.item(i).checkState() == 0


def test_enum_checklist_is_a_qdialog(qapp):
    """EnumChecklistDialog 必须是 QDialog 子类。"""
    from PySide2.QtWidgets import QDialog
    from inp_tool_gui.widgets.enum_checklist_dialog import EnumChecklistDialog
    dlg = EnumChecklistDialog(choices=["a", "b"], selected=set(), parent=None)
    assert isinstance(dlg, QDialog)
