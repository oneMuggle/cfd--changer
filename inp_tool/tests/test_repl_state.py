"""ReplSession / LoadedFile / UndoLog 数据类单测。"""
from pathlib import Path

import pytest

from inp_tool.repl_state import LoadedFile, ReplSession, UndoEntry, UndoLog


def test_loadedfile_starts_clean():
    lf = LoadedFile(alias='v1', path=Path('/tmp/x.inp'), inp=None)
    assert lf.dirty is False
    assert lf.last_saved_text is None


def test_undolog_push_pop():
    log = UndoLog()
    assert len(log) == 0
    e = UndoEntry(alias='v1', block='physics', key='refvel', old_values=[50.0])
    log.push(e)
    assert len(log) == 1
    popped = log.pop()
    assert popped is e
    assert len(log) == 0


def test_undolog_pop_empty_returns_none():
    log = UndoLog()
    assert log.pop() is None


def test_undolog_respects_maxlen():
    log = UndoLog(maxlen=3)
    for i in range(5):
        log.push(UndoEntry(alias='v', block='b', key=f'k{i}', old_values=[i]))
    assert len(log) == 3
    # deque 留 k2/k3/k4,pop 出栈序 k4/k3/k2 (LIFO: undo 栈先回滚最近一次)
    assert [log.pop().key for _ in range(3)] == ['k4', 'k3', 'k2']


def test_replsession_starts_empty():
    s = ReplSession()
    assert s.files == {}
    assert s.current is None
    assert len(s.undo) == 0
    assert s.variables == {}


def test_load_adds_file_and_sets_current(tmp_path):
    s = ReplSession()
    fake_path = tmp_path / 'mcfd.inp'
    fake_path.write_text('placeholder')
    s.load(fake_path, alias='v1')
    assert 'v1' in s.files
    assert s.current == 'v1'
    assert s.files['v1'].path == fake_path


def test_load_default_alias_is_stem(tmp_path):
    s = ReplSession()
    p = tmp_path / 'mcfd_v1.inp'
    p.write_text('x')
    s.load(p)
    assert s.current == 'mcfd_v1'


def test_load_collision_appends_suffix(tmp_path):
    s = ReplSession()
    p1 = tmp_path / 'a.inp'; p1.write_text('x')
    p2 = tmp_path / 'a_2.inp'; p2.write_text('x')  # 同 stem 'a' 冲突
    s.load(p1, alias='a')
    s.load(p2, alias='a')  # 显式 alias='a' 与已有冲突
    assert 'a' in s.files
    assert 'a_2' in s.files
    # 第二次 load 的 current 指向新别名
    assert s.current == 'a_2'


def test_unload_removes_file(tmp_path):
    s = ReplSession()
    p = tmp_path / 'a.inp'; p.write_text('x')
    s.load(p, alias='a')
    s.unload('a')
    assert 'a' not in s.files


def test_unload_dirty_raises_without_force(tmp_path):
    s = ReplSession()
    p = tmp_path / 'a.inp'; p.write_text('x')
    s.load(p, alias='a')
    s.files['a'].dirty = True
    with pytest.raises(RuntimeError, match='unsaved'):
        s.unload('a')
    # -f 强卸通过
    s.unload('a', force=True)
    assert 'a' not in s.files


def test_unload_current_clears_pointer(tmp_path):
    s = ReplSession()
    p = tmp_path / 'a.inp'; p.write_text('x')
    s.load(p, alias='a')
    s.unload('a')
    assert s.current is None


def test_use_switches_current(tmp_path):
    s = ReplSession()
    p1 = tmp_path / 'a.inp'; p1.write_text('x')
    p2 = tmp_path / 'b.inp'; p2.write_text('x')
    s.load(p1, alias='a')
    s.load(p2, alias='b')
    assert s.current == 'b'
    s.use('a')
    assert s.current == 'a'


def test_use_unknown_raises(tmp_path):
    s = ReplSession()
    with pytest.raises(KeyError):
        s.use('nope')
