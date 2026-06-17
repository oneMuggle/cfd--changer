"""MainWindow 集成测试(Phase 5)。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless。

测试覆盖:
- 构造后 4 个 tab 全在
- open 一个 .inp 后 tree_widget 被 populate + 切到 '文件' tab
- _on_detect_action 切到 '检测' tab + 跑检测(报告摘要更新)
- _on_sweep_action 切到 'Sweep' tab
- 顶层语句改值:_edit_top_stmt_value 写 + 推 undo + dirty
"""
import os
import textwrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide2.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def sample_inp_path(tmp_path):
    """写一个含 top_stmt + physics block + 顶层 seq.# eqnset_define(SST k-ω)。"""
    p = tmp_path / "test.inp"
    p.write_text(
        textwrap.dedent(
            """\
            title Hello
            seq.# 1 #vals 31 title eqnset_define
              values 101 1 1 2 3
              values 0 0 1 1 1
            physics begin
              reftem 300.0
              reynolds 1.0e6
              tnoneq_numeqns 0
            physics end
            """
        ),
        encoding="utf-8",
    )
    return str(p)


def test_central_tabs_present(qapp):
    """构造后中心区有 4 个 tab(文件/检测/Sweep/对比)。"""
    from inp_tool_gui.main_window import MainWindow
    from inp_tool.i18n_gui import tg

    win = MainWindow()
    try:
        tabs = win.tabs
        labels = [tabs.tabText(i) for i in range(tabs.count())]
        assert "文件(&E)" in labels
        assert "检测(&T)" in labels
        # v0.16.1:Sweep 顶层 tab 翻译为"批量算例" / "&Batch Cases"
        assert tg("tab.sweep_zh") in labels
        assert "对比(&D)" in labels
    finally:
        win.close()
        win.deleteLater()


def test_open_populates_tree(qapp, sample_inp_path):
    """open 一个 .inp → tree 被 populate + tab 切到 '文件'。"""
    from inp_tool_gui.main_window import MainWindow

    win = MainWindow()
    try:
        win.file_ctrl.open(sample_inp_path)
        win.edit_ctrl.mark_clean()
        win._refresh_after_open()

        labels = win.tree_widget.top_level_labels()
        assert "顶层语句" in labels
        assert "块" in labels

        # v0.16:tree_widget 现在包在 file_widget 容器内 → current tab 是容器
        current = win.tabs.currentWidget()
        assert current.layout() is not None
        assert current.layout().indexOf(win.tree_widget) >= 0
    finally:
        win.close()
        win.deleteLater()


def test_detect_action_runs_detection(qapp, sample_inp_path):
    """_on_detect_action 切到 '检测' tab 并跑检测(报告摘要更新)。"""
    from inp_tool_gui.main_window import MainWindow

    win = MainWindow()
    try:
        win.file_ctrl.open(sample_inp_path)
        win._on_detect_action()
        assert win.tabs.currentWidget() is win.detect_panel
        # v0.13:DetectPanel 摘要用 EquationSystemReport 格式
        assert "能量=" in win.detect_panel._summary_lbl.text()
    finally:
        win.close()
        win.deleteLater()


def test_sweep_action_switches_tab(qapp, sample_inp_path):
    """_on_sweep_action 切到 Sweep tab。"""
    from inp_tool_gui.main_window import MainWindow

    win = MainWindow()
    try:
        win.file_ctrl.open(sample_inp_path)
        win._on_sweep_action()
        # v0.16.1:Sweep 顶层 tab 翻译为"批量算例" / "&Batch Cases"
        # _on_sweep_action 找包含 "批量算例" / "Batch" 的 tab
        top_labels = [win.tabs.tabText(i) for i in range(win.tabs.count())]
        sweep_top_idx = next(
            (i for i, t in enumerate(top_labels)
             if "批量算例" in t or "Batch" in t), None
        )
        assert sweep_top_idx is not None
        assert win.tabs.currentIndex() == sweep_top_idx
    finally:
        win.close()
        win.deleteLater()


