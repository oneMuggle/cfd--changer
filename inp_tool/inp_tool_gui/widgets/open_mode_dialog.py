# inp_tool/inp_tool_gui/widgets/open_mode_dialog.py
"""OpenModeDialog:选择打开方式的弹窗(文件/文件夹)。

默认 folder 模式。
"""
from enum import Enum
from typing import Optional

from PySide2.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from inp_tool.i18n_gui import tg


class Mode(str, Enum):
    FILE = "file"
    FOLDER = "folder"


class OpenModeDialog(QDialog):
    """打开方式选择弹窗。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tg("open_mode.title"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tg("open_mode.label"), self))

        self._radio_file = QRadioButton(tg("open_mode.file_radio"), self)
        self._radio_folder = QRadioButton(tg("open_mode.folder_radio"), self)
        self._radio_folder.setChecked(True)
        layout.addWidget(self._radio_file)
        layout.addWidget(self._radio_folder)

        self._hint = QLabel(tg("open_mode.folder_hint"), self)
        self._hint.setStyleSheet("color: gray;")
        layout.addWidget(self._hint)

        self._chk_remember = QCheckBox(tg("open_mode.remember"), self)
        layout.addWidget(self._chk_remember)

        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        btns.button(QDialogButtonBox.Ok).setText(tg("open_mode.ok"))
        btns.button(QDialogButtonBox.Cancel).setText(tg("open_mode.cancel"))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_mode(self) -> Mode:
        return Mode.FOLDER if self._radio_folder.isChecked() else Mode.FILE

    def remember_choice(self) -> bool:
        return self._chk_remember.isChecked()
