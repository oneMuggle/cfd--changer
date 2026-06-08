"""ShellREPL 行为测试。onecmd 模拟用户输入,捕获 stdout/stderr 断言。"""
import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from inp_tool.repl import ShellREPL


SAMPLE_V1 = Path(__file__).parent / 'data' / 'sample_v1.inp'
SAMPLE_V2 = Path(__file__).parent / 'data' / 'sample_v2.inp'


def _run(repl, *lines):
    """喂入多行命令,返回 stdout + stderr 的合并输出。"""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        for line in lines:
            repl.onecmd(line)
    return out.getvalue() + err.getvalue()


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


def test_load_lists_in_files(tmp_path):
    p = tmp_path / 'mcfd.inp'
    p.write_text('placeholder\n')
    r = ShellREPL()
    out = _run(r, f'load {p}', 'files')
    assert 'mcfd' in out
    assert 'current' in out or '*' in out  # current 标记


def test_load_nonexistent_errors(tmp_path):
    r = ShellREPL()
    out = _run(r, f'load {tmp_path}/nope.inp')
    assert 'not found' in out
    assert r.session.current is None


def test_load_with_explicit_alias(tmp_path):
    p = tmp_path / 'mcfd.inp'; p.write_text('x')
    r = ShellREPL()
    _run(r, f'load {p} as v1')
    assert r.session.current == 'v1'
    assert 'v1' in r.session.files


def test_use_switches_current(tmp_path):
    p1 = tmp_path / 'a.inp'; p1.write_text('x')
    p2 = tmp_path / 'b.inp'; p2.write_text('x')
    r = ShellREPL()
    _run(r, f'load {p1} as a', f'load {p2} as b', 'use a')
    assert r.session.current == 'a'
    assert r.prompt == 'inp[a]> '


def test_use_unknown_errors():
    r = ShellREPL()
    out = _run(r, 'use nope')
    assert 'not loaded' in out or 'nope' in out


def test_unload_clean_succeeds(tmp_path):
    p = tmp_path / 'a.inp'; p.write_text('x')
    r = ShellREPL()
    _run(r, f'load {p} as a', 'unload a')
    assert 'a' not in r.session.files


def test_unload_dirty_errors_until_forced(tmp_path):
    p = tmp_path / 'a.inp'; p.write_text('x')
    r = ShellREPL()
    _run(r, f'load {p} as a')
    r.session.files['a'].dirty = True
    out = _run(r, 'unload a')
    assert 'unsaved' in out or 'dirty' in out
    assert 'a' in r.session.files  # 没卸掉
    out = _run(r, 'unload a -f')
    assert 'a' not in r.session.files


def test_status_shows_dirty_count(tmp_path):
    p = tmp_path / 'a.inp'; p.write_text('x')
    r = ShellREPL()
    _run(r, f'load {p} as a')
    r.session.files['a'].dirty = True
    out = _run(r, 'status')
    assert 'a' in out
    assert 'dirty' in out or 'unsaved' in out


def test_save_clears_dirty(tmp_path):
    p = tmp_path / 'a.inp'; p.write_text('x\n')
    r = ShellREPL()
    _run(r, f'load {p} as a')
    r.session.files['a'].dirty = True
    out = _run(r, 'save')
    assert r.session.files['a'].dirty is False


def test_save_as_creates_new_file(tmp_path):
    p = tmp_path / 'a.inp'; p.write_text('x\n')
    new_p = tmp_path / 'b.inp'
    r = ShellREPL()
    _run(r, f'load {p} as a')
    out = _run(r, f'save as {new_p}')
    assert new_p.exists()
    assert r.session.files['a'].dirty is False
    # alias 的 path 指向新文件
    assert r.session.files['a'].path == new_p


def test_unload_force_flag_in_any_position(tmp_path):
    """I3 修复:unload -f a 与 unload a -f 都要工作。"""
    p = tmp_path / 'a.inp'; p.write_text('x')
    r = ShellREPL()
    _run(r, f'load {p} as a')
    r.session.files['a'].dirty = True
    _run(r, 'unload -f a')  # -f 在 alias 前
    assert 'a' not in r.session.files


def test_unload_unknown_alias_returns_cleanly(tmp_path):
    """I1 修复:unload 不存在的 alias 时,_err 后无 fall-through。"""
    r = ShellREPL()
    out = _run(r, 'unload nope')
    assert 'not loaded' in out
    # prompt 保持默认(没有 current)
    assert r.prompt == 'inp> '


def test_info_runs_on_current(tmp_path):
    p = tmp_path / 's1.inp'
    p.write_text(SAMPLE_V1.read_text())
    r = ShellREPL()
    out = _run(r, f'load {p}', 'info')
    assert '块列表' in out or 'block' in out.lower()
    assert 'physics' in out


def test_get_reads_value(tmp_path):
    p = tmp_path / 's1.inp'
    p.write_text(SAMPLE_V1.read_text())
    r = ShellREPL()
    out = _run(r, f'load {p}', 'get refvel -b physics')
    assert 'refvel' in out
    assert '50.0' in out


def test_get_missing_key_errors(tmp_path):
    p = tmp_path / 's1.inp'
    p.write_text(SAMPLE_V1.read_text())
    r = ShellREPL()
    out = _run(r, f'load {p}', 'get nope -b physics')
    assert '不存在' in out or 'not found' in out.lower()


def test_set_marks_dirty(tmp_path):
    p = tmp_path / 's1.inp'
    p.write_text(SAMPLE_V1.read_text())
    r = ShellREPL()
    _run(r, f'load {p} as v1', 'set physics refvel 75.0')
    assert r.session.files['v1'].dirty is True


def test_diff_between_two_files(tmp_path):
    p1 = tmp_path / 'v1.inp'
    p2 = tmp_path / 'v2.inp'
    p1.write_text(SAMPLE_V1.read_text())
    p2.write_text(SAMPLE_V2.read_text())
    r = ShellREPL()
    out = _run(
        r,
        f'load {p1} as v1',
        f'load {p2} as v2',
        'use v1',
        'diff v2',
    )
    assert 'refvel' in out
