"""SweepYamlEditor:YAML 文本编辑器(QPlainTextEdit + 行号 + 语法高亮)。

Phase 5 / Task 5.1 基础视图组件。后续 Task 5.2(实时 lint)与
Task 5.3(侧边栏)将在此 widget 之上扩展。

UI 结构:
- :class:`LineNumberArea`(自定义 QWidget):绘制行号 + 错误行高亮(红底)
- :class:`YamlHighlighter`(QSyntaxHighlighter):关键词 / 注释 / 列表 / 字符串 / 数字着色
- :class:`YamlEditorWidget`(本 widget):组合 QPlainTextEdit 与 LineNumberArea

公开 API(向后兼容,Task 5.2/5.3 依赖):
- :meth:`text` / :meth:`set_text` — 读写编辑区文本
- :meth:`set_error_line` — 标记错误行(1-based;0 = 清除)

字体策略:等宽 monospace,默认 11pt;非 Pydantic 字段允许 ``list[X]`` 风格
(配合 ``from __future__ import annotations`` 在 3.8 下可解析)。

测试入口: ``inp_tool.tests.test_gui_sweep_yaml_editor``。
"""
from __future__ import annotations

import re
from typing import List, Optional

from PySide2.QtCore import QRect, QSize, Qt
from PySide2.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextFormat,
)
from PySide2.QtWidgets import (
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)


# --- 常量 --------------------------------------------------------------------

#: 等宽字体偏好列表(从最希望到 fallback;Qt 自动挑第一个可用的)
_MONO_FONT_FAMILIES = ("Courier New", "Menlo", "Consolas", "DejaVu Sans Mono")

#: 默认字号
_DEFAULT_FONT_PT = 11

#: 行号区域宽度(pixels)
_LINE_NUMBER_AREA_WIDTH = 44

#: sweep v2 YAML top-level 关键词(粗体深蓝)
_TOP_LEVEL_KEYWORDS = (
    "version",
    "template",
    "output_dir",
    "naming",
    "preset",
    "sweeps",
    "conditions",
)

#: sweep v2 YAML section-level 关键词(粗体深蓝)
_SECTION_KEYWORDS = (
    "when",
    "then",
    "disable_axes",
    "set_extra",
    "range",
)

#: 所有高亮关键词(top + section)
_ALL_KEYWORDS = _TOP_LEVEL_KEYWORDS + _SECTION_KEYWORDS

#: YAML 列表项前缀
_LIST_ITEM_RE = re.compile(r"^(\s*)-\s")
#: YAML 注释
_COMMENT_RE = re.compile(r"#[^\n]*")
#: 字符串值(单/双引号)
_STRING_VALUE_RE = re.compile(r":\s*(['\"]).*?\1")
#: 数值(含浮点 / 指数 / 负号)
_NUMBER_VALUE_RE = re.compile(r":\s*-?\d+(\.\d+)?([eE][+-]?\d+)?")
#: 内联列表(``[a, b, c]``)
_INLINE_LIST_RE = re.compile(r"\[[^\]\n]*\]")


# --- 高亮器 ------------------------------------------------------------------


