"""VariableTreeWidget:Sweep 可用变量树(共享组件,Task 4.1)。

UI 结构::

    +-----------------------------------------+
    | [ 搜索变量...                          ] |
    +-----------------------------------------+
    | 变量名             | 类型               |
    +--------------------+--------------------+
    | (枚举轴)           |                    |
    |   turbulence       | enum               |
    |   energy           | enum               |
    |   gas              | enum               |
    | <top>              |                    |
    |   mach[0]          | int                |
    | physics            |                    |
    |   reynolds[0]      | float              |
    | ...                |                    |
    +-----------------------------------------+

- 双击任一变量 leaf → emit :attr:`variable_picked`(payload 是 ``VarSpec.key``)
- 搜索框 ``textChanged`` → 大小写不敏感子串过滤(匹配 ``var.key`` 或 ``var.label``)
- 数据来源:
  - :meth:`set_template_path` → 调 :func:`enumerate_vars` 重新枚举
  - :meth:`set_vars` → 直接灌入(用于单测 / 已枚举好的列表)
"""
from typing import List, Optional

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import (
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from inp_tool.i18n_gui import tg

from inp_tool_gui.widgets.sweep_var_combo import (
    VarSpec,
    enumerate_vars,
)


# --- 常量 ------------------------------------------------------------

# 用于标记 tree item 是否为 leaf (真正的 VarSpec 行)。
# group item (顶层) 的 leaf flag 为 False。
_LEAF_ROLE = Qt.UserRole + 1
# group item 的 user role 存 block 名("(枚举轴)" / "<top>" / 块名)
_GROUP_ROLE = Qt.UserRole + 2

# 三类 group 的命名
_GROUP_ENUM = "(枚举轴)"  # kind == "enum" 的轴归入此处
_GROUP_TOP = "<top>"      # block == "<top>" 的顶层语句归入此处
# 其他具体 block 名直接用 var.block


class VariableTreeWidget(QWidget):
    """展示 :func:`enumerate_vars` 结果的树形组件。"""

    # 双击 leaf → payload 是 VarSpec.key
    variable_picked = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._all_vars: List[VarSpec] = []
        self._filtered_vars: List[VarSpec] = []
        self._template_path: Optional[str] = None
        self._build_ui()

    # --- UI 构造 -------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # 搜索框(i18n 优先,fallback 到硬编码 zh 字符串)
        try:
            placeholder = tg("sweep.lbl.template")  # 不新增 key
        except Exception:
            placeholder = "搜索变量..."
        if not placeholder:
            placeholder = "搜索变量..."
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(placeholder)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        root.addWidget(self.search_edit)

        # 树
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["变量名", "类型"])
        self.tree.setColumnWidth(0, 320)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        # 双击触发拾取
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        # itemActivated 在键盘 Enter / 程序触发时也会 emit,用于测试
        self.tree.itemActivated.connect(self._on_item_activated)
        root.addWidget(self.tree, 1)

    # --- 公开 API -------------------------------------------------------

    def set_template_path(self, path: Optional[str]) -> None:
        """调 :func:`enumerate_vars(path)` 重新灌入。"""
        self._template_path = path
        self.set_vars(enumerate_vars(path))

    def set_vars(self, vars: List[VarSpec]) -> None:
        """直接灌入已枚举好的 :class:`VarSpec` 列表(用于单测 / 上游已枚举)。"""
        self._all_vars = list(vars) if vars else []
        self._rebuild_tree()

    # --- 内部:树构建 ---------------------------------------------------

    def _on_search_changed(self, _text: str) -> None:
        """搜索框变化 → 重新过滤并重建树。"""
        self._rebuild_tree()

    def _filtered(self) -> List[VarSpec]:
        """根据当前搜索框过滤 self._all_vars。"""
        needle = self.search_edit.text().strip().lower()
        if not needle:
            return list(self._all_vars)
        out: List[VarSpec] = []
        for v in self._all_vars:
            if needle in v.key.lower() or needle in v.label.lower():
                out.append(v)
        return out

    def _rebuild_tree(self) -> None:
        """(过滤 → 分组) 重建整棵树。"""
        self.tree.blockSignals(True)
        try:
            self.tree.clear()
            self._filtered_vars = self._filtered()
            if not self._filtered_vars:
                return

            # 分组:enum → "(枚举轴)";block=="<top>" 或空 → "<top>";其他 → 块名
            groups: "dict[str, List[VarSpec]]" = {}
            order: List[str] = []
            for v in self._filtered_vars:
                if v.kind == "enum":
                    gname = _GROUP_ENUM
                elif v.block == _GROUP_TOP or not v.block:
                    gname = _GROUP_TOP
                else:
                    gname = v.block
                if gname not in groups:
                    groups[gname] = []
                    order.append(gname)
                groups[gname].append(v)

            # 排序:
            #   1) (枚举轴)
            #   2) <top>
            #   3) 其他块名按字母序
            enum_keys: List[str] = []
            top_keys: List[str] = []
            other_keys: List[str] = []
            for gname in order:
                if gname == _GROUP_ENUM:
                    enum_keys.append(gname)
                elif gname == _GROUP_TOP:
                    top_keys.append(gname)
                else:
                    other_keys.append(gname)
            other_keys.sort()
            sorted_order = enum_keys + top_keys + other_keys

            for gname in sorted_order:
                group_item = QTreeWidgetItem([gname, ""])
                group_item.setData(0, _GROUP_ROLE, gname)
                group_item.setData(0, _LEAF_ROLE, False)
                group_item.setFlags(Qt.ItemIsEnabled)
                self.tree.addTopLevelItem(group_item)
                for v in groups[gname]:
                    child = QTreeWidgetItem([v.label, v.kind])
                    child.setData(0, Qt.UserRole, v.key)
                    child.setData(0, _LEAF_ROLE, True)
                    child.setToolTip(0, v.key)
                    child.setToolTip(1, v.kind)
                    group_item.addChild(child)
                group_item.setExpanded(True)
        finally:
            self.tree.blockSignals(False)

    # --- 内部:信号分发 -------------------------------------------------

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        """双击触发拾取(仅 leaf)。"""
        key = self._leaf_key(item)
        if key is not None:
            self.variable_picked.emit(key)

    def _on_item_activated(self, item: QTreeWidgetItem, _col: int) -> None:
        """键盘 Enter 或程序触发 activated 时也拾取(单测友好)。"""
        key = self._leaf_key(item)
        if key is not None:
            self.variable_picked.emit(key)

    @staticmethod
    def _leaf_key(item: Optional[QTreeWidgetItem]) -> Optional[str]:
        """取 leaf item 的 key;非 leaf 返回 None。"""
        if item is None:
            return None
        is_leaf = item.data(0, _LEAF_ROLE)
        if not is_leaf:
            return None
        return item.data(0, Qt.UserRole)
