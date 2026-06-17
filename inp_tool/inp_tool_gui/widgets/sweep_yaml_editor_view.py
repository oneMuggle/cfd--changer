"""SweepYamlEditorView:Phase 5 / Task 5.3 容器 widget。

3-pane 布局(``QSplitter(Qt.Horizontal)``)::

    +-----------+--------------------------+-----------+
    | 变量树    |  YAML 编辑器              | 预览表    |
    | + presets |                          |           |
    | (左 200)  |  (中,自适应)             | (右 280)  |
    +-----------+--------------------------+-----------+

行为:
- ``store_changed``(YAML 编辑器 lint 通过)→ 刷新左侧变量树 + 右侧预览表
- 变量树双击/Enter → 在 YAML 编辑器光标处插入 var.key
- preset 列表双击 → 用 preset 内容替换 YAML 文本 + emit ``preset_loaded``
- 底部状态栏:展示 lint 状态(``valid`` / ``error`` / ``empty``)

不在 Task 5.3 范围内(MainWindow 集成在 Phase 7):
- 仅作为独立 widget 工作;无菜单/工具栏/快捷键
- preset 列表是简单 ``QListWidget``,无分组 / 拖拽 / 右键菜单

依赖:
- :class:`inp_tool_gui.widgets.sweep_yaml_editor.YamlEditorWidget`
- :class:`inp_tool_gui.widgets.variable_tree_widget.VariableTreeWidget`(软依赖;
  缺失时退化为占位 widget)
- :class:`inp_tool_gui.preset_library.PresetLibrary`(可选)
- :class:`inp_tool_gui.models.config_store.ConfigStore`
- :func:`inp_tool.sweep.expand_with_conditions`
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import yaml
from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from inp_tool_gui.models.config_store import ConfigStore
from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget


#: 实时预览表最多显示行数(避免笛卡尔积爆炸卡 UI)
_PREVIEW_LIMIT: int = 50


# --- helpers ---------------------------------------------------------------


def _axis_to_sweep_value(spec: Any) -> List[Any]:
    """``AxisSpec`` → ``SweepValue`` 列表。

    - ``range`` → ``[min, min+step, ..., max]``(端点都包含,step 非法时退化为单点)
    - 其他 kind → ``list(spec.values)``
    """
    kind = getattr(spec, "kind", "")
    if kind == "range":
        try:
            lo = float(spec.range_min)
            hi = float(spec.range_max)
            step = float(spec.range_step)
        except (TypeError, ValueError):
            return [lo] if spec.range_min is not None else []
        if step <= 0:
            return [lo, hi] if lo != hi else [lo]
        n = int((hi - lo) / step) + 1
        return [lo + i * step for i in range(n)]
    vals = getattr(spec, "values", ()) or ()
    return list(vals)


def _store_to_sweep_spec(store: ConfigStore) -> Any:
    """``ConfigStore`` → :class:`inp_tool.sweep.SweepSpec`。

    sweep 为空时仍构造(用空 ``values`` dict),由调用方决定是否展开。
    """
    from inp_tool.sweep import SweepSpec

    values: Dict[str, Any] = {}
    for key, axis in store.sweeps.items():
        values[key] = _axis_to_sweep_value(axis)
    return SweepSpec(values=values)


# --- 主 widget -----------------------------------------------------------


class SweepYamlEditorView(QWidget):
    """SweepYamlEditor 容器 widget(Phase 5 / Task 5.3)。

    公开 API:
    - :attr:`preset_loaded` — ``Signal(str)`` preset 列表双击时发 preset ref
    - :meth:`config_store` — 返回最近 ConfigStore
    - :meth:`set_store` — 外部替换 store(同步 YAML 文本 + sidebars)
    - :meth:`preview_row_count` — 预览表当前行数(测试用)
    - :meth:`preset_loaded_payload` — 最近 preset 加载的 ref(测试用)
    """

    #: preset 列表双击时发出 preset ref(``"name"`` 或 ``"team:dir/name"``)
    preset_loaded = Signal(str)

    def __init__(
        self,
        store: ConfigStore,
        preset_library: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store: ConfigStore = store
        self._preset_library: Optional[Any] = preset_library
        self._latest_store: Optional[ConfigStore] = None  # lint 链路最新值
        self._last_preset_ref: Optional[str] = None  # 测试用
        self._build_ui()
        # 初始状态:把 ConfigStore 序列化进 YAML,触发一次 lint 链路
        self._write_store_to_editor(store)
        # 把 sidebars 用当前 store 同步(初始一次)
        self._refresh_sidebars_from_store(store)

    # --- 公开 API ---------------------------------------------------------

    def config_store(self) -> ConfigStore:
        """返回最近的 ConfigStore(优先用 YAML 编辑器 lint 后的最新值,否则原值)。"""
        latest = self._latest_store
        return latest if latest is not None else self._store

    def set_store(self, store: ConfigStore) -> None:
        """外部传入新 store:替换 YAML 文本 + 刷新 sidebars。

        用 ``blockSignals`` 防止外部 set_store → store_changed 链路回环。
        """
        self._store = store
        self._write_store_to_editor(store)
        # set_text 内部 blockSignals,不会触发 lint 链路 → 手动刷新 sidebars
        self._refresh_sidebars_from_store(store)

    def preview_row_count(self) -> int:
        """预览表当前行数(实际渲染 + 受 ``_PREVIEW_LIMIT`` 上限影响)。"""
        return self._preview_table.rowCount()

    def preset_loaded_payload(self) -> Optional[str]:
        """最近一次 preset 加载事件的 ref(测试用)。``None`` = 尚未加载。"""
        return self._last_preset_ref

    # --- UI 构造 ---------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # 横向 splitter:左 | 中 | 右
        self._h_splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(self._h_splitter, 1)

        # 左:变量树 + presets(垂直 splitter)
        self._left_splitter = QSplitter(Qt.Vertical, self._h_splitter)
        self._var_tree = self._build_variable_tree()
        self._left_splitter.addWidget(self._var_tree)
        self._preset_list = self._build_preset_list()
        self._left_splitter.addWidget(self._preset_list)
        self._left_splitter.setStretchFactor(0, 3)
        self._left_splitter.setStretchFactor(1, 2)
        self._left_splitter.setSizes([300, 200])
        # widget 已挂,填充 preset 列表
        self._populate_presets()

        # 中:YAML 编辑器
        self._editor = YamlEditorWidget(self._h_splitter)

        # 右:预览表
        self._preview_table = self._build_preview_table()

        # splitter 比例:左 200 / 中 自适应 / 右 280
        self._h_splitter.addWidget(self._left_splitter)
        self._h_splitter.addWidget(self._editor)
        self._h_splitter.addWidget(self._preview_table)
        self._h_splitter.setStretchFactor(0, 0)
        self._h_splitter.setStretchFactor(1, 1)
        self._h_splitter.setStretchFactor(2, 0)
        self._h_splitter.setSizes([220, 800, 280])

        # 状态栏(底部)
        self._status_label = QLabel(self)
        self._status_label.setStyleSheet(
            "QLabel { padding: 2px 8px; background: #f0f0f0; color: #333; }"
        )
        root.addWidget(self._status_label)

        # --- 信号连接 ---
        # 编辑器 lint 通过 → 刷新 sidebars + 状态
        self._editor.store_changed.connect(self._on_store_changed)
        # 编辑器 lint 失败 → 状态栏红字
        self._editor.validation_error.connect(self._on_validation_error)
        # 变量树双击 / Enter → 在编辑器光标处插入 key
        self._var_tree.variable_picked.connect(self._on_variable_picked)
        # preset 列表双击 → 用 preset 内容替换 YAML
        self._preset_list.itemDoubleClicked.connect(self._on_preset_activated)

        # 初始状态文字
        self._set_status("idle", "")

    def _build_variable_tree(self) -> Any:
        # 延迟 import:VariableTreeWidget 在 feat/sweep-wizard 分支已实现,
        # 但本任务文件不应强依赖该分支,允许 None 时静默退化为空 widget。
        try:
            from inp_tool_gui.widgets.variable_tree_widget import (
                VariableTreeWidget,
            )
            return VariableTreeWidget(self._left_splitter)
        except Exception:
            placeholder = QListWidget(self._left_splitter)
            placeholder.addItem(QListWidgetItem("(变量树未加载)"))
            placeholder.setEnabled(False)
            return placeholder

    def _build_preset_list(self) -> QListWidget:
        lw = QListWidget(self._left_splitter)
        lw.setAlternatingRowColors(True)
        lw.setUniformItemSizes(True)
        # 不在此调 populate:self._preset_list 尚未赋值,放外层。
        return lw

    def _build_preview_table(self) -> QTableWidget:
        tbl = QTableWidget(self._h_splitter)
        tbl.setColumnCount(3)
        tbl.setHorizontalHeaderLabels(["case_id", "params", "applied"])
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.setAlternatingRowColors(True)
        # 列宽
        tbl.setColumnWidth(0, 80)
        tbl.setColumnWidth(1, 200)
        tbl.setColumnWidth(2, 160)
        return tbl

    # --- preset 列表填充 ---------------------------------------------------

    def _populate_presets(self) -> None:
        self._preset_list.clear()
        if self._preset_library is None:
            self._preset_list.addItem(QListWidgetItem("(preset 库未配置)"))
            self._preset_list.setEnabled(False)
            return
        try:
            metas = self._preset_library.list()
        except Exception as exc:  # noqa: BLE001
            self._preset_list.addItem(
                QListWidgetItem("(preset 列表加载失败: {})".format(exc))
            )
            self._preset_list.setEnabled(False)
            return
        if not metas:
            self._preset_list.addItem(QListWidgetItem("(空)"))
            self._preset_list.setEnabled(False)
            return
        self._preset_list.setEnabled(True)
        for m in metas:
            label = "{}  [{}]".format(m.name, m.source)
            item = QListWidgetItem(label)
            # ref 用于 ``PresetLibrary.get()`` 取回内容
            item.setData(Qt.UserRole, self._ref_of_meta(m))
            self._preset_list.addItem(item)

    @staticmethod
    def _ref_of_meta(meta: Any) -> str:
        """``PresetMeta`` → PresetLibrary.get() 接受的 ref 字符串。"""
        name = getattr(meta, "name", "")
        source = getattr(meta, "source", "user")
        if source == "user":
            return name
        # source 形如 ``"team:<dir>"``
        if source.startswith("team:"):
            return "{}:{}".format(source, name)
        return name

    # --- YAML ↔ ConfigStore -------------------------------------------------

    def _write_store_to_editor(self, store: ConfigStore) -> None:
        """``ConfigStore`` → YAML 文本 → 设置到编辑器。

        生成的 YAML 是最小可工作形式(满足 SweepControllerV2._parse 的 schema)。
        """
        from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2

        data = SweepControllerV2()._serialize(store)
        text = yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )
        self._editor.set_text(text)

    def _refresh_sidebars_from_store(self, store: ConfigStore) -> None:
        """根据 store 重算:变量树 + 预览表。"""
        # 变量树:用 template path 重枚举
        if hasattr(self._var_tree, "set_template_path"):
            self._var_tree.set_template_path(store.template or None)
        self._refresh_preview(store)

    def _refresh_preview(self, store: ConfigStore) -> None:
        """``expand_with_conditions`` → 写入预览表(最多 _PREVIEW_LIMIT 行)。"""
        self._preview_table.setRowCount(0)
        # 0 sweeps → 无 case 可展示
        if not store.sweeps:
            self._preview_table.setRowCount(0)
            return
        try:
            spec = _store_to_sweep_spec(store)
            # SweepSpec.values 不能为空 dict(expand_cartesian 会抛);
            # 但任一 axis.values 为空数组时同样抛。两种空都静默跳过。
            from inp_tool.sweep import expand_with_conditions

            cases = expand_with_conditions(spec, store.conditions)
        except Exception as exc:  # noqa: BLE001
            self._preview_table.setRowCount(1)
            self._preview_table.setItem(0, 0, QTableWidgetItem("error"))
            self._preview_table.setItem(0, 1, QTableWidgetItem(str(exc)))
            self._preview_table.setItem(0, 2, QTableWidgetItem(""))
            return

        limit = min(len(cases), _PREVIEW_LIMIT)
        self._preview_table.setRowCount(limit)
        for i in range(limit):
            case = cases[i]
            case_id = "{}".format(i + 1)
            params = ", ".join(
                "{}={}".format(k, v) for k, v in case.values.items()
            )
            applied = ", ".join(
                "{}={}".format(k, v) for (k, v) in case.extras)
            self._preview_table.setItem(i, 0, QTableWidgetItem(case_id))
            self._preview_table.setItem(i, 1, QTableWidgetItem(params))
            self._preview_table.setItem(i, 2, QTableWidgetItem(applied))

    # --- 信号槽 ---------------------------------------------------------

    def _on_store_changed(self, new_store: ConfigStore) -> None:
        """YAML lint 通过:用最新 store 刷新 sidebars。"""
        self._latest_store = new_store
        self._refresh_sidebars_from_store(new_store)
        self._set_status("valid", "校验通过")

    def _on_validation_error(self, message: str) -> None:
        """YAML lint 失败:状态栏红字 + 预览表保留上次。"""
        self._set_status("error", message)

    def _on_variable_picked(self, key: str) -> None:
        """变量树 leaf 拾取 → 在 YAML 编辑器光标处插入 key。

        用 ``cursor.insertText`` 不带换行;若 key 含 ``.``(形如 ``physics.reynolds[0]``)
        原样插入,后续由用户在 YAML 中按需加冒号。
        """
        edit = self._editor.plain_text_edit
        cursor = edit.textCursor()
        cursor.insertText(key)

    def _on_preset_activated(self, item: QListWidgetItem) -> None:
        """preset 列表双击 → 用 preset YAML 替换编辑器文本 + emit 信号。"""
        ref = item.data(Qt.UserRole)
        if not ref:
            return
        # 先取内容;若取不到,清空状态栏提示,不动编辑器。
        if self._preset_library is None:
            self._set_status("error", "preset 库未配置")
            return
        try:
            data = self._preset_library.get(ref)
        except Exception as exc:  # noqa: BLE001
            self._set_status("error", "preset 加载失败: {}".format(exc))
            return
        # 把 preset dict 写成 YAML(preset 通常只覆盖 sweeps / conditions,
        # 不一定有顶层 template / output_dir,但 dump 出来无害)
        try:
            text = yaml.safe_dump(
                data,
                allow_unicode=True,
                sort_keys=False,
                default_flow_style=False,
            )
        except Exception as exc:  # noqa: BLE001
            self._set_status("error", "preset 序列化失败: {}".format(exc))
            return
        self._editor.set_text(text)
        self._last_preset_ref = ref
        self.preset_loaded.emit(ref)

    # --- 状态栏 ---------------------------------------------------------

    def _set_status(self, kind: str, message: str) -> None:
        """更新底部状态栏文本 + 颜色。"""
        if kind == "valid":
            color = "#1b5e20"  # 深绿
            prefix = "OK"
        elif kind == "error":
            color = "#b71c1c"  # 深红
            prefix = "ERR"
        else:  # idle / empty
            color = "#555"
            prefix = "—"
        self._status_label.setStyleSheet(
            "QLabel {{ padding: 2px 8px; background: #f0f0f0; color: {}; }}"
            .format(color)
        )
        if message:
            self._status_label.setText("{}: {}".format(prefix, message))
        else:
            self._status_label.setText("{}: (idle)".format(prefix))


__all__: List[str] = ["SweepYamlEditorView"]