class YamlHighlighter(QSyntaxHighlighter):
    """简易 YAML 语法高亮:sweep v2 关键词 / 注释 / 列表项 / 字符串 / 数字。

    设计目标:
        - 覆盖 §4.4 列出的关键词(深蓝粗体)
        - 不追求完整 YAML 高亮(无字符串嵌套、anchor、tag 等)
        - 高亮代价低(textChanged 200ms debounce 时不影响滚动)
    """

    def __init__(self, document) -> None:
        super().__init__(document)
        self._keyword_format = QTextCharFormat()
        self._keyword_format.setForeground(QColor("#1f3a93"))  # 深蓝
        self._keyword_format.setFontWeight(QFont.Bold)

        self._comment_format = QTextCharFormat()
        self._comment_format.setForeground(QColor("#7f7f7f"))  # 灰
        self._comment_format.setFontItalic(True)

        self._list_item_format = QTextCharFormat()
        self._list_item_format.setForeground(QColor("#2e75b6"))  # 浅蓝

        self._string_format = QTextCharFormat()
        self._string_format.setForeground(QColor("#2e7d32"))  # 绿

        self._number_format = QTextCharFormat()
        self._number_format.setForeground(QColor("#d97706"))  # 橙

        # 关键词 regex 一次性编译
        # 匹配 ``key:`` 或 ``key:``(行首,允许前导空白;key 在 _ALL_KEYWORDS 中)
        kw_alt = "|".join(re.escape(k) for k in _ALL_KEYWORDS)
        self._keyword_re = re.compile(rf"(^|\n)(\s*)({kw_alt})(\s*):")

    def highlightBlock(self, text) -> None:  # type: ignore[override]
        # 1) 关键词(行级扫描,避免跨块匹配问题)
        for m in self._keyword_re.finditer(text):
            start = m.start(3)
            length = m.end(3) - start
            self.setFormat(start, length, self._keyword_format)

        # 2) 注释(整行灰)
        for m in _COMMENT_RE.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._comment_format)

        # 3) 列表项前缀(``-``)+ 后续裸值
        m = _LIST_ITEM_RE.match(text)
        if m:
            prefix_len = len(m.group(1)) + 2  # ``- `` + indent
            self.setFormat(m.start(1), prefix_len, self._list_item_format)
            # 紧跟的裸值(直到行尾 / 注释)
            rest = text[prefix_len:]
            cm_idx = rest.find("#")
            if cm_idx >= 0:
                rest = rest[:cm_idx]
            self.setFormat(prefix_len, len(rest), self._list_item_format)

        # 4) 字符串值(: "..." 或 : '...')
        for m in _STRING_VALUE_RE.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._string_format)

        # 5) 数字值(: 42 / : -3.14 / : 1e5),不与字符串重叠
        for m in _NUMBER_VALUE_RE.finditer(text):
            # 若该段已被字符串覆盖,跳过(简单互斥)
            if _STRING_VALUE_RE.match(text, m.start()):
                continue
            self.setFormat(m.start(), m.end() - m.start(), self._number_format)

        # 6) 内联列表 ``[...]``(用列表项颜色做轻提示)
        for m in _INLINE_LIST_RE.finditer(text):
            # 只染色未覆盖区段;setFormat 多次叠加 Qt 取后者,这里保守只染新段
            self.setFormat(m.start(), m.end() - m.start(), self._list_item_format)


# --- 行号侧栏 ----------------------------------------------------------------


class LineNumberArea(QWidget):
    """绘制 ``QPlainTextEdit`` 行号 + 错误行红底。

    标准做法(参见 Qt 文档 Code Editor 示例):
    - 重写 :meth:`paintEvent`,逐 block 画行号
    - 监听 ``blockCountChanged`` / ``updateRequest`` 触发 update
    """

    def __init__(self, editor: "YamlEditorWidget") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(_LINE_NUMBER_AREA_WIDTH, 0)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        # 没绑定的 editor 时直接返回(避免关闭时绘制)
        if self._editor is None:
            return
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))

        editor = self._editor._editor  # type: ignore[attr-defined]
        if editor is None:
            return

        block = editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
        bottom = top + editor.blockBoundingRect(block).height()
        height = editor.fontMetrics().height()

        error_line = self._editor.error_line  # type: ignore[attr-defined]

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                line_no = block_number + 1  # 1-based
                if line_no == error_line:
                    # 错误行:红底 + 白字
                    bg = QRect(0, int(top), self.width(), int(height))
                    painter.fillRect(bg, QColor("#d32f2f"))
                    painter.setPen(QColor("#ffffff"))
                else:
                    painter.setPen(QColor("#666666"))
                painter.drawText(
                    0,
                    int(top),
                    self.width() - 4,
                    height,
                    Qt.AlignRight,
                    str(line_no),
                )
            block = block.next()
            top = bottom
            bottom = top + editor.blockBoundingRect(block).height()
            block_number += 1


# --- 主 widget ---------------------------------------------------------------


