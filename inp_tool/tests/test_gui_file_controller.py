"""FileController 单元测试(纯 Python,无需 PySide2)。

阶段 2.1-2.4:open / save / set_value / round-trip。

这些测试**不**依赖 PySide2,只验证业务逻辑层(包装 inp_tool core)。
PySide2 装包后才被 test_gui_smoke.py 覆盖 Qt 集成。
"""
from pathlib import Path

import pytest

from inp_tool_gui.controllers.file_controller import FileController

DATA_DIR = Path(__file__).parent / "data"


# --- open / save -------------------------------------------------------


def test_initial_state_is_closed():
    """新构造的 FileController 没有打开文件。"""
    fc = FileController()
    assert fc.is_open is False
    assert fc.inp is None
    assert fc.current_path is None


def test_open_returns_inp_file():
    """open() 返回 InpFile,current_path 已设。"""
    fc = FileController()
    inp = fc.open(str(DATA_DIR / "sample_v1.inp"))
    assert inp is not None
    assert fc.current_path == DATA_DIR / "sample_v1.inp"
    assert fc.is_open is True


def test_open_nonexistent_raises():
    """open 不存在的路径应抛异常(inp_tool parser 的行为)。"""
    fc = FileController()
    with pytest.raises(Exception):
        fc.open(str(DATA_DIR / "does_not_exist.inp"))


def test_save_without_open_raises():
    """未 open 就 save 应明确报错。"""
    fc = FileController()
    with pytest.raises(RuntimeError):
        fc.save(str(DATA_DIR / "out.inp"))


def test_save_round_trip(tmp_path):
    """open → save → re-open,blocks 数一致。"""
    fc = FileController()
    original = fc.open(str(DATA_DIR / "sample_v1.inp"))
    out = tmp_path / "out.inp"
    fc.save(str(out))
    assert out.exists()

    fc2 = FileController()
    reloaded = fc2.open(str(out))
    assert len(reloaded.block_list) == len(original.block_list)


# --- set_value / get_value --------------------------------------------


def test_get_value_existing_keyword():
    """取现有 block + keyword 的 typed 值。"""
    fc = FileController()
    fc.open(str(DATA_DIR / "sample_v1.inp"))
    assert fc.get_value("physics", "refvel") == 50.0
    assert fc.get_value("system", "cfl") == 0.001


def test_get_value_unknown_block_returns_none():
    """未知 block 返回 None,不抛。"""
    fc = FileController()
    fc.open(str(DATA_DIR / "sample_v1.inp"))
    assert fc.get_value("nonexistent_block", "x") is None


def test_get_value_unknown_keyword_returns_none():
    """block 存在但 keyword 不存在返回 None。"""
    fc = FileController()
    fc.open(str(DATA_DIR / "sample_v1.inp"))
    assert fc.get_value("physics", "nonexistent_keyword") is None


def test_set_value_persists_through_save(tmp_path):
    """改值 → save → 重新 open,新值还在(round-trip 核心场景)。"""
    fc = FileController()
    fc.open(str(DATA_DIR / "sample_v1.inp"))
    assert fc.set_value("physics", "refvel", 100.0) is True

    out = tmp_path / "out.inp"
    fc.save(str(out))

    fc2 = FileController()
    fc2.open(str(out))
    assert fc2.get_value("physics", "refvel") == 100.0


def test_set_value_unknown_block_returns_false():
    """未知 block 返回 False。"""
    fc = FileController()
    fc.open(str(DATA_DIR / "sample_v1.inp"))
    assert fc.set_value("nonexistent_block", "x", 1) is False


def test_set_value_append_if_keyword_missing():
    """block 存在但 keyword 缺失 → append 新 Stmt,get_value 取得到。"""
    fc = FileController()
    fc.open(str(DATA_DIR / "sample_v1.inp"))
    assert fc.set_value("physics", "newword", 42.0) is True
    assert fc.get_value("physics", "newword") == 42.0


def test_set_value_unopened_raises():
    """未 open 就 set_value 应报错。"""
    fc = FileController()
    with pytest.raises(RuntimeError):
        fc.set_value("physics", "refvel", 100.0)
