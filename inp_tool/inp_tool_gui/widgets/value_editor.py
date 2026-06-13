"""ValueEditorDialog:单值编辑对话框(Phase 3)。

GUI 树形双击某 Stmt 的 value 单元格时弹出,接受用户修改,按原 typed 类型
(int / float / str / bool)做校验,通过后 :attr:`new_value` 返回推断后的新值。

校验失败时 **不** 关闭 dialog,用户可继续编辑(测试用 :meth:`result_accepted`
判定上次 accept() 是否真的成功)。

类型判定(优先级):
    bool > int > float > str
(``bool`` 是 ``int`` 子类,故须先判 bool。)

测试辅助方法: :meth:`set_text` / :meth:`type_label` / :meth:`findChild_text` /
:meth:`result_accepted` — 这些是公开 API,方便在 offscreen 环境驱动 line edit
而无需碰 private widget。
"""
from typing import Any, Optional

from PySide2.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


# CFD++ .inp 中 boolean 字段常用表示(大小写不敏感)
_BOOL_TRUE = {"t", "true", ".true.", "1"}
_BOOL_FALSE = {"f", "false", ".false.", "0"}


def _infer_kind(typed: Any) -> str:
    """按 typed 值推断 kind。优先级 bool > int > float > str。"""
    if isinstance(typed, bool):
        return "bool"
    if isinstance(typed, int):
        return "int"
    if isinstance(typed, float):
        return "float"
    return "str"


def _convert(text: str, kind: str) -> Optional[Any]:
    """按 kind 把 text 转成 typed 值;失败返回 None。"""
    s = text.strip()
    if kind == "int":
        try:
            return int(s)
        except ValueError:
            return None
    if kind == "float":
        try:
            s_norm = s.replace("d", "e").replace("D", "E")
            return float(s_norm)
        except ValueError:
            return None
    if kind == "bool":
        low = s.lower()
        if low in _BOOL_TRUE:
            return True
        if low in _BOOL_FALSE:
            return False
        return None
    # str:任何 strip 后的文本都接受(空串也允许,语义上等于 "")
    return s


class ValueEditorDialog(QDialog):
    """单值编辑对话框。"""

    def __init__(
        self,
        current_raw: str,
        current_typed: Any,
        parent: Optional[QDialog] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑值")
        self.setModal(True)

        self._kind: str = _infer_kind(current_typed)
        self._new_value: Any = None
        self._accepted: bool = False

        # --- UI 布局 -----------------------------------------------------
        layout = QVBoxLayout(self)

        self._type_lbl = QLabel(f"类型: {self._kind}", self)
        layout.addWidget(self._type_lbl)

        self._edit = QLineEdit(str(current_raw), self)
        self._edit.selectAll()
        layout.addWidget(self._edit)

        self._error_lbl = QLabel("", self)
        self._error_lbl.setStyleSheet("color: #c00;")
        self._error_lbl.setVisible(False)
        layout.addWidget(self._error_lbl)

        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        btns.accepted.connect(self.accept)  # 触发重写的 accept(),走校验
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._edit.setFocus()

    # --- 公开 API -------------------------------------------------------

    @property
    def new_value(self) -> Any:
        """最近一次成功 accept() 的推断 typed 值;未成功或 reject 返 None。"""
        return self._new_value

    # --- 测试辅助(也是 widget 自己的合法操作入口) --------------------

    def set_text(self, text: str) -> None:
        """直接设 line edit 文本(测试与外部调用)。"""
        self._edit.setText(text)

    def type_label(self) -> str:
        """返回 kind 标签(int / float / str / bool)。"""
        return self._kind

    def findChild_text(self) -> str:
        """返回 line edit 当前文本。"""
        return self._edit.text()

    def result_accepted(self) -> bool:
        """最近一次 accept() 是否通过校验并真正接受。"""
        return self._accepted

    # --- 槽 ----------------------------------------------------------

    def accept(self) -> None:
        """重写 accept:校验通过才真正关闭 dialog,失败则保持打开 + 显示错误标签。

        这样无论是 :class:`QDialogButtonBox` OK 按钮触发,还是测试代码直接调
        :meth:`accept`,都走同一条校验路径。

        注意:不在这里用模态 ``QMessageBox.warning`` — 那会在单元测试 / 自动化
        里阻塞事件循环。改为就地更新错误标签,视觉反馈足够且不阻塞。
        """
        text = self._edit.text()
        converted = _convert(text, self._kind)
        if converted is None and self._kind in ("int", "float", "bool"):
            self._error_lbl.setText(f"⚠ {text!r} 不是合法的 {self._kind}")
            self._error_lbl.setVisible(True)
            return  # 不关 dialog,保持打开
        # 校验通过 → 接受
        self._error_lbl.setVisible(False)
        self._new_value = converted
        self._accepted = True
        super().accept()