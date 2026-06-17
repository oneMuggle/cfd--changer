"""EnumChecklistDialog:枚举多选弹窗。

用于 ``SweepForm`` 的 enum_subset 字段 — 用户点击单元格时弹出,
在 checklist 中勾选/取消枚举值,确定后通过 :py:meth:`get_selected` 取回集合。

设计要点:
- 子类化 :class:`QDialog`,提供 OK / Cancel 按钮
- 内部 :class:`QListWidget`,每项带 :class:`Qt.ItemIsUserCheckable` flag
- 初始勾选状态由构造时的 ``selected`` 集合决定
- ``get_selected`` 实时从 list widget 重新读取,无需在勾选时维护影子状态
"""
from typing import Iterable, Optional, Set

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class EnumChecklistDialog(QDialog):
    """枚举多选弹窗。

    Parameters
    ----------
    choices:
        可供勾选的枚举值列表(显示顺序即传入顺序)。
    selected:
        初始已选集合。
    parent:
        父 widget,可为 None。
    """

    def __init__(
        self,
        choices: Iterable[str],
        selected: Set[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Select enum values"))

        # 先把 selected 物化成 set,允许传入可迭代对象(list/iterable)
        self._initial_selected = set(selected)
        self._choices = list(choices)

        layout = QVBoxLayout(self)

        self._list_widget = QListWidget(self)
        for choice in self._choices:
            item = QListWidgetItem(str(choice), self._list_widget)
            # 同时设置 Selectable(允许键盘导航)与 UserCheckable(显示复选框)
            item.setFlags(
                Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled
            )
            item.setCheckState(
                Qt.Checked if choice in self._initial_selected else Qt.Unchecked
            )
        layout.addWidget(self._list_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected(self) -> Set[str]:
        """返回当前勾选的枚举值集合。

        调用时机不限制:在 ``accept()`` 之前可预览,``accept()`` 之后取最终结果。
        """
        result = set()
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if item.checkState() == Qt.Checked:
                result.add(item.text())
        return result
