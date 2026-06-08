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
