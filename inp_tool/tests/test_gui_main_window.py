"""MainWindow 集成测试(需 PySide2)。

阶段 2:菜单 / 工具栏 / 状态栏 / File actions / Edit actions / dirty 标志。

注意:这些测试**RED**(PySide2 未装,等装包后转 GREEN)。
"""
import os
from pathlib import Path

import pytest

# 在 import Qt 任何东西之前设置 platform
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def qapp():
    """共享 QApplication 单例。"""
    from PySide2.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    # pytest session 结束时由 QApplication 自然销毁


@pytest.fixture
def win(qapp):
    """每个测试一个干净的 MainWindow。"""
    from inp_tool_gui.main_window import MainWindow
    w = MainWindow()
    yield w
    w.close()
    w.deleteLater()


# --- 构造 / 控制器绑定 ------------------------------------------------


def test_main_window_constructs_with_controllers(win):
    """构造时绑好 file/edit/sweep controller。"""
    assert win.file_ctrl is not None
    assert win.edit_ctrl is not None
    assert win.sweep_ctrl is not None
    assert win.edit_ctrl._file_ctrl is win.file_ctrl  # edit 绑 file


def test_main_window_title_initial(win):
    """未打开时标题 = APP_NAME vAPP_VERSION。"""
    title = win.windowTitle()
    assert "inp-tool-gui" in title
    assert "0.10.0-dev" in title
    assert "*" not in title  # 未 dirty


# --- 菜单 -------------------------------------------------------------


def test_main_window_has_file_edit_sweep_detect_help_menus(win):
    """5 大菜单齐全。"""
    titles = [a.text() for a in win.menuBar().actions()]
    assert any("文件" in t for t in titles)
    assert any("编辑" in t for t in titles)
    assert any("Sweep" in t for t in titles)
    assert any("检测" in t for t in titles)
    assert any("帮助" in t for t in titles)


# --- 工具栏 -----------------------------------------------------------


def test_main_window_toolbar_has_actions(win):
    """工具栏有 open/save/undo/redo 4 个 action(可能含 separator)。"""
    toolbars = win.findChildren(__import__("PySide2.QtWidgets", fromlist=["QToolBar"]).QToolBar)
    assert toolbars, "至少有一个工具栏"
    actions = [a.text() for a in toolbars[0].actions() if a.text()]
    assert any("打开" in t for t in actions)
    assert any("保存" in t for t in actions)
    assert any("撤销" in t for t in actions)
    assert any("重做" in t for t in actions)


# --- 状态栏 -----------------------------------------------------------


def test_main_window_statusbar_shows_unopened_initially(win):
    """未打开时状态栏左侧显示 (未打开文件)。"""
    assert win._status_path.text() == "(未打开文件)"


# --- File actions -----------------------------------------------------


def test_main_window_save_disabled_when_no_file(win):
    """未 open 时 save 灰掉。"""
    assert win.act_save.isEnabled() is False
    assert win.act_save_as.isEnabled() is False


def test_main_window_open_makes_save_enabled(win):
    """open 后 save / save_as / sweep 可用。"""
    win.file_ctrl.open(str(DATA_DIR / "sample_v1.inp"))
    win._refresh_after_open()
    assert win.act_save.isEnabled() is True
    assert win.act_save_as.isEnabled() is True
    assert win.act_sweep.isEnabled() is True


# --- Edit actions -----------------------------------------------------


def test_main_window_undo_redo_disabled_initially(win):
    """未改值时 undo/redo 灰掉。"""
    assert win.act_undo.isEnabled() is False
    assert win.act_redo.isEnabled() is False


def test_main_window_undo_enabled_after_edit(win):
    """改值后 undo 可用,redo 仍灰。"""
    win.file_ctrl.open(str(DATA_DIR / "sample_v1.inp"))
    win.edit_ctrl.set_value("physics", "refvel", 100.0)
    win._refresh_after_edit()
    assert win.act_undo.isEnabled() is True
    assert win.act_redo.isEnabled() is False


def test_main_window_redo_enabled_after_undo(win):
    """undo 后 redo 可用。"""
    win.file_ctrl.open(str(DATA_DIR / "sample_v1.inp"))
    win.edit_ctrl.set_value("physics", "refvel", 100.0)
    win._refresh_after_edit()
    win.edit_ctrl.undo()
    win._refresh_after_edit()
    assert win.act_undo.isEnabled() is False
    assert win.act_redo.isEnabled() is True


# --- dirty / 标题 -----------------------------------------------------


def test_main_window_title_dirty_marker_on_edit(win):
    """改值后标题含 *,save 后清掉。"""
    win.file_ctrl.open(str(DATA_DIR / "sample_v1.inp"))
    win.edit_ctrl.set_value("physics", "refvel", 100.0)
    win._refresh_after_edit()
    assert "*" in win.windowTitle()

    win.edit_ctrl.mark_clean()
    win._refresh_after_save()
    assert "*" not in win.windowTitle()


def test_main_window_statusbar_dirty_marker(win):
    """dirty 时状态栏显示 ●。"""
    win.file_ctrl.open(str(DATA_DIR / "sample_v1.inp"))
    win.edit_ctrl.set_value("physics", "refvel", 100.0)
    win._refresh_after_edit()
    assert win._status_dirty.text() == "●"
    win.edit_ctrl.mark_clean()
    win._refresh_after_save()
    assert win._status_dirty.text() == ""
