"""DetectPanel:检测报告 + Preset 应用面板(v0.13 升级版)。

UI 结构(自顶向下):
- 顶部按钮:``运行检测`` + 3 个 Preset 按钮(SST k-ω / 双温度 / 多组分)
- 摘要标签:DetectController.last_report.summary_zh()(v0.13 透传 EquationSystemReport)
- 检测报告表(QFormLayout,9 字段):
  - **新(v0.13)**:能量 / 湍流 / 气体 / 物种数(从 EquationSystemReport enum)
  - **旧(v0.12)**:参考温度 reftem / 雷诺数 reynolds / 湍流关键字 / chemistry 块 / 双温度(2T)
- **警告区 v0.13 双拆分**:
  - ``方程检测告警``(notes 字段,自身一致性)
  - ``Sweep Axis 告警``(sweeps_equation_warnings,wizard step_4b/4c 不兼容项)
- 推荐字段区:每行 ``(block, keyword) → value / 备注`` + "应用"按钮
"""
from typing import Optional

from PySide2.QtCore import Signal
from PySide2.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from inp_tool.model import InpFile

from inp_tool_gui.controllers.detect_controller import (
    DetectController,
    DetectionReport,
)
from inp_tool_gui.controllers.edit_controller import EditController


class DetectPanel(QWidget):
    """检测报告面板(v0.13 升级)。"""

    # emit: 用户点了 Preset 按钮(preset_name: "turb" | "2t" | "species")
    preset_requested = Signal(str)

    def __init__(
        self,
        detect_ctrl: DetectController,
        edit_ctrl: EditController,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._detect_ctrl = detect_ctrl
        self._edit_ctrl = edit_ctrl
        self._inp: Optional[InpFile] = None

        self._build_ui()

    # --- 公开 API -------------------------------------------------------

    def run(
        self,
        inp: InpFile,
        *,
        intended_axes: Optional[dict] = None,
    ) -> DetectionReport:
        """跑检测并刷新面板。

        ``intended_axes``(v0.11.0+):wizard step_4b/4c 选的 axis 值;
        不传则只做单纯方程检测(无 axis 兼容告警)。
        """
        self._inp = inp
        rep = self._detect_ctrl.run(inp, intended_axes=intended_axes)
        self._refresh(rep)
        return rep

    def current_inp(self) -> Optional[InpFile]:
        return self._inp

    # --- UI 构建 -------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 顶部按钮行
        btn_row = QHBoxLayout()
        self._btn_run = QPushButton("运行检测", self)
        self._btn_run.clicked.connect(self._on_run_clicked)
        btn_row.addWidget(self._btn_run)

        self._btn_preset_turb = QPushButton("应用 SST k-ω", self)
        self._btn_preset_turb.clicked.connect(lambda: self.preset_requested.emit("turb"))
        btn_row.addWidget(self._btn_preset_turb)

        self._btn_preset_2t = QPushButton("应用 双温度(2T)", self)
        self._btn_preset_2t.clicked.connect(lambda: self.preset_requested.emit("2t"))
        btn_row.addWidget(self._btn_preset_2t)

        self._btn_preset_species = QPushButton("应用 多组分", self)
        self._btn_preset_species.clicked.connect(
            lambda: self.preset_requested.emit("species")
        )
        btn_row.addWidget(self._btn_preset_species)

        btn_row.addStretch(1)
        root.addLayout(btn_row)

        # 摘要标签
        self._summary_lbl = QLabel("尚未运行检测", self)
        self._summary_lbl.setStyleSheet("font-weight: bold; padding: 6px;")
        root.addWidget(self._summary_lbl)

        # 检测报告区(v0.13:9 字段)
        report_box = QGroupBox("检测报告", self)
        report_layout = QFormLayout(report_box)
        # v0.13 新增:能量 / 湍流 / 气体 / 物种数
        self._lbl_energy = QLabel("-", report_box)
        self._lbl_turbulence_model = QLabel("-", report_box)
        self._lbl_gas = QLabel("-", report_box)
        self._lbl_n_species = QLabel("-", report_box)
        report_layout.addRow("能量(EnergyModel):", self._lbl_energy)
        report_layout.addRow("湍流(TurbulenceModel):", self._lbl_turbulence_model)
        report_layout.addRow("气体(GasModel):", self._lbl_gas)
        report_layout.addRow("物种数:", self._lbl_n_species)
        # v0.12 兼容字段
        self._lbl_reftem = QLabel("-", report_box)
        self._lbl_reynolds = QLabel("-", report_box)
        self._lbl_turb = QLabel("-", report_box)
        self._lbl_chem = QLabel("-", report_box)
        self._lbl_2t = QLabel("-", report_box)
        report_layout.addRow("参考温度 reftem:", self._lbl_reftem)
        report_layout.addRow("雷诺数 reynolds:", self._lbl_reynolds)
        report_layout.addRow("湍流关键字:", self._lbl_turb)
        report_layout.addRow("chemistry 块:", self._lbl_chem)
        report_layout.addRow("双温度(2T):", self._lbl_2t)
        root.addWidget(report_box)

        # 警告区 v0.13:双拆分
        warn_box = QGroupBox("方程检测告警(notes)", self)
        warn_layout = QVBoxLayout(warn_box)
        self._notes_view = QTextEdit(warn_box)
        self._notes_view.setReadOnly(True)
        self._notes_view.setMaximumHeight(100)
        warn_layout.addWidget(self._notes_view)
        root.addWidget(warn_box)

        sweep_warn_box = QGroupBox("Sweep Axis 告警(v0.13)", self)
        sweep_warn_layout = QVBoxLayout(sweep_warn_box)
        self._sweep_warn_view = QTextEdit(sweep_warn_box)
        self._sweep_warn_view.setReadOnly(True)
        self._sweep_warn_view.setMaximumHeight(100)
        sweep_warn_layout.addWidget(self._sweep_warn_view)
        root.addWidget(sweep_warn_box)

        # 推荐字段区
        rec_box = QGroupBox("推荐字段", self)
        outer = QVBoxLayout(rec_box)
        rec_holder = QWidget(rec_box)
        self._rec_layout = QFormLayout(rec_holder)
        rec_holder.setLayout(self._rec_layout)
        scroll = QScrollArea(rec_box)
        scroll.setWidget(rec_holder)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        root.addWidget(rec_box, 1)  # stretch

    # --- 刷新 ---------------------------------------------------------

    def _refresh(self, rep: DetectionReport) -> None:
        self._summary_lbl.setText(rep.summary_zh())
        # v0.13 新字段
        self._lbl_energy.setText(str(rep.energy_model.value))
        self._lbl_turbulence_model.setText(str(rep.turbulence_model.value))
        self._lbl_gas.setText(str(rep.gas_model.value))
        self._lbl_n_species.setText(str(rep.n_species))
        # v0.12 兼容
        self._lbl_reftem.setText("✓" if rep.has_reftem else "✗")
        self._lbl_reynolds.setText("✓" if rep.has_reynolds else "✗")
        self._lbl_turb.setText(
            ", ".join(rep.turb_keywords) if rep.turb_keywords else "✗"
        )
        self._lbl_chem.setText(str(rep.chemistry_blocks) if rep.has_chemistry else "✗")
        self._lbl_2t.setText("✓" if rep.is_two_temperature else "✗")

        # 警告 v0.13:双拆分
        if rep.notes:
            self._notes_view.setPlainText("\n".join("• " + n for n in rep.notes))
        else:
            self._notes_view.setPlainText("(无)")

        if rep.sweeps_equation_warnings:
            self._sweep_warn_view.setPlainText(
                "\n".join("⚠ " + w for w in rep.sweeps_equation_warnings)
            )
        else:
            self._sweep_warn_view.setPlainText("(无)")

        # 推荐字段列表
        self._clear_rec_layout()
        if not rep.recommended_fields:
            self._rec_layout.addRow(QLabel("(无推荐字段 — 关键字段已齐备)"))
            return
        for block_name, keyword, value, note in rep.recommended_fields:
            row_lbl = QLabel(f"{block_name}.{keyword} = {value}", self)
            note_lbl = QLabel(note, self)
            apply_btn = QPushButton("应用", self)
            apply_btn.clicked.connect(
                lambda _checked=False, b=block_name, k=keyword, v=value:
                self._apply_recommended(b, k, v)
            )
            row = QHBoxLayout()
            row.addWidget(row_lbl)
            row.addWidget(apply_btn)
            row.addStretch(1)
            wrap = QWidget(self)
            wrap.setLayout(row)
            self._rec_layout.addRow(wrap, note_lbl)

    def _clear_rec_layout(self) -> None:
        while self._rec_layout.rowCount() > 0:
            self._rec_layout.removeRow(0)

    # --- 槽 ----------------------------------------------------------

    def _on_run_clicked(self) -> None:
        if self._inp is None:
            return
        self.run(self._inp)

    def _apply_recommended(self, block_name: str, keyword: str, value: object) -> None:
        """应用一个推荐字段(走 EditController → 进 undo 栈)。"""
        self._edit_ctrl.set_value(block_name, keyword, value)