"""FieldSearchBar:挂在 :class:`QTreeWidget` 顶部的搜索框,实时过滤 item。

行为:
- 输入文本 → 所有 item 的 text(0) 做子串匹配
- 匹配项 setHidden(False);不匹配的 setHidden(True)
- 父节点:若有任一子项匹配,父节点也保持可见
- 清空 → 全部显示
- emit ``match_count_changed(int)``:当前可见 item 数
"""
from typing import Optional

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from inp_tool.i18n_gui import tg


class FieldSearchBar(QWidget):
    """树形搜索框。"""

    match_count_changed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tree: Optional[QTreeWidget] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText(tg("tree.search.placeholder"))
        self._edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._edit, 1)

        self._btn_clear = QPushButton(tg("tree.search.btn_clear"), self)
        self._btn_clear.clicked.connect(self._edit.clear)
        layout.addWidget(self._btn_clear)

    def attach(self, tree: QTreeWidget) -> None:
        """绑定一棵要过滤的树。"""
        self._tree = tree

    def set_query(self, text: str) -> None:
        """程序化设置搜索词(测试用,等同用户在编辑框输入)。"""
        self._edit.setText(text)

    def _on_text_changed(self, text: str) -> None:
        if self._tree is None:
            return
        text_lower = text.lower()
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            self._filter_item(top, text_lower)

        visible = self._count_visible(self._tree)
        self.match_count_changed.emit(visible)

    def _filter_item(self, item: QTreeWidgetItem, text_lower: str) -> bool:
        own_match = text_lower in item.text(0).lower() if text_lower else True
        any_child_visible = False
        for i in range(item.childCount()):
            child = item.child(i)
            child_visible = self._filter_item(child, text_lower)
            any_child_visible = any_child_visible or child_visible

        visible = own_match or any_child_visible
        item.setHidden(not visible)
        return visible

    def _count_visible(self, tree: QTreeWidget) -> int:
        n = 0

        def walk(item: QTreeWidgetItem) -> None:
            nonlocal n
            if not item.isHidden():
                n += 1
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(i))
        return n
