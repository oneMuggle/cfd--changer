"""SweepWizard:4-step 向导(template → axes → conditions → preview)。

P4 骨架(Task 4.2):只实现 Step 1 完整功能(3 个 QLineEdit + 浏览按钮
+ ConfigStore 单向同步)。Step 2/3/4 暂为占位 QLabel,留待
Task 4.3 / 4.4 / 4.5 填充。

数据流(单向,与 SweepFormView 一致):
- 用户编辑字段 → editingFinished → ``_emit_store(...)`` 拼新 ConfigStore
  → :pyattr:`store_changed` 信号 emit(new_store)
- 外部 replace(其他 view 改了)→ ``_sync_from_store(new_store)`` 重新填表单
- Step 切换只改 ``QStackedWidget`` 的 currentIndex,**不**改 store
- 取消按钮 → 关闭父 widget(无 parent 时 self.deleteLater())
"""
from typing import Optional

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from inp_tool.i18n_gui import tg
from inp_tool_gui.models.config_store import ConfigStore
from inp_tool_gui.widgets.sweep_wizard_step2 import SweepWizardStep2
from inp_tool_gui.widgets.sweep_wizard_step3 import SweepWizardStep3


_STEP_TITLES = (
    "wizard.step1",
    "wizard.step2",
    "wizard.step3",
    "wizard.step4",
)
_TODO_TEXTS = (
    None,  # Step 1 is real, not TODO
    "wizard.todo.step2",
    None,  # Step 3 is real (Task 4.4)
    "wizard.todo.step4",
)