def test_edit_top_stmt_value_writes_and_marks_dirty(qapp, sample_inp_path):
    """_edit_top_stmt_value 改顶层语句值 + 推 undo + dirty。"""
    from inp_tool_gui.main_window import MainWindow

    win = MainWindow()
    try:
        win.file_ctrl.open(sample_inp_path)
        win.edit_ctrl.mark_clean()
        assert win.edit_ctrl.is_dirty is False
        ok = win._edit_top_stmt_value("title", 0, "NewTitle")
        assert ok is True
        assert win.edit_ctrl.is_dirty is True
        assert win.edit_ctrl.undo_depth == 1
        title_stmt = next(
            s for s in win.file_ctrl.inp.top_stmts if s.keyword == "title"
        )
        assert title_stmt.values[0].raw == "NewTitle"
    finally:
        win.close()
        win.deleteLater()


def test_value_edit_requested_runs_dialog(qapp, sample_inp_path, monkeypatch):
    """_on_value_edit_requested 弹 ValueEditorDialog,设值后走 EditController。"""
    from PySide2.QtWidgets import QDialog
    from inp_tool_gui.main_window import MainWindow

    win = MainWindow()
    try:
        win.file_ctrl.open(sample_inp_path)
        win.edit_ctrl.mark_clean()

        from inp_tool_gui.widgets import value_editor as ve_mod

        class FakeDialog:
            Accepted = QDialog.Accepted

            def __init__(self, *a, **kw):
                self.new_value = 350.0

            def exec_(self):
                return QDialog.Accepted

        # 必须 patch main_window 已 import 的名字(模块级 import 在第一次
        # import 时绑定;改源模块 ve_mod.ValueEditorDialog 不会影响已绑定的引用)
        monkeypatch.setattr(
            "inp_tool_gui.main_window.ValueEditorDialog", FakeDialog
        )

        win._on_value_edit_requested(block_idx=0, keyword="reftem", value_idx=0)

        assert win.edit_ctrl.is_dirty is True
        assert win.edit_ctrl.undo_depth == 1
        from inp_tool.model import infer_type
        block = win.file_ctrl.inp.block_list[0]
        stmt = next(s for s in block.statements if s.keyword == "reftem")
        assert stmt.values[0].raw == "350.0"
        assert stmt.values[0].typed == infer_type("350.0")
    finally:
        win.close()
        win.deleteLater()


def test_act_detect_enabled_when_file_open(qapp, sample_inp_path):
    """open 后 act_detect 启用(原 Phase 2 是 disabled)。"""
    from inp_tool_gui.main_window import MainWindow

    win = MainWindow()
    try:
        win.file_ctrl.open(sample_inp_path)
        win._update_actions_enabled()
        assert win.act_detect.isEnabled() is True
        assert win.act_sweep.isEnabled() is True
    finally:
        win.close()
        win.deleteLater()


# 加到 test_gui_main_window_integration.py 末尾
import pytest
from pathlib import Path
from PySide2.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_has_search_bar_above_tree(qapp):
    from inp_tool_gui.main_window import MainWindow
    from inp_tool_gui.widgets.field_search_bar import FieldSearchBar
    win = MainWindow()
    try:
        assert len(win.findChildren(FieldSearchBar)) >= 1
    finally:
        win.close()
        win.deleteLater()


