"""SweepForm:批量算例生成表单(Phase 5)。

UI 结构:
- 顶部按钮:``加载 YAML...`` / ``加载 JSON...`` / ``运行(Dry)`` / ``运行`` / ``强制覆盖``
- 配置标签:模板路径 / 输出目录 / 命名模式 / case 数
- 结果表:QTableWidget 列出 CaseResult(case_id / path / 关键参数)

简化版(等 QThread 上线):
- 不在 QThread 后台跑,直接同步调 ``SweepController.run()``
- case 数 ≤ 100 时同步执行仍是 ms 级,可接受
- 后续可加 QThread + signal result_ready(plan §5.6)
"""
from typing import Optional

from PySide2.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from inp_tool_gui.controllers.sweep_controller import SweepController


class SweepForm(QWidget):
    """Sweep 配置表单 + 运行 + 结果展示。"""

    def __init__(
        self,
        sweep_ctrl: SweepController,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._sweep_ctrl = sweep_ctrl

        root = QVBoxLayout(self)

        # 顶部按钮行
        btn_row = QHBoxLayout()
        self._btn_yaml = QPushButton("加载 YAML...", self)
        self._btn_yaml.clicked.connect(self._pick_yaml)
        btn_row.addWidget(self._btn_yaml)

        self._btn_json = QPushButton("加载 JSON...", self)
        self._btn_json.clicked.connect(self._pick_json)
        btn_row.addWidget(self._btn_json)

        self._btn_run_dry = QPushButton("运行(Dry)", self)
        self._btn_run_dry.clicked.connect(lambda: self._on_run(dry=True))
        btn_row.addWidget(self._btn_run_dry)

        self._btn_run = QPushButton("运行", self)
        self._btn_run.clicked.connect(lambda: self._on_run(dry=False))
        btn_row.addWidget(self._btn_run)

        self._chk_force = QCheckBox("强制覆盖", self)
        btn_row.addWidget(self._chk_force)

        btn_row.addStretch(1)
        root.addLayout(btn_row)

        # 配置区
        cfg_box = QGroupBox("当前配置", self)
        cfg_layout = QFormLayout(cfg_box)
        self._lbl_tpl = QLabel("(未加载)", cfg_box)
        self._lbl_out = QLabel("(未加载)", cfg_box)
        self._lbl_naming = QLabel("(未加载)", cfg_box)
        self._lbl_cases = QLabel("0", cfg_box)
        cfg_layout.addRow("模板:", self._lbl_tpl)
        cfg_layout.addRow("输出目录:", self._lbl_out)
        cfg_layout.addRow("命名:", self._lbl_naming)
        cfg_layout.addRow("case 数:", self._lbl_cases)
        root.addWidget(cfg_box)

        # 结果表
        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(["case_id", "path", "params", "applied"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table, 1)

        self._refresh()

    # --- 公开 API -------------------------------------------------------

    def load_yaml(self, path: str) -> None:
        """外部直接 load YAML(供集成测试 / 拖拽)。"""
        try:
            self._sweep_ctrl.load_from_yaml(path)
        except Exception as exc:
            QMessageBox.critical(self, "加载失败", f"无法解析 YAML:\n{exc}")
            return
        self._refresh()

    def load_json(self, path: str) -> None:
        """外部直接 load JSON。"""
        try:
            self._sweep_ctrl.load_from_json(path)
        except Exception as exc:
            QMessageBox.critical(self, "加载失败", f"无法解析 JSON:\n{exc}")
            return
        self._refresh()

    def run_sync(self, *, dry: bool = False, force: bool = False) -> None:
        """同步跑 sweep 并刷新表(供测试 / 简化入口)。"""
        self._on_run(dry=dry, force=force)

    # --- 内部 ---------------------------------------------------------

    def _refresh(self) -> None:
        ctrl = self._sweep_ctrl
        self._lbl_tpl.setText(ctrl.template or "(未加载)")
        self._lbl_out.setText("(略)" if ctrl.is_loaded else "(未加载)")
        self._lbl_naming.setText("(略)" if ctrl.is_loaded else "(未加载)")
        self._lbl_cases.setText(str(ctrl.case_count) if ctrl.is_loaded else "0")
        self._btn_run_dry.setEnabled(ctrl.is_loaded)
        self._btn_run.setEnabled(ctrl.is_loaded)
        self._refresh_table()

    def _refresh_table(self) -> None:
        report = self._sweep_ctrl.last_report
        if report is None:
            self._table.setRowCount(0)
            return
        cases = report.cases
        self._table.setRowCount(len(cases))
        for row, c in enumerate(cases):
            self._table.setItem(row, 0, QTableWidgetItem(c.case_id))
            self._table.setItem(row, 1, QTableWidgetItem(c.path))
            self._table.setItem(row, 2, QTableWidgetItem(str(c.params)))
            self._table.setItem(row, 3, QTableWidgetItem(str(c.applied)))

    # --- 槽 ----------------------------------------------------------

    def _pick_yaml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选 sweep YAML", "", "YAML (*.yaml *.yml);;所有文件 (*)"
        )
        if not path:
            return
        self.load_yaml(path)

    def _pick_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选 sweep JSON", "", "JSON (*.json);;所有文件 (*)"
        )
        if not path:
            return
        self.load_json(path)

    def _on_run(self, dry: bool, force: bool = False) -> None:
        if not self._sweep_ctrl.is_loaded:
            return
        try:
            self._sweep_ctrl.run(
                dry_run=dry, force=force or self._chk_force.isChecked()
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "运行失败", f"Sweep 失败:\n{exc}"
            )
            return
        self._refresh_table()