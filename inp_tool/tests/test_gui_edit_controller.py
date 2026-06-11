"""EditController 单元测试(纯 Python,无需 PySide2)。

阶段 3 的 undo/redo 业务逻辑,提前到阶段 2 commit 以便最大化 GREEN 验证。
依赖 :class:`FileController`(同包,无 Qt)。
"""
from pathlib import Path

import pytest

from inp_tool_gui.controllers.edit_controller import EditController
from inp_tool_gui.controllers.file_controller import FileController

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def fc():
    """每个测试都得到一个打开 sample_v1.inp 的 FileController。"""
    fc = FileController()
    fc.open(str(DATA_DIR / "sample_v1.inp"))
    return fc


@pytest.fixture
def ec(fc):
    """每个测试都得到一个绑到 fixture fc 的 EditController。"""
    return EditController(fc)


# --- 初始状态 ---------------------------------------------------------


def test_initial_state_clean_and_empty(ec):
    """新建的 EditController 不 dirty,无 undo/redo 可做。"""
    assert ec.is_dirty is False
    assert ec.can_undo is False
    assert ec.can_redo is False


def test_dirty_flag_after_edit(ec):
    """set_value 后 is_dirty 变 True。"""
    ec.set_value("physics", "refvel", 100.0)
    assert ec.is_dirty is True


def test_mark_clean_resets_dirty(ec):
    """mark_clean() 后 is_dirty 变 False。"""
    ec.set_value("physics", "refvel", 100.0)
    assert ec.is_dirty is True
    ec.mark_clean()
    assert ec.is_dirty is False


# --- undo -------------------------------------------------------------


def test_undo_restores_previous_value(ec, fc):
    """undo 恢复原值。"""
    original = fc.get_value("physics", "refvel")
    assert original == 50.0

    ec.set_value("physics", "refvel", 100.0)
    assert fc.get_value("physics", "refvel") == 100.0

    entry = ec.undo()
    assert entry is not None
    assert fc.get_value("physics", "refvel") == original
    assert ec.can_undo is False
    assert ec.can_redo is True


def test_undo_empty_returns_none(ec):
    """undo 空栈返回 None,不抛。"""
    assert ec.undo() is None


def test_multiple_undos(ec, fc):
    """多次 undo 顺序还原。"""
    ec.set_value("physics", "refvel", 100.0)
    ec.set_value("physics", "refvel", 200.0)
    assert fc.get_value("physics", "refvel") == 200.0

    ec.undo()
    assert fc.get_value("physics", "refvel") == 100.0
    ec.undo()
    assert fc.get_value("physics", "refvel") == 50.0
    assert ec.can_undo is False


# --- redo -------------------------------------------------------------


def test_redo_reapplies_undone(ec, fc):
    """redo 重新应用。"""
    ec.set_value("physics", "refvel", 100.0)
    ec.undo()
    assert fc.get_value("physics", "refvel") == 50.0

    entry = ec.redo()
    assert entry is not None
    assert fc.get_value("physics", "refvel") == 100.0


def test_redo_empty_returns_none(ec):
    """redo 空栈返回 None。"""
    assert ec.redo() is None


def test_new_edit_clears_redo_stack(ec, fc):
    """新 edit 后 redo_stack 清空(标准 undo/redo 行为)。"""
    ec.set_value("physics", "refvel", 100.0)
    ec.undo()
    assert ec.can_redo is True

    ec.set_value("physics", "refvel", 200.0)
    assert ec.can_redo is False


# --- undo round-trip with save ----------------------------------------


def test_undo_redo_round_trip_through_save(ec, fc, tmp_path):
    """改值 → save → undo → save → re-open 验证 undo 真的改了文件。"""
    ec.set_value("physics", "refvel", 100.0)
    fc.save(str(tmp_path / "after_edit.inp"))

    ec.undo()
    fc.save(str(tmp_path / "after_undo.inp"))

    fc2 = FileController()
    fc2.open(str(tmp_path / "after_edit.inp"))
    assert fc2.get_value("physics", "refvel") == 100.0

    fc3 = FileController()
    fc3.open(str(tmp_path / "after_undo.inp"))
    assert fc3.get_value("physics", "refvel") == 50.0
