"""InpTreeWidget:树形展示 :class:`inp_tool.model.InpFile`(Phase 3)。

层级结构(3 层)::

    Root
    ├── 顶层语句
    │   ├── title        (stmt)
    │   │   ├── value[0] "Hello"
    │   │   └── value[1] "..."
    │   └── runtype
    │       └── value[0] "default"
    └── 块
        ├── physics      (block, block_idx=0)
        │   ├── reftem
        │   │   └── value[0] "300.0"
        │   └── reynolds
        │       └── value[0] "1.0e6"
        └── chemistry [1] (block, block_idx=1,同名第 2 个)
            └── model
                └── value[0] "air7"

双击 value 单元格 → 触发 :attr:`value_edit_requested` 信号,
由 :class:`MainWindow` 接收 → 弹 :class:`ValueEditorDialog` → 改值 → 局部刷新。

Item 数据约定(``Qt.UserRole``):
    - 顶层父节点: ``("parent", "top"|"blocks")``
    - block item: ``("block", block_idx, block_name)``
    - stmt item: ``("stmt", block_idx, stmt_idx, keyword)``
      (``block_idx = -1`` 表示顶层语句)
    - value item: ``("value", block_idx, stmt_idx, value_idx, keyword)``
"""
from typing import Any, List, Optional, Tuple

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QTreeWidget, QTreeWidgetItem

from inp_tool.model import InpFile


# --- 数据 role 辅助 ----------------------------------------------------


_PARENT_ROLE = "parent"
_BLOCK_ROLE = "block"
_STMT_ROLE = "stmt"
_VALUE_ROLE = "value"


