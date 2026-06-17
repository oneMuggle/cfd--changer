"""SweepWizard Step 2(选轴 + 设值)— Task 4.3。

UI 结构::

    +-------------------------------+--------------------------------+
    | 可用变量                       | 已选轴                          |
    | +---------------------------+ | +----------------------------+ |
    | | [ 搜索变量...            ] | | | 轴名       | 值       | 操作| |
    | +---------------------------+ | +----------------------------+ |
    | | (枚举轴)                  | | | turbulence | [sst,kw] | 删除| |
    | |   turbulence              | | | mach       | [0,2,1]  | 删除| |
    | |   energy                  | | | ...                       | |
    | | <top>                     | | +----------------------------+ |
    | |   mach[0]                 | |                                |
    | |   ...                     | |                                |
    | +---------------------------+ |                                |
    +-------------------------------+--------------------------------+

数据流(单向,与 SweepWizard 一致):
- 用户双击左侧变量 / 调 :meth:`add_axis(key)` → 拼新 store → emit
  :pyattr:`store_changed`
- 外部 replace(其他 view 改了)→ :meth:`refresh_from_store(new_store)` 重新填表

设计决策(P4 简化版,完整值 widget 留待 polish):
- 值列暂用只读 ``QTableWidgetItem`` 显示 spec 默认值文本(
  ``enum_subset``/``explicit_list``/``csv_str`` → ``values`` 拼接;
  ``range`` → ``range[min, max, step=...]``)。
- 不实现「按 kind 切换智能 widget」(checklist / spinbox / csv edit)。
  这是后续 polish 任务;本任务只验证 add/remove/refresh 三件事。
"""
from typing import Dict, Optional

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import (
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from inp_tool.i18n_gui import tg

from inp_tool_gui.models.config_store import AxisSpec, ConfigStore
from inp_tool_gui.widgets.sweep_var_combo import VarSpec
from inp_tool_gui.widgets.variable_tree_widget import (
    VariableTreeWidget,
    _LEAF_ROLE,
)


# --- 常量 ------------------------------------------------------------

_COL_KEY = 0    # 轴名(只读)
_COL_VALUE = 1  # 值(只读 P4 简化版)
_COL_OP = 2     # 操作(删除按钮)

# 每行 _COL_KEY 的 UserRole + 1 存轴 key,用于定位 store.sweeps 的 entry。
_ROLE_KEY = Qt.UserRole + 1


def _format_spec_text(spec: AxisSpec) -> str:
    """把 AxisSpec 渲成展示文本(P4 简化版)。"""
    if spec.kind == "range":
        return "range[{}, {}, step={}]".format(
            spec.range_min, spec.range_max, spec.range_step,
        )
    if spec.kind in ("enum_subset", "explicit_list", "csv_str"):
        return ", ".join(str(v) for v in spec.values)
    return str(spec)


def _default_spec_for_key(key: str, var: Optional[VarSpec]) -> AxisSpec:
    """为给定 key 推断默认 AxisSpec。

    - ``var.kind == "enum"`` → ``enum_subset`` 全选(从 var.enum_values)
    - ``var.kind == "int"`` → ``range``,min=0, max=2, step=1
    - ``var.kind == "float"`` → ``range``,min=0.0, max=2.0, step=1.0
    - 其它 / var is None → ``explicit_list``,空 tuple
    """
    if var is None:
        return AxisSpec(kind="explicit_list", values=())
    if var.kind == "enum":
        return AxisSpec(
            kind="enum_subset",
            values=tuple(var.enum_values or ()),
        )
    if var.kind == "int":
        return AxisSpec(kind="range", range_min=0, range_max=2, range_step=1)
    if var.kind == "float":
        return AxisSpec(
            kind="range", range_min=0.0, range_max=2.0, range_step=1.0,
        )
    return AxisSpec(kind="explicit_list", values=())


def _leaf_key_from_item(item: Optional[QTableWidgetItem]) -> Optional[str]:
    """(内部辅助)从 tree item 取 leaf 的 VarSpec.key;非 leaf → None。"""
    if item is None:
        return None
    is_leaf = item.data(0, _LEAF_ROLE)
    if not is_leaf:
        return None
    return item.data(0, Qt.UserRole)


class SweepWizardStep2(QWidget):
    """向导 Step 2:左变量树 + 右已选轴表。

    Signals:
        store_changed(object): 用户加/减轴时 emit 新 ConfigStore 实例。``object``
            而非 ``ConfigStore`` 类型是为跨模块稳定;消费者用
            ``isinstance(s, ConfigStore)`` 校验。
    """

    store_changed = Signal(object)

    def __init__(
        self,
        store: ConfigStore,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        # 当前已选轴 → AxisSpec(本组件持有的"next view"),refresh_from_store
        # 时被 store 覆盖;add/remove 时更新并 emit。
        self._selected: Dict[str, AxisSpec] = {}
        self._build_ui()
        self.refresh_from_store(store)

    # --- 公开属性 -------------------------------------------------------

    @property
    def tree(self) -> VariableTreeWidget:
        """暴露 :class:`VariableTreeWidget` 供测试 / 外部调用。"""
        return self._tree

    @property
    def selected(self) -> Dict[str, AxisSpec]:
        """当前已选轴 dict(只读副本语义)。"""
        return dict(self._selected)

    # --- UI 构造 -------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(splitter, 1)

        # --- 左:可用变量 -------------------------------------------------
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        lbl_left = QLabel(tg("wizard.step2.lbl.avail"), left)
        left_layout.addWidget(lbl_left)
        self._tree = VariableTreeWidget(left)
        left_layout.addWidget(self._tree, 1)
        self._btn_add = QPushButton(tg("wizard.step2.btn.add"), left)
        self._btn_add.clicked.connect(self._on_add_clicked)
        left_layout.addWidget(self._btn_add)

        # 双击 / activated → add_axis
        self._tree.variable_picked.connect(self.add_axis)

        # --- 右:已选轴 -------------------------------------------------
        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        lbl_right = QLabel(tg("wizard.step2.lbl.selected"), right)
        right_layout.addWidget(lbl_right)

        self._table = QTableWidget(right)
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([
            tg("wizard.step2.col.key"),
            tg("wizard.step2.col.value"),
            tg("wizard.step2.col.op"),
        ])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(_COL_KEY, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(_COL_VALUE, QHeaderView.Stretch)
        header.setSectionResizeMode(_COL_OP, QHeaderView.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        right_layout.addWidget(self._table, 1)

        self._empty_lbl = QLabel(tg("wizard.step2.empty"), right)
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self._empty_lbl)
        self._empty_lbl.hide()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

    # --- store 数据流 --------------------------------------------------

    def refresh_from_store(self, store: ConfigStore) -> None:
        """从给定 store 重建右侧表(外部 replace 后调用)。

        阻断 table signals 防止意外副作用。
        """
        self._store = store
        self._selected = dict(store.sweeps)
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            for key, spec in store.sweeps.items():
                self._append_row(key, spec)
            self._update_empty_label()
        finally:
            self._table.blockSignals(False)

    # --- 公开方法:add / remove ----------------------------------------

    def add_axis(self, key: str) -> None:
        """把 key 加入已选轴;若已存在则跳过(去重)。

        同时:
        1. 从 :attr:`_tree` 已枚举的 ``VarSpec`` 推断默认 AxisSpec
        2. 调 ``self._store.replace_sweep(key, spec)`` 拼新 store
        3. emit :pyattr:`store_changed`
        """
        if key in self._selected:
            return  # 去重
        var = self._find_var(key)
        spec = _default_spec_for_key(key, var)
        self._selected[key] = spec
        # 同步加 row(让用户看到视觉反馈,即使 emit 被外部拦截也能 re-render)
        self._table.blockSignals(True)
        try:
            self._append_row(key, spec)
            self._update_empty_label()
        finally:
            self._table.blockSignals(False)
        # 推 store(ConfigStore 是 frozen,replace_sweep 返回新实例)
        new_store = self._store.replace_sweep(key, spec)
        self._store = new_store
        self.store_changed.emit(new_store)

    def remove_axis(self, key: str) -> None:
        """从已选轴删除 key;若不存在则跳过。"""
        if key not in self._selected:
            return
        del self._selected[key]
        self._table.blockSignals(True)
        try:
            for row in range(self._table.rowCount()):
                item = self._table.item(row, _COL_KEY)
                if item is not None and item.data(_ROLE_KEY) == key:
                    self._table.removeRow(row)
                    break
            self._update_empty_label()
        finally:
            self._table.blockSignals(False)
        new_store = self._store.remove_sweep(key)
        self._store = new_store
        self.store_changed.emit(new_store)

    # --- 内部:row 管理 ------------------------------------------------

    def _append_row(self, key: str, spec: AxisSpec) -> None:
        """在表底部新增一行(轴名 / 值 / 删除按钮)。"""
        row = self._table.rowCount()
        self._table.insertRow(row)

        # 轴名(readonly)
        key_item = QTableWidgetItem(key)
        key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
        key_item.setData(_ROLE_KEY, key)
        self._table.setItem(row, _COL_KEY, key_item)

        # 值(readonly text,P4 简化版)
        val_text = _format_spec_text(spec)
        val_item = QTableWidgetItem(val_text)
        val_item.setFlags(val_item.flags() & ~Qt.ItemIsEditable)
        val_item.setToolTip(val_text)
        self._table.setItem(row, _COL_VALUE, val_item)

        # 删除按钮
        btn_del = QPushButton(tg("wizard.step2.btn.del"), self._table)
        btn_del.setObjectName("wizard_step2_del_{}".format(key))
        # 用默认参数锁住 key(避免 lambda 闭包变量被覆盖)
        btn_del.clicked.connect(lambda _checked=False, k=key: self.remove_axis(k))
        self._table.setCellWidget(row, _COL_OP, btn_del)

    def _update_empty_label(self) -> None:
        has_rows = self._table.rowCount() > 0
        self._empty_lbl.setVisible(not has_rows)

    def _find_var(self, key: str) -> Optional[VarSpec]:
        """在 self._tree._all_vars 里找 key 对应的 VarSpec。"""
        for v in self._tree._all_vars:
            if v.key == key:
                return v
        return None

    # --- 内部:UI 事件 --------------------------------------------------

    def _on_add_clicked(self) -> None:
        """点 "添加选中" 按钮 → 把当前 tree 选中行加入轴。

        VariableTreeWidget 已经覆盖双击 / Enter;按钮路径用
        :meth:`QTreeWidget.currentItem` 兜底。
        """
        item = self._tree.tree.currentItem()
        key = _leaf_key_from_item(item)
        if key is not None:
            self.add_axis(key)