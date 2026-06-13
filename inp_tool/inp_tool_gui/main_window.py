"""MainWindow:GUI 主窗口(:class:`QMainWindow` 子类,阶段 5 集成版)。

包含:
- File / Edit / Sweep / Detect / Help 菜单
- 主工具栏(打开/保存/撤销/重做)
- 状态栏(文件路径 / dirty 标志 / 行数)
- Ctrl+O / Ctrl+S / Ctrl+Shift+S / Ctrl+Z / Ctrl+Y / Ctrl+Q 快捷键
- 4 个标签页(中心区 QTabWidget):
  - 文件:InpTreeWidget,双击 value 弹 ValueEditorDialog
  - 检测:DetectPanel,3 个 Preset 按钮 + 推荐字段
  - Sweep:SweepForm,加载 YAML/JSON + 运行 + 结果表
  - 对比:DiffViewer,加载 A/B + unified diff
"""
from pathlib import Path
from typing import Optional

from PySide2.QtGui import QKeySequence
from PySide2.QtWidgets import (
    QAction,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QWidget,
)

from inp_tool_gui.app import APP_NAME, APP_VERSION
from inp_tool_gui.controllers.detect_controller import DetectController
from inp_tool_gui.controllers.diff_controller import DiffController
from inp_tool_gui.controllers.edit_controller import EditController
from inp_tool_gui.controllers.file_controller import FileController
from inp_tool_gui.controllers.sweep_controller import SweepController
from inp_tool_gui.widgets.detect_panel import DetectPanel
from inp_tool_gui.widgets.diff_viewer import DiffViewer
from inp_tool_gui.widgets.inp_tree import InpTreeWidget
from inp_tool_gui.widgets.preset_dialog import PresetDialog
from inp_tool_gui.widgets.sweep_form import SweepForm
from inp_tool_gui.widgets.value_editor import ValueEditorDialog


