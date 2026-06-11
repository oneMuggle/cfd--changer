"""EditController:GUI 编辑操作业务逻辑(undo / redo / dirty 标志)。

包装 :class:`FileController`,在改动值时自动记录 undo 栈。

**不**依赖 PySide2,纯 Python;widget 层只调此 controller。
"""
from dataclasses import dataclass
from typing import Any, List, Optional

from inp_tool_gui.controllers.file_controller import FileController


@dataclass
class UndoEntry:
    """一次字段修改的快照(用于 undo/redo)。"""

    block_name: str
    keyword: str
    old_value: Any
    new_value: Any
    block_idx: int = 0


class EditController:
    """GUI 的编辑控制器,绑到一个 :class:`FileController`。"""

    def __init__(self, file_ctrl: FileController) -> None:
        self._file_ctrl = file_ctrl
        self._undo_stack: List[UndoEntry] = []
        self._redo_stack: List[UndoEntry] = []
        self._is_dirty: bool = False

    # --- 状态查询 --------------------------------------------------------

    @property
    def is_dirty(self) -> bool:
        """是否有未保存的修改。"""
        return self._is_dirty

    @property
    def can_undo(self) -> bool:
        """undo 栈非空。"""
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        """redo 栈非空。"""
        return bool(self._redo_stack)

    @property
    def undo_depth(self) -> int:
        """undo 栈深度(供 UI 显示)。"""
        return len(self._undo_stack)

    @property
    def redo_depth(self) -> int:
        """redo 栈深度(供 UI 显示)。"""
        return len(self._redo_stack)

    # --- 修改 -----------------------------------------------------------

    def set_value(
        self,
        block_name: str,
        keyword: str,
        new_value: Any,
        *,
        block_idx: int = 0,
    ) -> bool:
        """改值,推 undo entry,标 dirty,清 redo 栈。

        block 不存在返回 :data:`False`(不推 undo、不标 dirty)。
        """
        old_value = self._file_ctrl.get_value(
            block_name, keyword, block_idx=block_idx
        )
        ok = self._file_ctrl.set_value(
            block_name, keyword, new_value, block_idx=block_idx
        )
        if not ok:
            return False
        self._undo_stack.append(
            UndoEntry(
                block_name=block_name,
                keyword=keyword,
                old_value=old_value,
                new_value=new_value,
                block_idx=block_idx,
            )
        )
        # 标准 undo/redo 行为:新操作清空 redo 栈
        self._redo_stack.clear()
        self._is_dirty = True
        return True

    # --- undo / redo ----------------------------------------------------

    def undo(self) -> Optional[UndoEntry]:
        """撤销最近一次 :meth:`set_value`,返回 :class:`UndoEntry`(供 UI 提示)。

        undo 栈空时返回 :data:`None`。
        """
        if not self._undo_stack:
            return None
        entry = self._undo_stack.pop()
        # 恢复旧值 — 不走 set_value(否则会推 undo,无限循环)
        self._file_ctrl.set_value(
            entry.block_name,
            entry.keyword,
            entry.old_value,
            block_idx=entry.block_idx,
        )
        self._redo_stack.append(entry)
        return entry

    def redo(self) -> Optional[UndoEntry]:
        """重做最近一次 :meth:`undo`,返回 :class:`UndoEntry`。

        redo 栈空时返回 :data:`None`。
        """
        if not self._redo_stack:
            return None
        entry = self._redo_stack.pop()
        self._file_ctrl.set_value(
            entry.block_name,
            entry.keyword,
            entry.new_value,
            block_idx=entry.block_idx,
        )
        self._undo_stack.append(entry)
        return entry

    # --- dirty 标志管理 -------------------------------------------------

    def mark_clean(self) -> None:
        """保存成功后调用,清 dirty 标志。"""
        self._is_dirty = False
