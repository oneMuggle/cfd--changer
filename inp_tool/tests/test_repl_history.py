"""repl_history 单测。"""
from pathlib import Path

import pytest

from inp_tool.repl_history import HistoryStore


def test_load_empty_if_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    h = HistoryStore()
    assert h.load() == []


def test_append_and_save(tmp_path, monkeypatch):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    h = HistoryStore()
    h.append('load foo.inp')
    h.append('set physics refvel 50.0')
    h.save()
    f = tmp_path / '.inp_history'
    assert f.exists()
    assert f.read_text().splitlines() == ['load foo.inp', 'set physics refvel 50.0']


def test_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    f = tmp_path / '.inp_history'
    f.write_text('cmd1\ncmd2\n')
    h = HistoryStore()
    out = h.load()
    assert out == ['cmd1', 'cmd2']


def test_maxlen_fifo(tmp_path, monkeypatch):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    h = HistoryStore(maxlen=3)
    for i in range(5):
        h.append(f'cmd{i}')
    h.save()
    out = (tmp_path / '.inp_history').read_text().splitlines()
    assert out == ['cmd2', 'cmd3', 'cmd4']


def test_bind_readline_returns_false_on_windows(monkeypatch):
    """Windows 上 bind_readline 必须直接返回 False(无 readline),覆盖率要算上这 2 行。"""
    from inp_tool.repl_history import HistoryStore
    monkeypatch.setattr('sys.platform', 'win32')
    h = HistoryStore()
    assert h.bind_readline() is False