class InpTreeWidget(QTreeWidget):
    """树形展示 InpFile。"""

    # signal: (block_idx, keyword, value_idx)
    # block_idx = -1 表示顶层语句
    value_edit_requested = Signal(int, str, int)

    def __init__(self, parent: Optional[QTreeWidget] = None) -> None:
        super().__init__(parent)
        self.setHeaderLabels(["字段", "类型", "值"])
        self.setColumnWidth(0, 280)
        self.setColumnWidth(1, 60)
        self.setAlternatingRowColors(True)

        # 信号 → emit value_edit_requested
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

        self._inp: Optional[InpFile] = None

    # --- 公开 API -------------------------------------------------------

    def populate(self, inp: InpFile) -> None:
        """用 ``inp`` 重建整棵树。"""
        self.clear()
        self._inp = inp

        # 顶层语句父节点
        top_parent = QTreeWidgetItem([self._LBL_TOP])
        top_parent.setData(0, Qt.UserRole, (_PARENT_ROLE, "top"))
        self.addTopLevelItem(top_parent)
        for stmt_idx, stmt in enumerate(inp.top_stmts):
            stmt_item = self._make_stmt_item(-1, stmt_idx, stmt.keyword)
            top_parent.addChild(stmt_item)
            for vi, v in enumerate(stmt.values):
                stmt_item.addChild(self._make_value_item(-1, stmt_idx, vi, stmt.keyword, v))

        # 块父节点
        blk_parent = QTreeWidgetItem([self._LBL_BLOCKS])
        blk_parent.setData(0, Qt.UserRole, (_PARENT_ROLE, "blocks"))
        self.addTopLevelItem(blk_parent)
        for blk_idx, block in enumerate(inp.block_list):
            label = self._block_label(blk_idx, block.name)
            blk_item = QTreeWidgetItem([label])
            blk_item.setData(0, Qt.UserRole, (_BLOCK_ROLE, blk_idx, block.name))
            blk_parent.addChild(blk_item)
            for stmt_idx, stmt in enumerate(block.statements):
                stmt_item = self._make_stmt_item(blk_idx, stmt_idx, stmt.keyword)
                blk_item.addChild(stmt_item)
                for vi, v in enumerate(stmt.values):
                    stmt_item.addChild(
                        self._make_value_item(blk_idx, stmt_idx, vi, stmt.keyword, v)
                    )

        # 展开前两层(便于浏览)
        self.expandAll()

    def request_edit(self, item: QTreeWidgetItem) -> None:
        """外部代码(测试 / MainWindow)显式触发某 item 的编辑请求。

        仅 value item 会 emit 信号;其他 item 静默忽略。
        """
        meta = item.data(0, Qt.UserRole)
        if not meta or meta[0] != _VALUE_ROLE:
            return
        # meta = ("value", block_idx, stmt_idx, value_idx, keyword)
        _, block_idx, _stmt_idx, value_idx, keyword = meta
        self.value_edit_requested.emit(int(block_idx), str(keyword), int(value_idx))

    def refresh_value(
        self,
        parent_label: str,
        keyword: str,
        value_idx: int,
    ) -> None:
        """刷新指定 value 的显示文本(不改 tree 结构)。"""
        item = self.find_value_item(parent_label, keyword, value_idx)
        if item is None:
            return
        meta = self._locate(parent_label, keyword, value_idx)
        if meta is None:
            return
        block_idx, stmt_idx, vi, _kw = meta
        if block_idx == -1:
            stmt = self._inp.top_stmts[stmt_idx]
        else:
            stmt = self._inp.block_list[block_idx].statements[stmt_idx]
        item.setText(0, stmt.values[vi].raw)
        item.setText(2, stmt.values[vi].raw)

    # --- 测试辅助(也是合理外部调用入口) ------------------------------

    def top_level_labels(self) -> List[str]:
        """顶层节点标签列表。"""
        return [self.topLevelItem(i).text(0) for i in range(self.topLevelItemCount())]

    def child_count(self, parent_label: str) -> int:
        """按 label 找顶层父节点,返其子项数。"""
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            if top.text(0) == parent_label:
                return top.childCount()
        # 也搜顶层 block(label 直接在顶层 items)
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            for j in range(top.childCount()):
                if top.child(j).text(0) == parent_label:
                    return top.child(j).childCount()
        return 0

    def find_value_item(
        self,
        parent_label: str,
        stmt_keyword: str,
        value_idx: int,
    ) -> Optional[QTreeWidgetItem]:
        """按 ``(parent_label, stmt_keyword, value_idx)`` 找 value item。"""
        meta = self._locate(parent_label, stmt_keyword, value_idx)
        if meta is None:
            return None
        block_idx, stmt_idx, vi, _kw = meta
        return self._walk_to_value_item(block_idx, stmt_idx, vi)

    # --- 内部 ---------------------------------------------------------

    _LBL_TOP = "顶层语句"
    _LBL_BLOCKS = "块"

    def _block_label(self, blk_idx: int, name: str) -> str:
        """同名 block 第 2+ 个加 `` [N]`` 后缀(0-indexed,与 list_idx 一致)。"""
        if self._inp is None:
            return name
        total = self._count_blocks_with_name(name)
        if total == 1:
            return name
        return f"{name} [{blk_idx}]"

    def _count_blocks_with_name(self, name: str) -> int:
        if self._inp is None:
            return 0
        return sum(1 for b in self._inp.block_list if b.name == name)

    def _make_stmt_item(self, block_idx: int, stmt_idx: int, keyword: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([keyword, "stmt", ""])
        item.setData(0, Qt.UserRole, (_STMT_ROLE, block_idx, stmt_idx, keyword))
        return item

    def _make_value_item(
        self,
        block_idx: int,
        stmt_idx: int,
        value_idx: int,
        keyword: str,
        value: Any,
    ) -> QTreeWidgetItem:
        raw = getattr(value, "raw", str(value))
        item = QTreeWidgetItem([raw, "value", raw])
        item.setData(
            0,
            Qt.UserRole,
            (_VALUE_ROLE, block_idx, stmt_idx, value_idx, keyword),
        )
        return item

    def _walk_to_value_item(
        self, block_idx: int, stmt_idx: int, value_idx: int
    ) -> Optional[QTreeWidgetItem]:
        """从顶层按 (block_idx, stmt_idx, value_idx) 走到 value item。"""
        # block_idx = -1 → 顶层语句;否则 → 块
        if block_idx == -1:
            top = self._find_top_by_label(self._LBL_TOP)
            if top is None:
                return None
            stmt_item = top.child(stmt_idx)
            if stmt_item is None:
                return None
            return stmt_item.child(value_idx)
        blk_parent = self._find_top_by_label(self._LBL_BLOCKS)
        if blk_parent is None:
            return None
        # block 在 blk_parent 第 blk_idx 个 child
        blk_item = blk_parent.child(block_idx)
        if blk_item is None:
            return None
        stmt_item = blk_item.child(stmt_idx)
        if stmt_item is None:
            return None
        return stmt_item.child(value_idx)

    def _find_top_by_label(self, label: str) -> Optional[QTreeWidgetItem]:
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            if top.text(0) == label:
                return top
        return None

    def _locate(
        self, parent_label: str, keyword: str, value_idx: int
    ) -> Optional[Tuple[int, int, int, str]]:
        """根据 parent_label + keyword + value_idx 反查 (block_idx, stmt_idx, vi, keyword)。

        parent_label 可以是:
          - ``"顶层语句"`` → block_idx = -1
          - ``"<block_name>"`` 或 ``"<block_name> [N]"`` → block_idx = N 或第一个同名
        """
        if self._inp is None:
            return None
        if parent_label == self._LBL_TOP:
            for stmt_idx, stmt in enumerate(self._inp.top_stmts):
                if stmt.keyword == keyword and value_idx < len(stmt.values):
                    return (-1, stmt_idx, value_idx, keyword)
            return None
        # block label 解析
        block_idx = self._parse_block_label(parent_label)
        if block_idx is None or block_idx >= len(self._inp.block_list):
            return None
        block = self._inp.block_list[block_idx]
        for stmt_idx, stmt in enumerate(block.statements):
            if stmt.keyword == keyword and value_idx < len(stmt.values):
                return (block_idx, stmt_idx, value_idx, keyword)
        return None

    def _parse_block_label(self, label: str) -> Optional[int]:
        """``physics`` → 0 (第一个 physics);``chemistry [1]`` → 1。"""
        if self._inp is None:
            return None
        if " [" in label and label.endswith("]"):
            name, idx_s = label.rsplit(" [", 1)
            try:
                idx = int(idx_s[:-1])
                if 0 <= idx < len(self._inp.block_list):
                    if self._inp.block_list[idx].name == name:
                        return idx
            except ValueError:
                pass
            return None
        # 无后缀 → 找第一个同名 block
        for i, b in enumerate(self._inp.block_list):
            if b.name == label:
                return i
        return None

    # --- 槽 ----------------------------------------------------------

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        self.request_edit(item)