"""ShellREPL 行为测试。onecmd 模拟用户输入,捕获 stdout 断言。"""
import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from inp_tool.repl import ShellREPL


def _run(repl, *lines):
    """喂入多行命令,返回捕获的 stdout。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        for line in lines:
            repl.onecmd(line)
    return buf.getvalue()


def test_prompt_default():
    r = ShellREPL()
    assert r.prompt == 'inp> '


def test_prompt_changes_when_file_loaded(tmp_path):
    p = tmp_path / 'x.inp'; p.write_text('placeholder')
    r = ShellREPL()
    _run(r, f'load {p}')
    assert r.prompt == 'inp[x]> '  # 'x' 是 stem


def test_intro_banner_present():
    r = ShellREPL()
    assert 'interactive shell' in r.intro
    assert "'help'" in r.intro
    assert "'exit'" in r.intro


def test_empty_line_does_not_crash():
    r = ShellREPL()
    out = _run(r, '')
    assert out == ''  # 无输出,无异常
