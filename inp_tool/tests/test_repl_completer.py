"""InpCompleter 单元测试。"""
from pathlib import Path
from argparse import Namespace

import pytest

from inp_tool.repl_completer import InpCompleter
from inp_tool.repl_state import LoadedFile, ReplSession


@pytest.fixture
def session_with_file(tmp_path):
    """构造一个 session,加载一个最小 InpFile。"""
    from inp_tool.parser import parse_file
    p = tmp_path / 'sample.inp'
    p.write_text('physics begin\n  refvel 50.0\nphysics end\noptions begin\n  cfl 0.001\noptions end\n')
    inp = parse_file(str(p))
    s = ReplSession()
    s.load(p, alias='v1')
    return s


def test_complete_command_lists_all():
    s = ReplSession()
    c = InpCompleter(s)
    out = c.complete_command('')
    assert 'load' in out
    assert 'files' in out
    assert 'set' in out
    assert 'exit' in out


def test_complete_command_prefix_filter():
    s = ReplSession()
    c = InpCompleter(s)
    out = c.complete_command('lo')
    assert out == ['load']


def test_complete_alias_returns_loaded(session_with_file):
    c = InpCompleter(session_with_file)
    out = c.complete_alias('')
    assert 'v1' in out


def test_complete_alias_no_files():
    s = ReplSession()
    c = InpCompleter(s)
    assert c.complete_alias('') == []


def test_complete_block_returns_block_names(session_with_file):
    c = InpCompleter(session_with_file)
    out = c.complete_block('v1', '')
    assert 'physics' in out
    assert 'options' in out


def test_complete_block_prefix(session_with_file):
    c = InpCompleter(session_with_file)
    out = c.complete_block('v1', 'phy')
    assert out == ['physics']


def test_complete_block_unknown_alias():
    s = ReplSession()
    c = InpCompleter(s)
    assert c.complete_block('nope', '') == []


def test_complete_key_returns_keys(session_with_file):
    c = InpCompleter(session_with_file)
    out = c.complete_key('v1', 'physics', '')
    assert 'refvel' in out


def test_complete_key_prefix(session_with_file):
    c = InpCompleter(session_with_file)
    out = c.complete_key('v1', 'physics', 'ref')
    assert out == ['refvel']


def test_complete_shell_finds_ls():
    s = ReplSession()
    c = InpCompleter(s)
    out = c.complete_shell('ls')
    assert 'ls' in out or any(o.startswith('ls') for o in out)