def test_main_window_has_sweep_tab(qapp):
    """v0.16.1:Sweep 顶层 tab 翻译为"批量算例" / "&Batch Cases"。

    Phase 7 / Task 7.1: Sweep 顶层 tab 现在包一个内嵌 QTabWidget,
    含 3 个子视图(Wizard / Form / YAML),共享一个 ConfigStore。
    ``sweep_form`` 仍作为 Form 子视图的别名(向后兼容老测试)。
    """
    from inp_tool_gui.main_window import MainWindow
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.widgets.sweep_yaml_editor import SweepYamlEditorView
    from PySide2.QtWidgets import QTabWidget
    from inp_tool.i18n_gui import tg

    win = MainWindow()
    try:
        # 找到翻译后的 Sweep 顶层 tab
        sweep_idx = None
        for i in range(win.tabs.count()):
            title = win.tabs.tabText(i)
            if tg("tab.sweep_zh") in title:
                sweep_idx = i
                break
        assert sweep_idx is not None, "MainWindow 没有 Sweep 顶层 tab"
        # Phase 7:Sweep 顶层 tab 容器是内嵌 QTabWidget
        inner = win.tabs.widget(sweep_idx)
        assert isinstance(inner, QTabWidget)
        assert inner.count() == 3
        # 3 个子视图:Wizard / SweepFormView / SweepYamlEditorView
        assert isinstance(inner.widget(0), SweepWizard)
        assert isinstance(inner.widget(1), SweepFormView)
        assert isinstance(inner.widget(2), SweepYamlEditorView)
        # 向后兼容别名
        assert win.sweep_form is win._sweep_form
        assert win._sweep_initial_store is win._sweep_store
    finally:
        win.close()
        win.deleteLater()


def test_sweep_inner_tab_shortcuts_switch_views(qapp):
    """Phase 7 / Task 7.1:Ctrl+1/2/3 切 Sweep 子 tab(Wizard/Form/YAML)。"""
    from inp_tool_gui.main_window import MainWindow
    from inp_tool.i18n_gui import tg
    from PySide2.QtGui import QKeySequence

    win = MainWindow()
    try:
        # 找内嵌 Sweep tab
        inner = None
        for i in range(win.tabs.count()):
            if tg("tab.sweep_zh") in win.tabs.tabText(i):
                inner = win.tabs.widget(i)
                break
        assert inner is not None
        assert inner.count() == 3
        # 默认是 0(Wizard)
        assert inner.currentIndex() == 0
        # 触发 Ctrl+2 → 切到 Form
        win._shortcut_form.activated.emit()
        assert inner.currentIndex() == 1
        # 触发 Ctrl+3 → 切到 YAML
        win._shortcut_yaml.activated.emit()
        assert inner.currentIndex() == 2
        # 触发 Ctrl+1 → 回到 Wizard
        win._shortcut_wizard.activated.emit()
        assert inner.currentIndex() == 0
    finally:
        win.close()
        win.deleteLater()


def test_sweep_subviews_share_config_store(qapp):
    """3 个子视图共享一个 ConfigStore:改 wizard → form 应同步(经 _on_view_store_changed)。

    这里直接调 wizard 的 store_changed emit(模拟"用户在 wizard 改了字段")。
    """
    from inp_tool_gui.main_window import MainWindow
    from inp_tool_gui.models.config_store import ConfigStore, AxisSpec

    win = MainWindow()
    try:
        # 初始 store 模板路径应为空
        assert win._sweep_store.template == ""
        assert win._sweep_form._edit_tpl.text() == ""
        assert win._sweep_wizard._edit_tpl.text() == ""

        # 构造新 store(模拟 wizard 改 template)
        new_store = win._sweep_store.replace(template="/tmp/foo.inp")
        # 直接 emit(等同用户 editingFinished 触发的 wizard.store_changed)
        win._sweep_wizard.store_changed.emit(new_store)

        # 中央 store 已更新
        assert win._sweep_store.template == "/tmp/foo.inp"
        # Form 子视图应同步(setText 被 _sync_from_store 调过)
        assert win._sweep_form._edit_tpl.text() == "/tmp/foo.inp"
        # YAML 子视图应同步(序列化回文本)
        yaml_text = win._sweep_yaml._editor.toPlainText()
        assert "/tmp/foo.inp" in yaml_text
    finally:
        win.close()
        win.deleteLater()