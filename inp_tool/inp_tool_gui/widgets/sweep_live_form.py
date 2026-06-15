"""SweepLiveForm:实时编辑 sweep 配置的表单(v0.16 新增)。"""
from typing import Dict, List, Optional

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (
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

from inp_tool_gui.controllers.sweep_controller import SweepController
from inp_tool.i18n_gui import tg


class SweepLiveForm(QWidget):
    """Sweep 实时编辑表单。"""

    def __init__(
        self,
        sweep_ctrl: SweepController,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._sweep_ctrl = sweep_ctrl
        self._build_ui()
        self._sync_from_controller()

    def sync_from_controller(self) -> None:
        """从 controller 拉取最新 dict,刷新表单(供外部修改后回灌)。"""
        self._sync_from_controller()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 模板路径
        tpl_row = QHBoxLayout()
        self._edit_tpl = QLineEdit(self)
        self._edit_tpl.editingFinished.connect(self._on_sync)
        self._btn_tpl = QPushButton("浏览...", self)
        self._btn_tpl.clicked.connect(self._pick_template)
        tpl_row.addWidget(self._edit_tpl, 1)
        tpl_row.addWidget(self._btn_tpl)
        root.addLayout(tpl_row)

        # 输出目录
        out_row = QHBoxLayout()
        self._edit_out = QLineEdit(self)
        self._edit_out.editingFinished.connect(self._on_sync)
        self._btn_out = QPushButton("浏览...", self)
        self._btn_out.clicked.connect(self._pick_output)
        out_row.addWidget(self._edit_out, 1)
        out_row.addWidget(self._btn_out)
        root.addLayout(out_row)

        # naming
        self._edit_naming = QLineEdit(self)
        self._edit_naming.editingFinished.connect(self._on_sync)
        root.addWidget(self._edit_naming)

        # Sweep 轴表
        axes_box = QGroupBox(tg("sweep.title.sweeps_axes"), self)
        axes_layout = QVBoxLayout(axes_box)
        self._axes_table = QTableWidget(0, 2, self)
        self._axes_table.setHorizontalHeaderLabels(["轴名", "值列表(逗号分隔)"])
        self._axes_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        axes_layout.addWidget(self._axes_table)
        self._btn_add_axis = QPushButton("添加轴", self)
        self._btn_add_axis.clicked.connect(self._add_axis_row)
        axes_layout.addWidget(self._btn_add_axis)
        root.addWidget(axes_box, 1)

        # 同步状态
        self._lbl_status = QLabel("", self)
        root.addWidget(self._lbl_status)

        # 保存为 YAML
        self._btn_save_yaml = QPushButton(tg("sweep.btn.save_config"), self)
        self._btn_save_yaml.clicked.connect(self._save_yaml)
        root.addWidget(self._btn_save_yaml)

    def _sync_from_controller(self) -> None:
        if not self._sweep_ctrl.is_loaded:
            return
        self._edit_tpl.blockSignals(True)
        self._edit_out.blockSignals(True)
        self._edit_naming.blockSignals(True)
        self._edit_tpl.setText(self._sweep_ctrl.template or "")
        out = getattr(self._sweep_ctrl._sweep, "output_dir", "")
        self._edit_out.setText(str(out) if out else "")
        naming = getattr(self._sweep_ctrl._sweep, "naming", "")
        self._edit_naming.setText(str(naming) if naming else "")
        sweeps = self._sweep_ctrl._sweep.sweeps
        self._axes_table.setRowCount(0)
        for k, v in sweeps.values.items():
            self._append_axis_row(k, v)
        self._edit_tpl.blockSignals(False)
        self._edit_out.blockSignals(False)
        self._edit_naming.blockSignals(False)

    def _collect_to_dict(self) -> Dict:
        if not self._edit_tpl.text().strip():
            raise ValueError(tg("sweep.live.need_template"))
        if not self._edit_out.text().strip():
            raise ValueError(tg("sweep.live.need_output"))
        sweeps_dict = {}
        for r in range(self._axes_table.rowCount()):
            key_item = self._axes_table.item(r, 0)
            val_item = self._axes_table.item(r, 1)
            if not key_item or not val_item:
                continue
            key = key_item.text().strip()
            if not key:
                continue
            raw = val_item.text().strip()
            try:
                vals = [
                    _parse_scalar(x) for x in raw.split(",") if x.strip()
                ]
            except ValueError as e:
                raise ValueError(
                    tg("sweep.live.invalid_axis", key=key, val=raw)
                ) from e
            sweeps_dict[key] = vals
        return {
            "template": self._edit_tpl.text().strip(),
            "output_dir": self._edit_out.text().strip(),
            "naming": self._edit_naming.text().strip() or "case",
            "sweeps": sweeps_dict,
        }

    def _on_sync(self) -> None:
        try:
            d = self._collect_to_dict()
        except ValueError as e:
            self._lbl_status.setText(str(e))
            return
        try:
            self._sweep_ctrl.load_from_dict(d)
            self._lbl_status.setText(tg("sweep.live.sync_ok"))
        except Exception as e:
            self._lbl_status.setText(
                tg("sweep.live.sync_fail", err=str(e))
            )

    def _save_yaml(self) -> None:
        try:
            d = self._collect_to_dict()
        except ValueError as e:
            QMessageBox.warning(
                self, tg("sweep.btn.save_config"), str(e)
            )
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

    def _pick_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tg("sweep.lbl.template"), "", "mcfd.inp (*.inp)"
        )
        if path:
            self._edit_tpl.setText(path)
            self._on_sync()

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, tg("sweep.lbl.output")
        )
        if path:
            self._edit_out.setText(path)
            self._on_sync()

    def _add_axis_row(self) -> None:
        self._append_axis_row("", "")

    def _append_axis_row(self, key, val) -> None:
        r = self._axes_table.rowCount()
        self._axes_table.insertRow(r)
        self._axes_table.setItem(r, 0, QTableWidgetItem(key))
        if isinstance(val, list):
            text = ", ".join(str(x) for x in val)
        else:
            text = str(val) if val is not None else ""
        self._axes_table.setItem(r, 1, QTableWidgetItem(text))
        self._axes_table.itemChanged.connect(lambda *_: self._on_sync())


def _parse_scalar(s):
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
