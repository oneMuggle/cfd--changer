"""MainWindow:GUI 主窗口(:class:`QMainWindow` 子类,阶段 2 骨架)。

包含:
- File / Edit / Sweep / Detect / Help 菜单
- 主工具栏(打开/保存/撤销/重做)
- 状态栏(文件路径 / dirty 标志 / 行数)
- Ctrl+O / Ctrl+S / Ctrl+Shift+S / Ctrl+Z / Ctrl+Y / Ctrl+Q 快捷键
- File/Edit actions 与 :class:`FileController` / :class:`EditController` 桥接

阶段 3 起在中心区域加 :class:`InpTreeWidget` 等子 widget。
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
    QToolBar,
    QWidget,
)

from inp_tool_gui.app import APP_NAME, APP_VERSION
from inp_tool_gui.controllers.edit_controller import EditController
from inp_tool_gui.controllers.file_controller import FileController
from inp_tool_gui.controllers.sweep_controller import SweepController


class MainWindow(QMainWindow):
    """v0.10 GUI 主窗口。

    实例化时:
    - 构造 :class:`FileController` / :class:`EditController` / :class:`SweepController`
    - 设置窗口标题与初始尺寸
    - 构建菜单 / 工具栏 / 状态栏
    - 绑定 shortcuts 与信号
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # 控制器层(零 PySide2 依赖,纯 Python)
        self.file_ctrl = FileController()
        self.edit_ctrl = EditController(self.file_ctrl)
        self.sweep_ctrl = SweepController()

        # Qt UI
        self._setup_window()
        self._setup_actions()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_statusbar()
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

        # Sweep(占位,阶段 5 接入)
        self.act_sweep = QAction("批量算例(&W)...", self)
        self.act_sweep.triggered.connect(self._on_sweep_placeholder)

        # Detect(占位,阶段 4 接入)
        self.act_detect = QAction("检测方程/湍流(&D)", self)
        self.act_detect.setEnabled(False)  # 阶段 4 启用

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
        toolbar.setObjectName("MainToolBar")  # saveState 需要 objectName
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
        bar.addWidget(self._status_path, 1)  # stretch
        bar.addPermanentWidget(self._status_dirty)
        bar.addPermanentWidget(self._status_lines)

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

    # --- Sweep / Detect placeholder -------------------------------------

    def _on_sweep_placeholder(self) -> None:
        QMessageBox.information(
            self, "Sweep(占位)", "Sweep 表单将在阶段 5 实现。"
        )

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
        self._update_title()
        self._update_actions_enabled()

    def _refresh_after_save(self) -> None:
        self._update_title()
        self._update_actions_enabled()

    def _refresh_after_edit(self) -> None:
        self._update_title()
        self._update_actions_enabled()

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