class SweepWizard(QWidget):
    """SweepWizard:4-step 向导 (template → axes → conditions → preview)。

    Signals:
        store_changed(object): 当用户编辑任何字段,emit 新的 ConfigStore 实例。
            ``object`` 类型而非 ``ConfigStore`` 是因为 Qt Signal 不直接支持自定义
            类型在跨模块 import 时的稳定注册;消费者用 ``isinstance(s, ConfigStore)``
            校验。
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
        """返回当前 wizard 持有的 ConfigStore(只读引用)。"""
        return self._store

    # --- UI 构造 -------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 顶部步骤指示
        self._step_indicators = []
        indicator_row = QHBoxLayout()
        indicator_row.addStretch(1)
        for idx, key in enumerate(_STEP_TITLES):
            lbl = QLabel(tg(key), self)
            lbl.setObjectName("wizard_step_indicator_{}".format(idx))
            self._step_indicators.append(lbl)
            indicator_row.addWidget(lbl)
            if idx < len(_STEP_TITLES) - 1:
                sep = QLabel(" -> ", self)
                indicator_row.addWidget(sep)
        indicator_row.addStretch(1)
        root.addLayout(indicator_row)

        # QStackedWidget 含 4 页
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._build_step1())  # index 0
        # Step 2:实例化并连接 store_changed → _set_store
        self._step2 = SweepWizardStep2(self._store, self)
        self._step2.store_changed.connect(self._on_step2_store_changed)
        self._stack.addWidget(self._step2)  # 1
        # Step 3(Task 4.4):实例化并连接 store_changed → _set_store
        self._step3 = SweepWizardStep3(self._store, self)
        self._step3.store_changed.connect(self._on_step3_store_changed)
        self._stack.addWidget(self._step3)  # 2
        self._stack.addWidget(self._build_placeholder("wizard.todo.step4"))  # 3
        root.addWidget(self._stack, 1)

        # 底部按钮行
        btn_row = QHBoxLayout()
        self._btn_prev = QPushButton(tg("wizard.btn.prev"), self)
        self._btn_prev.setEnabled(False)  # Step 1 时上一步禁用
        self._btn_prev.clicked.connect(self._on_prev)
        self._btn_next = QPushButton(tg("wizard.btn.next"), self)
        self._btn_next.clicked.connect(self._on_next)
        self._btn_cancel = QPushButton(tg("wizard.btn.cancel"), self)
        self._btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._btn_prev)
        btn_row.addStretch(1)
        btn_row.addWidget(self._btn_next)
        btn_row.addWidget(self._btn_cancel)
        root.addLayout(btn_row)

        # 初始 step 指示
        self._update_step_indicators()

    def _build_step1(self) -> QWidget:
        """Step 1:模板路径 / 输出目录 / 命名模式。"""
        page = QWidget(self)
        layout = QVBoxLayout(page)

        # 模板路径
        tpl_row = QHBoxLayout()
        self._lbl_tpl = QLabel(tg("sweep.lbl.template"), page)
        self._lbl_tpl.setMinimumWidth(80)
        self._edit_tpl = QLineEdit(page)
        self._edit_tpl.editingFinished.connect(self._on_template_changed)
        self._btn_tpl = QPushButton(tg("wizard.btn.browse"), page)
        self._btn_tpl.clicked.connect(self._browse_template)
        tpl_row.addWidget(self._lbl_tpl)
        tpl_row.addWidget(self._edit_tpl, 1)
        tpl_row.addWidget(self._btn_tpl)
        layout.addLayout(tpl_row)

        # 输出目录
        out_row = QHBoxLayout()
        self._lbl_out = QLabel(tg("sweep.lbl.output"), page)
        self._lbl_out.setMinimumWidth(80)
        self._edit_out = QLineEdit(page)
        self._edit_out.editingFinished.connect(self._on_output_changed)
        self._btn_out = QPushButton(tg("wizard.btn.browse"), page)
        self._btn_out.clicked.connect(self._browse_output)
        out_row.addWidget(self._lbl_out)
        out_row.addWidget(self._edit_out, 1)
        out_row.addWidget(self._btn_out)
        layout.addLayout(out_row)

        # 命名模式
        naming_row = QHBoxLayout()
        self._lbl_naming = QLabel(tg("sweep.lbl.naming"), page)
        self._lbl_naming.setMinimumWidth(80)
        self._edit_naming = QLineEdit(page)
        self._edit_naming.editingFinished.connect(self._on_naming_changed)
        naming_row.addWidget(self._lbl_naming)
        naming_row.addWidget(self._edit_naming, 1)
        layout.addLayout(naming_row)

        layout.addStretch(1)
        return page

    def _build_placeholder(self, todo_key: str) -> QWidget:
        """Steps 2-4 占位(TODO 标签)。"""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        lbl = QLabel(tg(todo_key), page)
        lbl.setAlignment(Qt.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(lbl, 0, Qt.AlignCenter)
        layout.addStretch(1)
        return page

    # --- store -> form 数据流 ------------------------------------------

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
        # 同步 Step 2:重新从 store 刷新右侧表 + 用当前 template 重新枚举变量
        if hasattr(self, "_step2"):
            self._step2.tree.set_template_path(store.template)
            self._step2.refresh_from_store(store)
        # 同步 Step 3:重建条件 rows
        if hasattr(self, "_step3"):
            self._step3.refresh_from_store(store)

    # --- Step 2 数据流 -------------------------------------------------

    def _on_step2_store_changed(self, new_store: object) -> None:
        """Step 2 add/remove 轴 → 用 wizard 自己的 _set_store 推进 store。

        与 Step 1 共享同一 emit 出口,这样外部消费者只监听一个信号。
        """
        if not isinstance(new_store, ConfigStore):
            return
        if new_store == self._store:
            return  # 无变化
        self._set_store(new_store)

    # --- Step 3 数据流 -------------------------------------------------

    def _on_step3_store_changed(self, new_store: object) -> None:
        """Step 3 add/remove/edit 条件 → 用 wizard 自己的 _set_store 推进 store。

        与 Step 2 同款:外部消费者只监听 wizard.store_changed 一个信号。
        """
        if not isinstance(new_store, ConfigStore):
            return
        if new_store == self._store:
            return  # 无变化
        self._set_store(new_store)

    def _set_store(self, new_store: ConfigStore) -> None:
        """内部:set self._store + emit store_changed(供 Step 2/3 调用)。

        与 ``_emit_store`` 不同:这里**不**调 ``self._store.replace``,
        因为 new_store 已经由 Step 2/3 自己构造好;避免重复 replace。

        还会同步刷新 Step 2/3 的 UI(只刷"非源"的 step);但同源 step
        不会因 setText 触发回环:Step 内部 emit 后调 _set_store,store
        已经是最新的,Step 自己的 _rules 跟 store 一致,所以"刷不刷新"
        结果一样。
        """
        self._store = new_store
        # 同步刷新 Step 2/3(若有 sweep 变化让 step2 重画;若 condition 变化让 step3 重画)
        if hasattr(self, "_step2"):
            self._step2.refresh_from_store(new_store)
        if hasattr(self, "_step3"):
            self._step3.refresh_from_store(new_store)
        self.store_changed.emit(new_store)

    # --- form -> store 数据流 ------------------------------------------

    def _on_template_changed(self) -> None:
        self._emit_store(template=self._edit_tpl.text().strip())

    def _on_output_changed(self) -> None:
        self._emit_store(output_dir=self._edit_out.text().strip())

    def _on_naming_changed(self) -> None:
        # 命名模式不能为空 — fallback 到 "case"
        text = self._edit_naming.text().strip() or "case"
        self._emit_store(naming=text)

    def _browse_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tg("dialog.open_title"), "",
            tg("dialog.open_inp_filter"),
        )
        if path:
            self._edit_tpl.setText(path)
            self._on_template_changed()

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tg("sweep.lbl.output"))
        if path:
            self._edit_out.setText(path)
            self._on_output_changed()

    def _emit_store(self, **kwargs) -> None:
        """用 kwargs 调 ``self._store.replace(...)`` 构造新 store,emit store_changed。"""
        new_store = self._store.replace(**kwargs)
        if new_store == self._store:
            # 无变化(用户编辑了又改回原值)→ 不发信号
            return
        self._store = new_store
        # template 字段变化 → 同步刷 Step 2 的变量树(让用户看到对应模板的变量)
        if "template" in kwargs and hasattr(self, "_step2"):
            self._step2.tree.set_template_path(new_store.template)
        self.store_changed.emit(new_store)

    # --- 步骤切换 -------------------------------------------------------

    def _on_next(self) -> None:
        idx = self._stack.currentIndex()
        if idx < self._stack.count() - 1:
            self._stack.setCurrentIndex(idx + 1)
            self._update_step_indicators()

    def _on_prev(self) -> None:
        idx = self._stack.currentIndex()
        if idx > 0:
            self._stack.setCurrentIndex(idx - 1)
            self._update_step_indicators()

    def _on_cancel(self) -> None:
        """关闭父 widget(无 parent 时 self.deleteLater())。"""
        parent = self.parentWidget()
        if parent is not None:
            parent.close()
        else:
            self.deleteLater()

    def _update_step_indicators(self) -> None:
        """更新 prev 按钮的 enabled 状态(Step 1 时禁用)。"""
        idx = self._stack.currentIndex()
        self._btn_prev.setEnabled(idx > 0)
