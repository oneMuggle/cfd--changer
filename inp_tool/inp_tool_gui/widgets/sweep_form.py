"""SweepForm:Sweep 配置 + 实时编辑 + 加载/保存 + 运行 + 结果展示(v0.16.1 整合版)。

UI 结构:
- 顶部:模板路径 / 输出目录 / 命名模式(``QLineEdit`` + 浏览按钮,失焦即同步)
- Sweep 轴表:``QTableWidget`` 2 列(轴名 + 值列表,逗号分隔)
- 按钮行:加载 YAML / 加载 JSON / 保存为 YAML
- 按钮行:运行(Dry) / 运行 / 强制覆盖
- 状态行:同步状态 + case 数
- 结果表:``QTableWidget`` 4 列(case_id / path / params / applied)

工作流:
- 启动时从 controller 拉一次,填表单(:meth:`_sync_from_controller`)
- 用户编辑字段 → editingFinished / itemChanged → :meth:`_sync_form_to_controller`
- 加载 YAML/JSON 后 → controller reload → :meth:`_sync_from_controller` 填表单

公开 API(向后兼容):
- :meth:`load_yaml` / :meth:`load_json` / :meth:`run_sync`
"""
from typing import Any, Dict, List, Optional

from PySide2.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from inp_tool.i18n_gui import tg
from inp_tool_gui.controllers.sweep_controller import SweepController
from inp_tool_gui.widgets.sweep_var_combo import VarSpec  # 新增(Task 7)


