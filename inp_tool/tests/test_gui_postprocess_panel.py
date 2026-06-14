"""``PostprocessPanel`` Smoke 测试。

只验证 widget 构造 + 公共 API 可调,不触发实际 GUI 显示。
用 ``QT_QPA_PLATFORM=offscreen`` 跑(headless)。

完整集成测试(信号槽 / 用户交互)留给 manual QA。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# 必须在 import PySide2 前设置
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide2 = pytest.importorskip("PySide2")


# ============================================================================
# QApplication fixture(模块级共享,避免 segfault)
# ============================================================================

@pytest.fixture(scope="module")
def qapp():
    """模块级 QApplication。"""
    from PySide2.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ============================================================================
# 构造测试
# ============================================================================

class TestPostprocessPanelConstruction:
    def test_construct_panel(self, qapp):
        from inp_tool_gui.widgets.postprocess_panel import PostprocessPanel
        panel = PostprocessPanel()
        assert panel is not None

    def test_panel_is_qwidget(self, qapp):
        from PySide2.QtWidgets import QWidget
        from inp_tool_gui.widgets.postprocess_panel import PostprocessPanel
        panel = PostprocessPanel()
        assert isinstance(panel, QWidget)


# ============================================================================
# 公共 API
# ============================================================================

class TestPostprocessPanelApi:
    """panel 至少应有 add_case_dir / clear_cases / get_op / get_geometry API。"""

    def test_add_case_dir(self, qapp, tmp_path):
        from inp_tool_gui.widgets.postprocess_panel import PostprocessPanel
        panel = PostprocessPanel()
        case = tmp_path / "case"
        case.mkdir()
        panel.add_case_dir(case)
        assert case in panel.get_case_dirs()

    def test_clear_cases(self, qapp, tmp_path):
        from inp_tool_gui.widgets.postprocess_panel import PostprocessPanel
        panel = PostprocessPanel()
        panel.add_case_dir(tmp_path / "a")
        panel.add_case_dir(tmp_path / "b")
        panel.clear_cases()
        assert panel.get_case_dirs() == []

    def test_set_op(self, qapp):
        from inp_tool_gui.widgets.postprocess_panel import PostprocessPanel
        panel = PostprocessPanel()
        panel.set_op("1,2")
        assert panel.get_op() == "1,2"

    def test_set_geometry(self, qapp):
        from inp_tool_gui.widgets.postprocess_panel import PostprocessPanel
        panel = PostprocessPanel()
        panel.set_geometry(sref=2.0, lref=3.0,
                          xref=0.1, yref=0.2, zref=0.3)
        geom = panel.get_geometry()
        assert geom["sref"] == pytest.approx(2.0)
        assert geom["lref"] == pytest.approx(3.0)
        assert geom["xref"] == pytest.approx(0.1)


# ============================================================================
# 信号槽接线 sanity
# ============================================================================

class TestPostprocessPanelSignals:
    """panel 应暴露 run_requested 信号(action 按钮触发时 emit)。"""

    def test_run_requested_signal_exists(self, qapp):
        from inp_tool_gui.widgets.postprocess_panel import PostprocessPanel
        panel = PostprocessPanel()
        # Qt Signal 在类层定义,实例上可访问
        assert hasattr(panel, "run_requested")

    def test_log_widget_exists(self, qapp):
        """panel 应有日志区(QPlainTextEdit 或 QTextEdit),供 controller 写消息。"""
        from inp_tool_gui.widgets.postprocess_panel import PostprocessPanel
        panel = PostprocessPanel()
        # append_log 方法应该存在
        assert hasattr(panel, "append_log")

    def test_append_log_does_not_crash(self, qapp):
        from inp_tool_gui.widgets.postprocess_panel import PostprocessPanel
        panel = PostprocessPanel()
        panel.append_log("test message")
        panel.append_log("another line")
