"""DiffViewer:对比两个 .inp 的双栏 diff 视图(Phase 5)。

UI 结构:
- 顶部按钮:``加载 A...`` / ``加载 B...`` / ``对比``
- 路径标签:A / B 两个文件路径
- 变更数标签:N 处变更
- 主区:QTextBrowser 渲染 unified diff(用 setHtml 高亮 +/-)

简化:不实现真正的"双栏并排",用 unified diff 文本 + 高亮(红 - / 绿 +)。
"""
from typing import Optional

from PySide2.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from inp_tool_gui.controllers.diff_controller import DiffController


def _colorize_unified(text: str) -> str:
    """把 unified diff 文本转 HTML,行首 +/-/@@ 加色。"""
    out_lines = []
    for line in text.split("\n"):
        esc = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        if line.startswith("---"):
            out_lines.append(f'<span style="color:#888">{esc}</span>')
        elif line.startswith("+++"):
            out_lines.append(f'<span style="color:#888">{esc}</span>')
        elif line.startswith("@@"):
            out_lines.append(f'<span style="color:#06c">{esc}</span>')
        elif line.startswith("+"):
            out_lines.append(f'<span style="color:#0a0">{esc}</span>')
        elif line.startswith("-"):
            out_lines.append(f'<span style="color:#c00">{esc}</span>')
        else:
            out_lines.append(esc)
    return "<pre style='font-family: monospace'>" + "\n".join(out_lines) + "</pre>"


class DiffViewer(QWidget):
    """对比两个 .inp 的 diff 视图。"""

    def __init__(
        self,
        diff_ctrl: DiffController,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._diff_ctrl = diff_ctrl

        root = QVBoxLayout(self)

        # 顶部按钮行
        btn_row = QHBoxLayout()
        self._btn_a = QPushButton("加载 A...", self)
        self._btn_a.clicked.connect(self._pick_a)
        btn_row.addWidget(self._btn_a)

        self._btn_b = QPushButton("加载 B...", self)
        self._btn_b.clicked.connect(self._pick_b)
        btn_row.addWidget(self._btn_b)

        self._btn_diff = QPushButton("对比", self)
        self._btn_diff.clicked.connect(self._run_diff)
        btn_row.addWidget(self._btn_diff)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        # 路径 / 变更数
        path_row = QHBoxLayout()
        self._lbl_a = QLabel("A: (未选)", self)
        self._lbl_b = QLabel("B: (未选)", self)
        self._lbl_changes = QLabel("变更数: -", self)
        path_row.addWidget(self._lbl_a, 1)
        path_row.addWidget(self._lbl_b, 1)
        path_row.addWidget(self._lbl_changes)
        root.addLayout(path_row)

        # 主区
        self._view = QTextBrowser(self)
        self._view.setOpenExternalLinks(False)
        root.addWidget(self._view, 1)

        self._refresh()

    # --- 公开 API -------------------------------------------------------

    def load_paths(self, a: str, b: str) -> None:
        """外部调用直接设两个路径 + diff(供集成测试)。"""
        self._lbl_a.setText(f"A: {a}")
        self._lbl_b.setText(f"B: {b}")
        try:
            self._diff_ctrl.load_pair(a, b)
        except Exception as exc:
            self._view.setHtml(f"<pre style='color:#c00'>diff 失败: {exc}</pre>")
            self._lbl_changes.setText("变更数: -")
            return
        self._refresh()

    # --- 内部 -----------------------------------------------------------

    def _refresh(self) -> None:
        n = self._diff_ctrl.change_count
        self._lbl_changes.setText(f"变更数: {n}")
        if self._diff_ctrl.has_pair:
            text = self._diff_ctrl.unified_text()
            self._view.setHtml(_colorize_unified(text))
        else:
            self._view.setHtml("<i>(未加载文件)</i>")

    def _pick_a(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选 A 文件", "", "mcfd.inp (*.inp);;所有文件 (*)"
        )
        if not path:
            return
        self._lbl_a.setText(f"A: {path}")
        self._maybe_diff()

    def _pick_b(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选 B 文件", "", "mcfd.inp (*.inp);;所有文件 (*)"
        )
        if not path:
            return
        self._lbl_b.setText(f"B: {path}")
        self._maybe_diff()

    def _maybe_diff(self) -> None:
        a = self._lbl_a.text().removeprefix("A: ")
        b = self._lbl_b.text().removeprefix("B: ")
        if a.startswith("(") or b.startswith("("):
            return
        try:
            self._diff_ctrl.load_pair(a, b)
        except Exception as exc:
            self._view.setHtml(f"<pre style='color:#c00'>diff 失败: {exc}</pre>")
            return
        self._refresh()

    def _run_diff(self) -> None:
        self._maybe_diff()