"""PresetDialog:3 类 Preset 通用应用对话框(Phase 4)。

v0.9.1 完整版未上线,当前为简化版:

- ``PresetDialog(preset_name, edit_ctrl, parent=None)``
- 构造时按 ``preset_name`` 加载内置的"写入操作"列表 (block, keyword, value)
- accept → 调 :meth:`EditController.set_value` 批量写入(走 undo 栈)
- reject → 无操作

3 类 preset 当前实现的写入:
- ``turb`` (SST k-ω):reynolds=1e6 / turbi=0.01 / turbk=0.01 / turbw=0.01
- ``2t`` (双温度):reftem=300 / vibtem=300 / turbe=0
- ``species`` (多组分):占位(待 v0.9.1 SpeciesPreset.apply)

v0.9.1 上线后,本对话框直接调 ``TurbulenceKOmegaPreset.apply(inp)`` 等高层 API,
不再手写写入逻辑。
"""
from typing import Any, List, Optional, Tuple

from PySide2.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)

from inp_tool_gui.controllers.edit_controller import EditController


# 内置 preset 的写入操作(每条 = (block_name, keyword, value, note))
_PRESETS: dict = {
    "turb": [
        ("physics", "reynolds", 1.0e6, "SST k-ω 默认雷诺数"),
        ("physics", "turbi", 0.01, "湍流强度 I"),
        ("physics", "turbk", 0.01, "湍流长度尺度 L"),
        ("physics", "turbw", 0.01, "湍流频率 ω"),
    ],
    "2t": [
        ("physics", "reftem", 300.0, "参考温度"),
        ("physics", "vibtem", 300.0, "振动温度(2T)"),
        ("physics", "turbe", 0, "关闭湍流额外项"),
    ],
    "species": [
        # species preset 当前只是占位(追加 chemistry block 涉及 Block.append)
        # v0.9.1 上线后改为 SpeciesPreset.apply(inp)
    ],
}


class PresetDialog(QDialog):
    """通用 Preset 应用对话框。"""

    def __init__(
        self,
        preset_name: str,
        edit_ctrl: EditController,
        parent: Optional[QDialog] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"应用 Preset: {preset_name}")
        self.setModal(True)

        if preset_name not in _PRESETS:
            raise ValueError(f"未知 preset: {preset_name}")
        self._preset_name = preset_name
        self._ops: List[Tuple[str, str, Any, str]] = list(_PRESETS[preset_name])
        self._edit_ctrl = edit_ctrl
        self._applied = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"即将写入以下字段({len(self._ops)} 条):", self))
        self._ops_view = QTextEdit(self)
        self._ops_view.setReadOnly(True)
        self._ops_view.setPlainText(self._format_ops())
        layout.addWidget(self._ops_view)

        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _format_ops(self) -> str:
        lines = []
        for b, k, v, note in self._ops:
            lines.append(f"  • {b}.{k} = {v!r}  ({note})")
        return "\n".join(lines) if lines else "(无写入操作 — 此 preset 为占位)"

    def accept(self) -> None:
        """应用所有 ops,然后关闭。"""
        for block_name, keyword, value, _note in self._ops:
            self._edit_ctrl.set_value(block_name, keyword, value)
        self._applied = True
        super().accept()

    @property
    def applied(self) -> bool:
        """是否 accept 时执行了写入。"""
        return self._applied

    @property
    def op_count(self) -> int:
        """要执行的写入操作数。"""
        return len(self._ops)