class YamlEditorWidget(QWidget):
    """YAML 文本编辑器 + 行号 + 语法高亮(Phase 5 / Task 5.1)。

    用法::

        editor = YamlEditorWidget()
        editor.set_text("version: 2\\nsweeps:\\n  mach: [1, 2]\\n")
        editor.set_error_line(2)  # 第二行标红
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._error_line: int = 0  # 1-based;0 = 无错误

        # --- QPlainTextEdit ---
        self._editor = QPlainTextEdit(self)
        self._highlighter = YamlHighlighter(self._editor.document())

        # 等宽字体:依次尝试偏好列表
        mono_family = self._pick_mono_family()
        font = QFont(mono_family, _DEFAULT_FONT_PT)
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        self._editor.setFont(font)
        # widget 自身也设同字体(被外部查询 widget.font() 时拿到正确 family)
        self.setFont(font)

        # 样式微调:tab 宽 4 字符、文档边距
        self._editor.setTabStopWidth(self._editor.fontMetrics().width(" ") * 4)
        self._editor.setLineWrapMode(QPlainTextEdit.NoWrap)

        # --- 行号侧栏 ---
        self._line_number_area = LineNumberArea(self)
        self._editor.blockCountChanged.connect(self._update_line_number_area_width)
        self._editor.updateRequest.connect(self._update_line_number_area)
        self._editor.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_line_number_area_width(0)
        self._highlight_current_line()

    # --- 公开 API --------------------------------------------------------

    def text(self) -> str:
        """返回当前 YAML 文本。"""
        return self._editor.toPlainText()

    def set_text(self, text: str) -> None:
        """设置 YAML 文本;使用 blockSignals 避免触发外部 re-highlight 回调。

        防止回环:set_text 自身不需触发 textChanged 信号(语法高亮由
        QSyntaxHighlighter 在 document 变更时自动重算)。
        """
        self._editor.blockSignals(True)
        try:
            self._editor.setPlainText(text)
        finally:
            self._editor.blockSignals(False)
        # 高亮器会自动重跑,但行号区域需手动刷新
        self._line_number_area.update()

    def set_error_line(self, line_number: int) -> None:
        """标记错误行(1-based);0 表示清除错误标记。

        不存在的行号(如超过总行数)不会报错,只是没东西可画。
        """
        self._error_line = max(0, int(line_number))
        self._line_number_area.update()

    # --- 内部辅助 -------------------------------------------------------

    @property
    def error_line(self) -> int:
        """行号区绘制时读取的当前错误行(1-based,0 = 无)。"""
        return self._error_line

    def _pick_mono_family(self) -> str:
        """从 ``_MONO_FONT_FAMILIES`` 选第一个 Qt 能识别的 family。"""
        from PySide2.QtGui import QFontDatabase

        available = set(QFontDatabase().families())
        for fam in _MONO_FONT_FAMILIES:
            if fam in available:
                return fam
        return "Courier New"  # 兜底

    def _update_line_number_area_width(self, _new_block_count: int) -> None:
        """blockCount 变化 → 重设 viewport 左边距。"""
        self._editor.setViewportMargins(_LINE_NUMBER_AREA_WIDTH, 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        """viewport 滚动 / 重绘 → 同步刷新行号区。"""
        if dy != 0:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self._editor.viewport().rect()):
            self._update_line_number_area_width(0)

    def _highlight_current_line(self) -> None:
        """当前编辑行加浅灰底(QPlainTextEdit ExtraSelection)。"""
        if not self.isEnabled():
            return
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor("#fff8e1"))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = self._editor.textCursor()
        selection.cursor.clearSelection()
        self._editor.setExtraSelections([selection])

    # --- 布局 -----------------------------------------------------------

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(QRect(cr.left(), cr.top(), _LINE_NUMBER_AREA_WIDTH, cr.height()))
        self._editor.setGeometry(QRect(cr.left() + _LINE_NUMBER_AREA_WIDTH, cr.top(), cr.width() - _LINE_NUMBER_AREA_WIDTH, cr.height()))

    # 提供一个便利:暴露内部 editor 用于诊断/调试(测试也可能用到)
    @property
    def plain_text_edit(self) -> QPlainTextEdit:
        """暴露内部 :class:`QPlainTextEdit`,主要给测试 / 子类使用。"""
        return self._editor


__all__: List[str] = [
    "YamlEditorWidget",
    "YamlHighlighter",
    "LineNumberArea",
]
