"""``PostprocessPanel`` — CFD++ 后处理 GUI 面板。

只负责 UI 布局和信号槽接线;业务逻辑全部走
:class:`inp_tool_gui.controllers.postprocess_controller.PostprocessController`。

信号:
- :attr:`run_requested` — emit ``(action_name, params_dict)`` 当用户点击 action 按钮
  - ``action_name`` ∈ ``{"extract", "convergence", "report", "plot", "all"}``
  - ``params_dict``:case_dirs / sref / lref / ... / op
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Union

from PySide2.QtCore import Signal
from PySide2.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


# Spinbox 数值范围(避免 -inf/inf,但允许常见 CFD 量纲)
_GEOM_MIN = -1e6
_GEOM_MAX = 1e6
_GEOM_DECIMALS = 4


class PostprocessPanel(QWidget):
    """CFD++ 后处理面板。

    使用范式::

        panel = PostprocessPanel()
        panel.run_requested.connect(on_run)
        layout.addWidget(panel)

        # 编程添加 case 目录
        panel.add_case_dir(Path("/path/to/case_01"))
        panel.set_geometry(sref=1.0, lref=1.0)
        panel.set_op("1,2")
    """

    # action_name, params_dict
    run_requested = Signal(str, dict)

    def __init__(self, parent: Union[QWidget, None] = None) -> None:
        super().__init__(parent)
        self._case_dirs: List[Path] = []
        self._build_ui()

    # ----------------------------------------------------------------------
    # UI 构建
    # ----------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        # ---- 顶部:case 选择 ----
        case_box = QGroupBox("算例目录")
        case_layout = QVBoxLayout(case_box)
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("选目录...")
        self._add_btn.clicked.connect(self._on_add_case)
        self._clear_btn = QPushButton("清空")
        self._clear_btn.clicked.connect(self.clear_cases)
        self._case_label = QLabel("Cases: 0")
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._clear_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self._case_label)
        case_layout.addLayout(btn_row)

        self._case_list = QListWidget()
        case_layout.addWidget(self._case_list)
        outer.addWidget(case_box)

        # ---- 中部:几何 + op ----
        geom_box = QGroupBox("参考几何 & 积分 op")
        geom_layout = QFormLayout(geom_box)

        self._sref_spin = self._make_spin(1.0)
        self._lref_spin = self._make_spin(1.0)
        self._xref_spin = self._make_spin(0.0)
        self._yref_spin = self._make_spin(0.0)
        self._zref_spin = self._make_spin(0.0)
        self._xcg_spin = self._make_spin(0.0)
        self._op_edit = QLineEdit("1")
        self._op_edit.setPlaceholderText("如 '1' 或 '1,2,3'")

        geom_layout.addRow("Sref (m²):", self._sref_spin)
        geom_layout.addRow("Lref (m):", self._lref_spin)
        geom_layout.addRow("Xref (m):", self._xref_spin)
        geom_layout.addRow("Yref (m):", self._yref_spin)
        geom_layout.addRow("Zref (m):", self._zref_spin)
        geom_layout.addRow("Xcg (m):", self._xcg_spin)
        geom_layout.addRow("积分 op:", self._op_edit)
        outer.addWidget(geom_box)

        # ---- 5 action 按钮 ----
        action_row = QHBoxLayout()
        self._action_buttons: Dict[str, QPushButton] = {}
        for action, label in [
            ("extract", "提取力"),
            ("convergence", "收敛分析"),
            ("report", "Excel"),
            ("plot", "收敛图"),
            ("all", "全部"),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(self._make_action_handler(action))
            action_row.addWidget(btn)
            self._action_buttons[action] = btn
        outer.addLayout(action_row)

        # ---- 日志区 ----
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("操作日志...")
        outer.addWidget(self._log, stretch=1)

    def _make_spin(self, default: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(_GEOM_MIN, _GEOM_MAX)
        spin.setDecimals(_GEOM_DECIMALS)
        spin.setValue(default)
        spin.setSingleStep(0.1)
        return spin

    def _make_action_handler(self, action: str):
        def _handler():
            params = {
                "case_dirs": list(self._case_dirs),
                "op": self._op_edit.text(),
                "sref": self._sref_spin.value(),
                "lref": self._lref_spin.value(),
                "xref": self._xref_spin.value(),
                "yref": self._yref_spin.value(),
                "zref": self._zref_spin.value(),
                "xcg": self._xcg_spin.value(),
            }
            self.run_requested.emit(action, params)
        return _handler

    # ----------------------------------------------------------------------
    # 槽:文件对话框
    # ----------------------------------------------------------------------

    def _on_add_case(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择算例目录")
        if d:
            self.add_case_dir(Path(d))

    # ----------------------------------------------------------------------
    # 公共 API(编程接口,测试 + main_window 用)
    # ----------------------------------------------------------------------

    def add_case_dir(self, path: Union[str, Path]) -> None:
        """添加一个算例目录(去重)。"""
        p = Path(path)
        if p in self._case_dirs:
            return
        self._case_dirs.append(p)
        self._case_list.addItem(str(p))
        self._update_case_label()

    def get_case_dirs(self) -> List[Path]:
        """返回当前 case 目录列表副本。"""
        return list(self._case_dirs)

    def clear_cases(self) -> None:
        """清空 case 列表。"""
        self._case_dirs = []
        self._case_list.clear()
        self._update_case_label()

    def _update_case_label(self) -> None:
        self._case_label.setText(f"Cases: {len(self._case_dirs)}")

    def set_op(self, op: str) -> None:
        self._op_edit.setText(op)

    def get_op(self) -> str:
        return self._op_edit.text()

    def set_geometry(
        self,
        sref: Union[float, None] = None,
        lref: Union[float, None] = None,
        xref: Union[float, None] = None,
        yref: Union[float, None] = None,
        zref: Union[float, None] = None,
        xcg: Union[float, None] = None,
    ) -> None:
        """部分更新几何 spinbox 值。"""
        if sref is not None:
            self._sref_spin.setValue(float(sref))
        if lref is not None:
            self._lref_spin.setValue(float(lref))
        if xref is not None:
            self._xref_spin.setValue(float(xref))
        if yref is not None:
            self._yref_spin.setValue(float(yref))
        if zref is not None:
            self._zref_spin.setValue(float(zref))
        if xcg is not None:
            self._xcg_spin.setValue(float(xcg))

    def get_geometry(self) -> Dict[str, float]:
        """返回当前几何 spinbox 值字典。"""
        return {
            "sref": self._sref_spin.value(),
            "lref": self._lref_spin.value(),
            "xref": self._xref_spin.value(),
            "yref": self._yref_spin.value(),
            "zref": self._zref_spin.value(),
            "xcg": self._xcg_spin.value(),
        }

    def append_log(self, message: str) -> None:
        """追加一行日志到日志区。"""
        self._log.appendPlainText(str(message))

    def clear_log(self) -> None:
        """清空日志区。"""
        self._log.clear()
