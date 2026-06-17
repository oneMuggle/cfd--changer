"""SweepYamlEditorView:基于 ConfigStore 单向数据流的 YAML 编辑视图(P5 / Task 7.1)。

UI 结构:
- 顶部 toolbar:加载 YAML / 保存为 YAML / 应用(把 YAML 文本回写 ConfigStore)
- 中央:``QPlainTextEdit``(等宽字体,显示 sweep YAML 文本)
- 底部:状态行(校验结果 / 错误位置)

数据流(单向):
- 外部 ``ConfigStore`` 变化 → ``_sync_from_store(store)`` → 序列化回 YAML 文本
- 用户点"应用" → ``yaml.safe_load`` 文本 → 解析为 ``ConfigStore`` →
  若成功 emit ``store_changed(new_store)``,若失败显示错误

注意:本视图**不**在每次 textChanged 时 emit store_changed
(避免用户输入半个 YAML 字符时污染其他视图);
只在用户点"应用"或 Ctrl+Enter 时同步,这是 spec §4.4 的语义
("实时 lint 提示,但不主动改 store")。
"""
from typing import Optional

from PySide2.QtCore import Signal
from PySide2.QtGui import QFont
from PySide2.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from inp_tool.i18n_gui import tg
from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2
from inp_tool_gui.models.config_store import ConfigStore


class SweepYamlEditorView(QWidget):
    """基于 ConfigStore 单向数据流的 YAML 编辑视图(P5 / Task 7.1)。

    Signals:
        store_changed(object): 当用户点"应用"且解析成功,emit 新 ConfigStore。
            与 SweepWizard / SweepFormView 一致:object + isinstance 校验。
    """

    store_changed = Signal(object)

    def __init__(
        self,
        store: ConfigStore,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._ctrl = SweepControllerV2()
        self._build_ui()
        self._sync_from_store(store)

    # --- 公开属性 -------------------------------------------------------

    @property
    def config_store(self) -> ConfigStore:
        return self._store

    # --- UI 构造 -------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 工具行
        btn_row = QHBoxLayout()
        self._btn_load = QPushButton(tg("sweep.btn.load_yaml"), self)
        self._btn_load.clicked.connect(self._on_load_clicked)
        self._btn_save = QPushButton(tg("sweep.btn.save_config"), self)
        self._btn_save.clicked.connect(self._on_save_clicked)
        self._btn_apply = QPushButton(tg("sweep.yaml.btn.apply"), self)
        self._btn_apply.clicked.connect(self._on_apply_clicked)
        btn_row.addWidget(self._btn_load)
        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_apply)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        # YAML 编辑区
        self._editor = QPlainTextEdit(self)
        font = QFont("Courier New")
        font.setStyleHint(QFont.Monospace)
        self._editor.setFont(font)
        self._editor.setPlaceholderText(
            "# Edit sweep YAML (v2 schema) here. Click 'Apply' (Ctrl+Enter) to sync."
        )
        root.addWidget(self._editor, 1)

        # 状态行
        self._lbl_status = QLabel("", self)
        root.addWidget(self._lbl_status)

    # --- store → form 数据流 -------------------------------------------

    def _sync_from_store(self, store: ConfigStore) -> None:
        """从 store 序列化回 YAML 文本(外部 replace 后调用)。

        阻塞 signals 防 ``textChanged`` 误触发 apply 路径;
        本视图不接 textChanged → store,只在用户点 apply 时同步。
        """
        self._store = store
        data = self._ctrl._serialize(store)
        import yaml
        text = yaml.safe_dump(
            data, allow_unicode=True, sort_keys=False, default_flow_style=False
        )
        self._editor.blockSignals(True)
        try:
            self._editor.setPlainText(text)
        finally:
            self._editor.blockSignals(False)
        self._lbl_status.setText("")

    # --- 用户操作 -------------------------------------------------------

    def _on_load_clicked(self) -> None:
        """弹文件对话框 → 加载 YAML → emit 新 store(外部需接 store_changed 推回)。"""
        path, _ = QFileDialog.getOpenFileName(
            self, tg("dialog.open_title"), "",
            tg("sweep.yaml.file_filter"),
        )
        if not path:
            return
        try:
            new_store = self._ctrl.load_yaml(path)
        except Exception as exc:
            self._lbl_status.setText(
                tg("sweep.load_failed_yaml", err=str(exc))
            )
            return
        self._store = new_store
        # 重新序列化(规范化)
        self._sync_from_store(new_store)
        self.store_changed.emit(new_store)
        self._lbl_status.setText(tg("sweep.live.sync_ok"))

    def _on_save_clicked(self) -> None:
        """弹保存对话框 → 把当前 YAML 文本(经应用)写盘。

        若当前文本未应用(用户编辑过但未点 apply),先尝试解析;失败则报错。
        """
        path, _ = QFileDialog.getSaveFileName(
            self, tg("dialog.save_title"), "sweep.yaml",
            tg("sweep.yaml.file_filter"),
        )
        if not path:
            return
        # 先应用一次:这样落盘的内容 = 用户最后看到的内容
        try:
            new_store = self._parse_text()
        except Exception as exc:
            self._lbl_status.setText(
                tg("sweep.load_failed_yaml", err=str(exc))
            )
            return
        try:
            self._ctrl.dump_yaml(new_store, path)
        except Exception as exc:
            self._lbl_status.setText(str(exc))
            return
        self._lbl_status.setText(tg("sweep.yaml.saved", path=path))

    def _on_apply_clicked(self) -> None:
        """把当前 YAML 文本解析为 ConfigStore,emit store_changed。"""
        try:
            new_store = self._parse_text()
        except Exception as exc:
            self._lbl_status.setText(
                tg("sweep.load_failed_yaml", err=str(exc))
            )
            return
        if new_store == self._store:
            self._lbl_status.setText(tg("sweep.yaml.no_change"))
            return
        self._store = new_store
        self.store_changed.emit(new_store)
        self._lbl_status.setText(tg("sweep.live.sync_ok"))

    def _parse_text(self) -> ConfigStore:
        """解析当前 YAML 文本为 ConfigStore;失败抛 ValueError。"""
        import yaml
        text = self._editor.toPlainText()
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("YAML root must be a mapping")
        return self._ctrl._parse(data)