class MainWindow(QMainWindow):
    """v0.10 GUI 主窗口。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # 控制器层(零 PySide2 依赖,纯 Python)
        self.file_ctrl = FileController()
        self.edit_ctrl = EditController(self.file_ctrl)
        self.sweep_ctrl = SweepController()
        self.detect_ctrl = DetectController()
        self.diff_ctrl = DiffController()

        # Qt UI
        self._setup_window()
        self._setup_actions()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_central()
        self._update_actions_enabled()
        self._update_title()

    # --- UI 构造 -------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1280, 800)

    def _setup_actions(self) -> None:
        # File
        self.act_open = QAction("打开(&O)...", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self._on_open)

        self.act_save = QAction("保存(&S)", self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.triggered.connect(self._on_save)

        self.act_save_as = QAction("另存为(&A)...", self)
        self.act_save_as.setShortcut(QKeySequence.SaveAs)
        self.act_save_as.triggered.connect(self._on_save_as)

        self.act_exit = QAction("退出(&X)", self)
        self.act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_exit.triggered.connect(self.close)

        # Edit
        self.act_undo = QAction("撤销(&U)", self)
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.triggered.connect(self._on_undo)

        self.act_redo = QAction("重做(&R)", self)
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.triggered.connect(self._on_redo)

        # Sweep / Detect(阶段 5 启用,接入标签页)
        self.act_sweep = QAction("批量算例(&W)...", self)
        self.act_sweep.triggered.connect(self._on_sweep_action)

        self.act_detect = QAction("检测方程/湍流(&D)", self)
        self.act_detect.triggered.connect(self._on_detect_action)

    def _setup_menus(self) -> None:
        menubar = self.menuBar()

        m_file = menubar.addMenu("文件(&F)")
        m_file.addAction(self.act_open)
        m_file.addAction(self.act_save)
        m_file.addAction(self.act_save_as)
        m_file.addSeparator()
        m_file.addAction(self.act_exit)

        m_edit = menubar.addMenu("编辑(&E)")
        m_edit.addAction(self.act_undo)
        m_edit.addAction(self.act_redo)

        m_sweep = menubar.addMenu("Sweep(&W)")
        m_sweep.addAction(self.act_sweep)

        m_detect = menubar.addMenu("检测(&D)")
        m_detect.addAction(self.act_detect)

        m_help = menubar.addMenu("帮助(&H)")
        m_help.addAction("关于(&A)...").triggered.connect(self._on_about)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setObjectName("MainToolBar")
        toolbar.addAction(self.act_open)
        toolbar.addAction(self.act_save)
        toolbar.addSeparator()
        toolbar.addAction(self.act_undo)
        toolbar.addAction(self.act_redo)
        self.addToolBar(toolbar)

    def _setup_statusbar(self) -> None:
        bar = QStatusBar(self)
        self.setStatusBar(bar)
        self._status_path = QLabel("(未打开文件)")
        self._status_dirty = QLabel("")
        self._status_lines = QLabel("0 行")
        bar.addWidget(self._status_path, 1)
        bar.addPermanentWidget(self._status_dirty)
        bar.addPermanentWidget(self._status_lines)

    def _setup_central(self) -> None:
        """中心区:QTabWidget 容纳 4 个 widget。"""
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("CentralTabs")

        self.tree_widget = InpTreeWidget(self)
        self.tree_widget.value_edit_requested.connect(self._on_value_edit_requested)
        self.tabs.addTab(self.tree_widget, "文件(&E)")

        self.detect_panel = DetectPanel(self.detect_ctrl, self.edit_ctrl, self)
        self.detect_panel.preset_requested.connect(self._on_preset_requested)
        self.tabs.addTab(self.detect_panel, "检测(&T)")

        self.sweep_form = SweepForm(self.sweep_ctrl, self)
        self.tabs.addTab(self.sweep_form, "Sweep(&S)")

        self.diff_viewer = DiffViewer(self.diff_ctrl, self)
        self.tabs.addTab(self.diff_viewer, "对比(&D)")

        self.setCentralWidget(self.tabs)

    # --- File actions ---------------------------------------------------

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开 mcfd.inp", str(Path.cwd()),
            "mcfd.inp (*.inp);;所有文件 (*)",
        )
        if not path:
            return
        try:
            self.file_ctrl.open(path)
        except Exception as exc:
            QMessageBox.critical(self, "打开失败", f"无法解析 {path}:\n{exc}")
            return
        self.edit_ctrl.mark_clean()
        self._refresh_after_open()

    def _on_save(self) -> None:
        if not self.file_ctrl.is_open:
            return
        try:
            self.file_ctrl.save()
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", f"无法保存:\n{exc}")
            return
        self.edit_ctrl.mark_clean()
        self._refresh_after_save()

    def _on_save_as(self) -> None:
        if not self.file_ctrl.is_open:
            return
        suggested = (
            str(self.file_ctrl.current_path)
            if self.file_ctrl.current_path
            else str(Path.cwd() / "untitled.inp")
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "另存为", suggested, "mcfd.inp (*.inp);;所有文件 (*)",
        )
        if not path:
            return
        try:
            self.file_ctrl.save(path)
        except Exception as exc:
            QMessageBox.critical(self, "另存为失败", f"无法保存:\n{exc}")
            return
        self.edit_ctrl.mark_clean()
        self._refresh_after_save()

    # --- Edit actions ----------------------------------------------------

    def _on_undo(self) -> None:
        if self.edit_ctrl.undo() is not None:
            self._refresh_after_edit()

    def _on_redo(self) -> None:
        if self.edit_ctrl.redo() is not None:
            self._refresh_after_edit()

    # --- 树形 value 双击 → ValueEditorDialog ----------------------------

    def _on_value_edit_requested(
        self, block_idx: int, keyword: str, value_idx: int
    ) -> None:
        inp = self.file_ctrl.inp
        if inp is None:
            return
        # 取当前 stmt 的 raw + typed
        if block_idx == -1:
            stmt_idx = _find_stmt_idx(inp.top_stmts, keyword)
            stmt = inp.top_stmts[stmt_idx] if stmt_idx >= 0 else None
        else:
            if block_idx >= len(inp.block_list):
                return
            block = inp.block_list[block_idx]
            stmt_idx = _find_stmt_idx(block.statements, keyword)
            stmt = block.statements[stmt_idx] if stmt_idx >= 0 else None
        if stmt is None or value_idx >= len(stmt.values):
            return
        v = stmt.values[value_idx]
        dlg = ValueEditorDialog(
            current_raw=v.raw, current_typed=v.typed, parent=self
        )
        if dlg.exec_() != ValueEditorDialog.Accepted:
            return
        new_value = dlg.new_value
        if block_idx == -1:
            ok = self._edit_top_stmt_value(keyword, value_idx, new_value)
        else:
            ok = self.edit_ctrl.set_value(
                inp.block_list[block_idx].name,
                keyword,
                new_value,
                block_idx=block_idx,
            )
        if ok:
            self._refresh_after_edit()

    def _edit_top_stmt_value(
        self, keyword: str, value_idx: int, new_value: object
    ) -> bool:
        """顶层语句(value_idx 不在 block 索引内)直接写 InpFile + 推 undo。"""
        inp = self.file_ctrl.inp
        if inp is None:
            return False
        from inp_tool_gui.controllers.edit_controller import UndoEntry

        for stmt in inp.top_stmts:
            if stmt.keyword == keyword and value_idx < len(stmt.values):
                old_value = stmt.values[value_idx].typed
                stmt.values[value_idx].raw = str(new_value)
                # 用 infer_type 让 typed 跟 raw 一致
                from inp_tool.model import infer_type
                stmt.values[value_idx].typed = infer_type(str(new_value))
                self.edit_ctrl._undo_stack.append(
                    UndoEntry(
                        block_name="<top>",
                        keyword=keyword,
                        old_value=old_value,
                        new_value=new_value,
                        block_idx=-1,
                    )
                )
                self.edit_ctrl._redo_stack.clear()
                self.edit_ctrl._is_dirty = True
                return True
        return False

    # --- Sweep / Detect actions ----------------------------------------

    def _on_sweep_action(self) -> None:
        """菜单触发:跳到 Sweep 标签页。"""
        self.tabs.setCurrentWidget(self.sweep_form)

    def _on_detect_action(self) -> None:
        """菜单触发:跳到检测标签页 + 立即跑检测。"""
        self.tabs.setCurrentWidget(self.detect_panel)
        if self.file_ctrl.inp is not None:
            self.detect_panel.run(self.file_ctrl.inp)

    def _on_preset_requested(self, preset_name: str) -> None:
        """DetectPanel 的 Preset 按钮 → 弹 PresetDialog → accept 后 refresh。"""
        if self.file_ctrl.inp is None:
            QMessageBox.information(self, "未打开文件", "请先打开一个 .inp 文件。")
            return
        dlg = PresetDialog(preset_name, self.edit_ctrl, parent=self)
        dlg.set_inp(self.file_ctrl.inp)  # v0.13:preset 需要 InpFile
        if dlg.exec_() == PresetDialog.Accepted:
            self._refresh_after_edit()
            self.detect_panel.run(self.file_ctrl.inp)

    def _on_about(self) -> None:
        QMessageBox.about(
            self, f"关于 {APP_NAME}",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "mcfd.inp 桌面编辑器(PySide2 + inp_tool core)\n"
            "支持 Win7 / Win10 / Linux 三平台。",
        )

    # --- UI 刷新 --------------------------------------------------------

    def _refresh_after_open(self) -> None:
        path = self.file_ctrl.current_path
        self._status_path.setText(str(path) if path else "(未打开文件)")
        if path and path.exists():
            try:
                with open(str(path), "r", encoding="utf-8", errors="replace") as f:
                    n_lines = sum(1 for _ in f)
                self._status_lines.setText(f"{n_lines} 行")
            except OSError:
                self._status_lines.setText("0 行")
        if self.file_ctrl.inp is not None:
            self.tree_widget.populate(self.file_ctrl.inp)
            self.detect_panel.run(self.file_ctrl.inp)
            self.tabs.setCurrentWidget(self.tree_widget)
        self._update_title()
        self._update_actions_enabled()

    def _refresh_after_save(self) -> None:
        self._update_title()
        self._update_actions_enabled()

    def _refresh_after_edit(self) -> None:
        self._update_title()
        self._update_actions_enabled()
        # MVP: 整个树重建;后续可优化为单行 refresh_value
        if self.file_ctrl.inp is not None:
            self.tree_widget.populate(self.file_ctrl.inp)

    def _update_title(self) -> None:
        path = self.file_ctrl.current_path
        if path is None:
            self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        else:
            star = " *" if self.edit_ctrl.is_dirty else ""
            self.setWindowTitle(f"{path.name}{star} — {APP_NAME}")
        self._status_dirty.setText("●" if self.edit_ctrl.is_dirty else "")

    def _update_actions_enabled(self) -> None:
        self.act_save.setEnabled(self.file_ctrl.is_open)
        self.act_save_as.setEnabled(self.file_ctrl.is_open)
        self.act_undo.setEnabled(self.edit_ctrl.can_undo)
        self.act_redo.setEnabled(self.edit_ctrl.can_redo)
        self.act_sweep.setEnabled(self.file_ctrl.is_open)
        self.act_detect.setEnabled(self.file_ctrl.is_open)


def _find_stmt_idx(stmts, keyword: str) -> int:
    """找 keyword 在 stmts 中的索引;找不到返 -1。"""
    for i, s in enumerate(stmts):
        if s.keyword == keyword:
            return i
    return -1