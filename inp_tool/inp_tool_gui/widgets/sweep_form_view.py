"""SweepFormView:基于 ConfigStore 单向数据流的 Sweep 配置视图(P3 骨架)。

UI 结构(与 ``SweepForm`` 类似,但数据源改为不可变 ``ConfigStore``):
- 顶部:模板路径 / 输出目录 / 命名模式(``QLineEdit`` + 浏览按钮,失焦即同步)
- Sweep 轴表:``QTableWidget`` 2 列(轴名 + 值列表,逗号分隔)
- 按钮行:加载 YAML / 加载 JSON / 保存为 YAML / 运行(Dry) / 运行 / 强制覆盖
- 状态行 + case 数 label
- 结果表:``QTableWidget`` 4 列(case_id / path / params / applied)

数据流(单向):
- 用户编辑字段 → editingFinished → ``_emit_store()`` 拼新 ConfigStore
  → :pyattr:`store_changed` 信号 emit(new_store)
- 外部 replace(其他 view 改了)→ ``_sync_from_store(new_store)`` 重新填表单

后续 Task:
- 值 cell 按 ``AxisSpec.kind`` 智能切换(enum_subset → checklist / range → spinbox / ...)
- 按钮接线(加载 / 保存 / 运行)留给 Task 3.3
"""
from typing import Optional

from PySide2.QtCore import Signal
from PySide2.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from inp_tool.i18n_gui import tg
from inp_tool_gui.models.config_store import AxisSpec, ConfigStore