class SweepForm(QWidget):
    """Sweep 配置 + 实时编辑 + 加载/保存 + 运行 + 结果展示(v0.16.1 整合版)。"""

    def __init__(
        self,
        sweep_ctrl: SweepController,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._sweep_ctrl = sweep_ctrl
        self._build_ui()
        self._sync_from_controller()

    # --- UI 构造 -------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 模板路径
        tpl_row = QHBoxLayout()
        self._lbl_tpl = QLabel(tg("sweep.lbl.template"), self)
        self._lbl_tpl.setMinimumWidth(80)
        self._edit_tpl = QLineEdit(self)
        self._edit_tpl.editingFinished.connect(self._sync_form_to_controller)
        self._btn_tpl = QPushButton("浏览...", self)
        self._btn_tpl.clicked.connect(self._pick_template)
        tpl_row.addWidget(self._lbl_tpl)
        tpl_row.addWidget(self._edit_tpl, 1)
        tpl_row.addWidget(self._btn_tpl)
        root.addLayout(tpl_row)

        # 输出目录
        out_row = QHBoxLayout()
        self._lbl_out = QLabel(tg("sweep.lbl.output"), self)
        self._lbl_out.setMinimumWidth(80)
        self._edit_out = QLineEdit(self)
        self._edit_out.editingFinished.connect(self._sync_form_to_controller)
        self._btn_out = QPushButton("浏览...", self)
        self._btn_out.clicked.connect(self._pick_output)
        out_row.addWidget(self._lbl_out)
        out_row.addWidget(self._edit_out, 1)
        out_row.addWidget(self._btn_out)
        root.addLayout(out_row)

        # 命名
        naming_row = QHBoxLayout()
        self._lbl_naming = QLabel(tg("sweep.lbl.naming"), self)
        self._lbl_naming.setMinimumWidth(80)
        self._edit_naming = QLineEdit(self)
        self._edit_naming.editingFinished.connect(self._sync_form_to_controller)
        naming_row.addWidget(self._lbl_naming)
        naming_row.addWidget(self._edit_naming, 1)
        root.addLayout(naming_row)

        # Sweep 轴表
        axes_box = QGroupBox(tg("sweep.title.sweeps_axes"), self)
        axes_layout = QVBoxLayout(axes_box)
        self._axes_table = QTableWidget(0, 2, self)
        self._axes_table.setHorizontalHeaderLabels(["轴名", "值列表(逗号分隔)"])
        self._axes_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self._axes_table.itemChanged.connect(self._on_axis_changed)
        axes_layout.addWidget(self._axes_table)
        self._btn_add_axis = QPushButton("添加轴", self)
        self._btn_add_axis.clicked.connect(lambda: self._append_axis_row("", ""))
        axes_layout.addWidget(self._btn_add_axis)
        root.addWidget(axes_box, 1)

        # 按钮行:加载 / 保存
        btn_row_top = QHBoxLayout()
        self._btn_load_yaml = QPushButton(tg("sweep.btn.load_yaml"), self)
        self._btn_load_yaml.clicked.connect(self._pick_yaml)
        self._btn_load_json = QPushButton(tg("sweep.btn.load_json"), self)
        self._btn_load_json.clicked.connect(self._pick_json)
        self._btn_save_yaml = QPushButton(tg("sweep.btn.save_config"), self)
        self._btn_save_yaml.clicked.connect(self._save_yaml)
        btn_row_top.addWidget(self._btn_load_yaml)
        btn_row_top.addWidget(self._btn_load_json)
        btn_row_top.addWidget(self._btn_save_yaml)
        btn_row_top.addStretch(1)
        root.addLayout(btn_row_top)

        # 按钮行:运行
        btn_row_run = QHBoxLayout()
        self._btn_run_dry = QPushButton(tg("sweep.btn.run_dry"), self)
        self._btn_run_dry.clicked.connect(lambda: self._on_run(dry=True))
        self._btn_run = QPushButton(tg("sweep.btn.run"), self)
        self._btn_run.clicked.connect(lambda: self._on_run(dry=False))
        self._chk_force = QCheckBox(tg("sweep.btn.force"), self)
        btn_row_run.addWidget(self._btn_run_dry)
        btn_row_run.addWidget(self._btn_run)
        btn_row_run.addWidget(self._chk_force)
        btn_row_run.addStretch(1)
        root.addLayout(btn_row_run)

        # 状态行 + case 数
        status_row = QHBoxLayout()
        self._lbl_status = QLabel("", self)
        self._lbl_cases = QLabel(tg("sweep.lbl.case_count") + " 0", self)
        status_row.addWidget(self._lbl_status, 1)
        status_row.addWidget(self._lbl_cases)
        root.addLayout(status_row)

        # 结果表
        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(
            [
                tg("sweep.col.case_id"),
                tg("sweep.col.path"),
                tg("sweep.col.params"),
                tg("sweep.col.applied"),
            ]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table, 1)

    # --- controller ↔ form 数据流 -------------------------------------

    def _sync_from_controller(self) -> None:
        """从 controller 拉取,填到表单。"""
        if not self._sweep_ctrl.is_loaded:
            self._update_status()
            return
        # 阻塞信号防回灌
        for w in (self._edit_tpl, self._edit_out, self._edit_naming):
            w.blockSignals(True)
        try:
            self._edit_tpl.setText(self._sweep_ctrl.template or "")
            out = getattr(self._sweep_ctrl._sweep, "output_dir", "")
            self._edit_out.setText(str(out) if out else "")
            naming = getattr(self._sweep_ctrl._sweep, "naming", "")
            self._edit_naming.setText(str(naming) if naming else "")
        finally:
            for w in (self._edit_tpl, self._edit_out, self._edit_naming):
                w.blockSignals(False)
        # axes(重建表)
        self._axes_table.blockSignals(True)
        try:
            self._axes_table.setRowCount(0)
            for k, v in self._sweep_ctrl._sweep.sweeps.values.items():
                self._append_axis_row(k, v)
        finally:
            self._axes_table.blockSignals(False)
        self._update_status()

    def _collect_to_dict(self) -> Dict[str, Any]:
        """从表单字段收 dict,失败抛 ValueError。"""
        if not self._edit_tpl.text().strip():
            raise ValueError(tg("sweep.live.need_template"))
        if not self._edit_out.text().strip():
            raise ValueError(tg("sweep.live.need_output"))
        sweeps_dict: Dict[str, List[Any]] = {}
        for r in range(self._axes_table.rowCount()):
            spec = self._spec_for_row(r)
            if spec is None:
                continue
            key = spec.key
            cell = self._axes_table.cellWidget(r, 1)
            if isinstance(cell, QLineEdit):
                raw = cell.text().strip()
                try:
                    vals = [self._parse_scalar(x) for x in raw.split(",") if x.strip()]
                except ValueError as e:
                    raise ValueError(
                        tg("sweep.live.invalid_axis", key=key, val=raw)
                    ) from e
                sweeps_dict[key] = vals
            elif isinstance(cell, QLabel):
                sweeps_dict[key] = list(spec.enum_values or ())
        return {
            "template": self._edit_tpl.text().strip(),
            "output_dir": self._edit_out.text().strip(),
            "naming": self._edit_naming.text().strip() or "case",
            "sweeps": sweeps_dict,
        }

    def _sync_form_to_controller(self) -> None:
        """把表单同步到 controller(失焦触发)。"""
        # 单元级校验(状态栏提示,不阻断)
        for r in range(self._axes_table.rowCount()):
            err = self._validate_value_cell(r)
            if err:
                self._lbl_status.setText(err)
                return
        try:
            d = self._collect_to_dict()
        except ValueError as e:
            if self._sweep_ctrl.is_loaded:
                self._lbl_status.setText(str(e))
            return
        try:
            self._sweep_ctrl.load_from_dict(d)
        except Exception as e:
            self._lbl_status.setText(tg("sweep.live.sync_fail", err=str(e)))
            return
        self._update_status()

    def _update_status(self) -> None:
        if not self._sweep_ctrl.is_loaded:
            self._lbl_status.setText("")
            self._lbl_cases.setText(tg("sweep.lbl.case_count") + " 0")
            self._btn_run_dry.setEnabled(False)
            self._btn_run.setEnabled(False)
            return
        n = self._sweep_ctrl.case_count
        self._lbl_cases.setText(tg("sweep.lbl.case_count") + " {}".format(n))
        self._lbl_status.setText(tg("sweep.live.sync_ok"))
        self._btn_run_dry.setEnabled(True)
        self._btn_run.setEnabled(True)

    def _on_axis_changed(self, _idx_or_item=None) -> None:
        """QComboBox.currentIndexChanged 或 QTableWidget.itemChanged 触发。"""
        sender = self.sender()
        row = -1
        for r in range(self._axes_table.rowCount()):
            if self._axes_table.cellWidget(r, 0) is sender:
                row = r
                break
        if row < 0:
            return
        spec = self._spec_for_row(row)
        if spec is None:
            return
        old_text = ""
        old_cell = self._axes_table.cellWidget(row, 1)
        if isinstance(old_cell, QLineEdit):
            old_text = old_cell.text()
        new_cell = self._make_value_cell_for_kind(spec)
        if isinstance(new_cell, QLineEdit):
            new_cell.setText(old_text)
            new_cell.editingFinished.connect(self._sync_form_to_controller)
        self._axes_table.setCellWidget(row, 1, new_cell)
        self._sync_form_to_controller()

    def _spec_for_row(self, row: int) -> Optional[VarSpec]:
        """取一行的 VarSpec(从 combobox userData)。"""
        combo = self._axes_table.cellWidget(row, 0)
        if not isinstance(combo, QComboBox):
            return None
        key = combo.currentData()
        if not key:
            return None
        for s in self._sweep_ctrl.available_vars(self._sweep_ctrl.template):
            if s.key == key:
                return s
        return VarSpec(key=key, label=key + " (未知)", kind="str")

    def _validate_value_cell(self, row: int) -> Optional[str]:
        """校验一行的值 cell;返回错误信息或 None(OK)。"""
        spec = self._spec_for_row(row)
        if spec is None:
            return None
        cell = self._axes_table.cellWidget(row, 1)
        if not isinstance(cell, QLineEdit):
            return None
        raw = cell.text().strip()
        if not raw:
            return None
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if spec.kind == "int":
            for i, p in enumerate(parts, start=1):
                try:
                    int(p)
                except ValueError:
                    tmpl = tg("sweep.live.invalid_int")
                    return tmpl.replace("{key}", spec.key).replace("{idx}", str(i))
        elif spec.kind == "float":
            for i, p in enumerate(parts, start=1):
                try:
                    float(p.replace("d", "e").replace("D", "E"))
                except ValueError:
                    tmpl = tg("sweep.live.invalid_float")
                    return tmpl.replace("{key}", spec.key).replace("{idx}", str(i))
        return None

    def _make_combo_for_row(self, spec: Optional[VarSpec]) -> QComboBox:
        """根据当前 controller 模板,生成含所有可选变量的 QComboBox。"""
        template = self._sweep_ctrl.template
        specs = self._sweep_ctrl.available_vars(template)
        combo = QComboBox(self)
        for s in specs:
            combo.addItem(s.label, userData=s.key)
        if spec is not None:
            for i in range(combo.count()):
                if combo.itemData(i) == spec.key:
                    combo.setCurrentIndex(i)
                    break
        return combo

    def _make_value_cell_for_kind(self, spec: VarSpec) -> QWidget:
        """按 spec.kind 生成值 cell:enum→QLabel(不可编辑),其他→QLineEdit。"""
        if spec.kind == "enum":
            values = spec.enum_values or ()
            lbl = QLabel(", ".join(values), self)
            lbl.setStyleSheet("color: #555; font-style: italic;")
            return lbl
        return QLineEdit(self)

    def _append_axis_row(
        self,
        key: str = "",
        raw_val: Any = "",
    ) -> None:
        """追加一行:第 0 列 QComboBox(选变量),第 1 列 QLineEdit/QLabel(值)。"""
        r = self._axes_table.rowCount()
        self._axes_table.insertRow(r)

        specs = self._sweep_ctrl.available_vars(self._sweep_ctrl.template)
        spec = None
        for s in specs:
            if s.key == key:
                spec = s
                break
        if spec is None and key:
            spec = VarSpec(key=key, label=key + " (未知)", kind="str")

        # 第 0 列:QComboBox
        combo = self._make_combo_for_row(spec)
        self._axes_table.setCellWidget(r, 0, combo)
        combo.currentIndexChanged.connect(self._on_axis_changed)

        # 第 1 列:按 kind
        if spec is not None:
            cell = self._make_value_cell_for_kind(spec)
            if isinstance(cell, QLineEdit):
                text = ", ".join(str(x) for x in raw_val) if isinstance(raw_val, list) else str(raw_val or "")
                cell.setText(text)
                cell.editingFinished.connect(self._sync_form_to_controller)
            self._axes_table.setCellWidget(r, 1, cell)

    def _mark_row_orphan(self, r: int) -> None:
        """标记行为失效(红底)。Task 9 加 tooltip 完整化。"""
        for col in (0, 1):
            w = self._axes_table.cellWidget(r, col)
            if w is not None:
                w.setStyleSheet("background-color: #FFD6D6;")

    def _mark_row_normal(self, r: int) -> None:
        """清除失效标记。"""
        for col in (0, 1):
            w = self._axes_table.cellWidget(r, col)
            if w is not None:
                w.setStyleSheet("")

    @staticmethod
    def _parse_scalar(s: str) -> Any:
        s = s.strip()
        try:
            return int(s)
        except ValueError:
            pass
        try:
            return float(s)
        except ValueError:
            pass
        return s

    # --- 公开 API(向后兼容) -------------------------------------------

    def load_yaml(self, path: str) -> None:
        """外部直接 load YAML(供集成测试 / 拖拽)。"""
        self._load_yaml_path(path)

    def load_json(self, path: str) -> None:
        """外部直接 load JSON。"""
        self._load_json_path(path)

    def run_sync(self, *, dry: bool = False, force: bool = False) -> None:
        """同步跑 sweep 并刷新表(供测试 / 简化入口)。"""
        self._on_run(dry=dry, force=force)

    # --- 加载 / 保存 YAML/JSON -----------------------------------------

    def _pick_yaml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选 sweep YAML", "", "YAML (*.yaml *.yml);;所有文件 (*)"
        )
        if not path:
            return
        self._load_yaml_path(path)

    def _load_yaml_path(self, path: str) -> None:
        try:
            self._sweep_ctrl.load_from_yaml(path)
        except Exception as exc:
            QMessageBox.critical(
                self, "加载失败",
                tg("sweep.load_failed_yaml", err=str(exc)),
            )
            return
        self._sync_from_controller()  # 加载后填表单

    def _pick_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选 sweep JSON", "", "JSON (*.json);;所有文件 (*)"
        )
        if not path:
            return
        self._load_json_path(path)

    def _load_json_path(self, path: str) -> None:
        try:
            self._sweep_ctrl.load_from_json(path)
        except Exception as exc:
            QMessageBox.critical(
                self, "加载失败",
                tg("sweep.load_failed_json", err=str(exc)),
            )
            return
        self._sync_from_controller()  # 加载后填表单

    def _save_yaml(self) -> None:
        try:
            d = self._collect_to_dict()
        except ValueError as e:
            QMessageBox.warning(self, tg("sweep.btn.save_config"), str(e))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tg("sweep.btn.save_config"), "sweep.yaml",
            "YAML (*.yaml *.yml);;所有文件 (*)",
        )
        if not path:
            return
        import yaml
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        self._lbl_status.setText("已保存:{}".format(path))

    # --- 浏览按钮 -----------------------------------------------------

    def _pick_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tg("sweep.lbl.template"), "", "mcfd.inp (*.inp)"
        )
        if path:
            self._edit_tpl.setText(path)
            self._sync_form_to_controller()

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tg("sweep.lbl.output"))
        if path:
            self._edit_out.setText(path)
            self._sync_form_to_controller()

    # --- 运行 ----------------------------------------------------------

    def _on_run(self, dry: bool, force: bool = False) -> None:
        if not self._sweep_ctrl.is_loaded:
            return
        # 先同步一次(用户可能编辑后没失焦)
        self._sync_form_to_controller()
        if not self._sweep_ctrl.is_loaded:
            return
        try:
            self._sweep_ctrl.run(
                dry_run=dry, force=force or self._chk_force.isChecked()
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "运行失败",
                tg("sweep.run_failed", err=str(exc)),
            )
            return
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