class SweepFormView(QWidget):
    """基于 ConfigStore 单向数据流的 Sweep 配置视图(P3 骨架)。

    Signals:
        store_changed(object): 当用户编辑任何字段,emit 新的 ConfigStore 实例。
            ``object`` 类型而非 ``ConfigStore`` 是因为 Qt Signal 不直接支持自定义类型
            在跨模块 import 时的稳定注册;消费者用 ``isinstance(s, ConfigStore)`` 校验。
    """

    store_changed = Signal(object)

    def __init__(
        self,
        store: ConfigStore,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._build_ui()
        self._sync_from_store(store)

    # --- 公开属性 -------------------------------------------------------

    @property
    def config_store(self) -> ConfigStore:
        """返回当前 view 持有的 ConfigStore(只读引用)。"""
        return self._store

    # --- UI 构造 -------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 模板路径
        tpl_row = QHBoxLayout()
        self._lbl_tpl = QLabel(tg("sweep.lbl.template"), self)
        self._lbl_tpl.setMinimumWidth(80)
        self._edit_tpl = QLineEdit(self)
        self._edit_tpl.editingFinished.connect(self._on_tpl_editing_finished)
        self._btn_tpl = QPushButton("浏览...", self)
        # TODO(Task 3.3): 接线 _pick_template
        self._btn_tpl.clicked.connect(lambda: None)
        tpl_row.addWidget(self._lbl_tpl)
        tpl_row.addWidget(self._edit_tpl, 1)
        tpl_row.addWidget(self._btn_tpl)
        root.addLayout(tpl_row)

        # 输出目录
        out_row = QHBoxLayout()
        self._lbl_out = QLabel(tg("sweep.lbl.output"), self)
        self._lbl_out.setMinimumWidth(80)
        self._edit_out = QLineEdit(self)
        self._edit_out.editingFinished.connect(self._on_out_editing_finished)
        self._btn_out = QPushButton("浏览...", self)
        # TODO(Task 3.3): 接线 _pick_output
        self._btn_out.clicked.connect(lambda: None)
        out_row.addWidget(self._lbl_out)
        out_row.addWidget(self._edit_out, 1)
        out_row.addWidget(self._btn_out)
        root.addLayout(out_row)

        # 命名
        naming_row = QHBoxLayout()
        self._lbl_naming = QLabel(tg("sweep.lbl.naming"), self)
        self._lbl_naming.setMinimumWidth(80)
        self._edit_naming = QLineEdit(self)
        self._edit_naming.editingFinished.connect(self._on_naming_editing_finished)
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
        # TODO(Task 3.3+): 完整 wiring — 智能值 cell / itemChanged → store emit
        axes_layout.addWidget(self._axes_table)
        self._btn_add_axis = QPushButton("添加轴", self)
        # TODO(Task 3.3): 接线 _append_axis_row
        self._btn_add_axis.clicked.connect(lambda: None)
        axes_layout.addWidget(self._btn_add_axis)
        root.addWidget(axes_box, 1)

        # 按钮行:加载 / 保存
        btn_row_top = QHBoxLayout()
        self._btn_load_yaml = QPushButton(tg("sweep.btn.load_yaml"), self)
        # TODO(Task 3.3): 接线 load YAML
        self._btn_load_yaml.clicked.connect(lambda: None)
        self._btn_load_json = QPushButton(tg("sweep.btn.load_json"), self)
        # TODO(Task 3.3): 接线 load JSON
        self._btn_load_json.clicked.connect(lambda: None)
        self._btn_save_yaml = QPushButton(tg("sweep.btn.save_config"), self)
        # TODO(Task 3.3): 接线 save YAML
        self._btn_save_yaml.clicked.connect(lambda: None)
        btn_row_top.addWidget(self._btn_load_yaml)
        btn_row_top.addWidget(self._btn_load_json)
        btn_row_top.addWidget(self._btn_save_yaml)
        btn_row_top.addStretch(1)
        root.addLayout(btn_row_top)

        # 按钮行:运行
        btn_row_run = QHBoxLayout()
        self._btn_run_dry = QPushButton(tg("sweep.btn.run_dry"), self)
        # TODO(Task 3.3): 接线 run dry
        self._btn_run_dry.clicked.connect(lambda: None)
        self._btn_run = QPushButton(tg("sweep.btn.run"), self)
        # TODO(Task 3.3): 接线 run
        self._btn_run.clicked.connect(lambda: None)
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

    # --- store → form 数据流 -------------------------------------------

    def _sync_from_store(self, store: ConfigStore) -> None:
        """从给定 store 重新填表单(外部 replace 后调用)。

        阻断信号防止 editingFinished 在 setText 时误触发 store_changed。
        """
        self._store = store
        widgets = (self._edit_tpl, self._edit_out, self._edit_naming)
        for w in widgets:
            w.blockSignals(True)
        try:
            self._edit_tpl.setText(store.template or "")
            self._edit_out.setText(store.output_dir or "")
            self._edit_naming.setText(store.naming or "")
        finally:
            for w in widgets:
                w.blockSignals(False)

        # axes:重建表
        self._axes_table.blockSignals(True)
        try:
            self._axes_table.setRowCount(0)
            for key, spec in store.sweeps.items():
                self._append_axis_row_from_spec(key, spec)
        finally:
            self._axes_table.blockSignals(False)

        # case 数 label
        try:
            n = store.case_count
        except Exception:
            n = 0
        self._lbl_cases.setText(tg("sweep.lbl.case_count") + " {}".format(n))

    def _append_axis_row_from_spec(self, key: str, spec: AxisSpec) -> None:
        """在 axes_table 末尾追加一行,第一列显示 key,第二列显示 spec.values 的 str。"""
        r = self._axes_table.rowCount()
        self._axes_table.insertRow(r)
        self._axes_table.setItem(r, 0, QTableWidgetItem(key))
        if spec.kind == "range":
            text = "range[{min}, {max}, step={step}]".format(
                min=spec.range_min, max=spec.range_max, step=spec.range_step,
            )
        else:
            text = ", ".join(str(v) for v in spec.values)
        self._axes_table.setItem(r, 1, QTableWidgetItem(text))

    # --- form → store 数据流 -------------------------------------------

    def _on_tpl_editing_finished(self) -> None:
        self._emit_store(template=self._edit_tpl.text().strip())

    def _on_out_editing_finished(self) -> None:
        self._emit_store(output_dir=self._edit_out.text().strip())

    def _on_naming_editing_finished(self) -> None:
        self._emit_store(naming=self._edit_naming.text().strip() or "case")

    def _emit_store(self, **kwargs) -> None:
        """用 kwargs 调 ``self._store.replace(...)`` 构造新 store,emit store_changed。"""
        new_store = self._store.replace(**kwargs)
        if new_store == self._store:
            # 无变化(用户编辑了又改回原值)→ 不发信号
            return
        self._store = new_store
        self.store_changed.emit(new_store)
        # 同步 case 数
        try:
            n = new_store.case_count
        except Exception:
            n = 0
        self._lbl_cases.setText(tg("sweep.lbl.case_count") + " {}".format(n))
