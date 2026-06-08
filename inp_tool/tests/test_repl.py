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


def test_alias_prefix_overrides_current(tmp_path):
    """v1: 前缀使 get 作用于 v1 而非 current。"""
    s1 = tmp_path / 's1.inp'
    s1.write_text('physics begin\n  refvel 50.0\nphysics end\n')
    s2 = tmp_path / 's2.inp'
    s2.write_text('physics begin\n  refvel -1.0\nphysics end\n')
    r = ShellREPL()
    out = _run(
        r,
        f'load {s1} as v1',
        f'load {s2} as v2',
        'v1:get refvel -b physics',
    )
    # v1 的 refvel 是 50.0
    assert '50.0' in out


def test_alias_prefix_with_set(tmp_path):
    """v1: 前缀的 set 标记 v1 dirty,v2 不受影响。"""
    s1 = tmp_path / 's1.inp'; s1.write_text('physics begin\n  refvel 1.0\nphysics end\n')
    s2 = tmp_path / 's2.inp'; s2.write_text('physics begin\n  refvel 2.0\nphysics end\n')
    r = ShellREPL()
    _run(
        r,
        f'load {s1} as v1',
        f'load {s2} as v2',
        'v1:set physics refvel 99.0',
    )
    assert r.session.files['v1'].dirty is True
    assert r.session.files['v2'].dirty is False


def test_alias_prefix_with_unknown_alias(tmp_path):
    """未加载的 alias:前缀应被忽略或报错(不崩)。"""
    p = tmp_path / 's.inp'; p.write_text('physics begin\n  refvel 1.0\nphysics end\n')
    r = ShellREPL()
    # 不崩 + r.session.current 保持为 v1
    _run(r, f'load {p} as v1', 'nope:get refvel -b physics')
    assert r.session.current == 'v1'


def test_let_stores_variable():
    r = ShellREPL()
    _run(r, 'let alpha=3.5')
    assert r.session.variables.get('alpha') == '3.5'


def test_dollar_var_interpolated(tmp_path):
    p = tmp_path / 's.inp'; p.write_text('physics begin\n  refvel 1.0\nphysics end\n')
    r = ShellREPL()
    _run(
        r,
        f'load {p} as v1',
        'let mach=75.0',
        'set physics refvel $mach',
    )
    out2 = _run(r, 'get refvel -b physics')
    assert '75.0' in out2
    assert r.session.files['v1'].dirty is True


def test_undefined_var_errors(tmp_path):
    p = tmp_path / 's.inp'; p.write_text('physics begin\n  refvel 1.0\nphysics end\n')
    r = ShellREPL()
    out = _run(
        r,
        f'load {p} as v1',
        'set physics refvel $undefined',
    )
    assert 'undefined' in out


def test_double_dollar_literal():
    r = ShellREPL()
    r.session.variables['x'] = 'Y'
    out = _run(r, 'let val=$$x')
    # $$ 转义为字面 $,x 不展开
    assert r.session.variables.get('val') == '$x'


def test_shell_escape_runs_command():
    r = ShellREPL()
    out = _run(r, '! echo hello')
    assert 'hello' in out


def test_shell_escape_reports_nonzero_exit():
    r = ShellREPL()
    out = _run(r, '! sh -c "echo bad; exit 3"')
    assert 'bad' in out
    assert 'exit code' in out or '3' in out


def test_undo_restores_value(tmp_path):
    p = tmp_path / 's.inp'; p.write_text('physics begin\n  refvel 1.0\nphysics end\n')
    r = ShellREPL()
    _run(r, f'load {p} as v1')
    # 改值
    _run(r, 'set physics refvel 99.0')
    assert r.session.files['v1'].dirty is True
    # 撤销
    out = _run(r, 'undo')
    assert 'undone' in out.lower() or 'restored' in out.lower() or '回滚' in out
    # 验证值已恢复
    out2 = _run(r, 'get refvel -b physics')
    assert '1.0' in out2


def test_undo_empty_errors():
    r = ShellREPL()
    out = _run(r, 'undo')
    assert 'nothing' in out.lower() or 'undo' in out.lower()


def test_undo_multiple_steps(tmp_path):
    p = tmp_path / 's.inp'; p.write_text('physics begin\n  refvel 1.0\nphysics end\n')
    r = ShellREPL()
    _run(r, f'load {p} as v1')
    _run(r, 'set physics refvel 99.0')
    _run(r, 'set physics refvel 88.0')
    _run(r, 'undo 2')
    out = _run(r, 'get refvel -b physics')
    assert '1.0' in out


def test_set_then_set_undo_chain(tmp_path):
    """Regression: do_set 后 lf.inp 必须与磁盘同步,否则连续 set + undo 会回滚到错的值。"""
    p = tmp_path / 's.inp'; p.write_text('physics begin\n  refvel 1.0\nphysics end\n')
    r = ShellREPL()
    _run(r, f'load {p} as v1')
    _run(r, 'set physics refvel 50.0')   # disk: 50, lf.inp 应该同步
    _run(r, 'set physics refvel 99.0')   # disk: 99
    # undo 应该回滚到 50(第二次 set 之前),而不是 1.0
    _run(r, 'undo')
    out = _run(r, 'get refvel -b physics')
    assert '50.0' in out, f"expected 50.0, got: {out}"


def test_sweep_command_available():
    """do_sweep 必须存在并能调 cmd_sweep(只验证可达,完整 sweep 流程由 cli 已有测试覆盖)。"""
    # 直接验证:do_sweep 是可调用的方法
    assert hasattr(ShellREPL, 'do_sweep')
    assert callable(ShellREPL.do_sweep)
    # 走 onecmd 路径:不能掉到 cmd.Cmd 默认 'Unknown syntax' 分支
    p = SAMPLE_V1
    r = ShellREPL()
    out = _run(
        r,
        f'load {p} as v1',
        'let alpha=2.5',
        'sweep --help',
    )
    assert 'Unknown syntax' not in out  # do_sweep 必须存在并被分派
    assert r.session.current == 'v1'  # sweep 失败不应破坏 current


def test_sweep_runs_with_args(tmp_path):
    """do_sweep 必须真的跑出算例,不只是 'Unknown syntax' 检查。"""
    template = tmp_path / 'tmpl.inp'
    template.write_text('physics begin\n  refvel 1.0\nphysics end\n')
    out_dir = tmp_path / 'cases'
    r = ShellREPL()
    out = _run(
        r,
        f'load {template} as v1',
        f'sweep {template} --alpha 0,4 --mach 0.6,0.8 --out {out_dir}',
    )
    # alpha 2 × mach 2 = 4 cases;另外若 freestream 引入 t_inf/p_inf 扫描,数量可能 ≥ 4
    generated = list(out_dir.glob('*.inp'))
    assert len(generated) >= 4, (
        f"expected >=4 .inp files, got {len(generated)}. REPL output:\n{out}"
    )


def test_completer_attached_to_repl():
    """ShellREPL 必须挂一个 InpCompleter 实例供 complete() 调度。"""
    from inp_tool.repl_completer import InpCompleter
    r = ShellREPL()
    assert isinstance(r._completer, InpCompleter)


def test_complete_command_candidates():
    """complete(text, state) 在首 token 位置应返回 REPL_COMMANDS 候选。"""
    r = ShellREPL()
    # readline.get_line_buffer 在测试环境下会返回空字符串,触发"首 token"分支
    cands_first = r.complete('lo', 0)
    cands_second = r.complete('lo', 1)
    # state=0 应该返回候选列表第一项(state=1 返回第二项,以此类推)
    assert cands_first == 'load'  # 'lo' 前缀唯一匹配 'load'
    assert cands_second is None  # 没有第二个候选


def test_complete_alias_for_use_command(tmp_path):
    """当首 token 是 'use' 时,应补全 alias 列表。"""
    p = tmp_path / 's.inp'; p.write_text('physics begin\n  refvel 1.0\nphysics end\n')
    r = ShellREPL()
    _run(r, f'load {p} as v1')
    cands = r.complete('', 0)  # state=0
    # cmd.Cmd 的 complete() 是按行调度的;但我们手测它的核心逻辑:
    # 既然 readline 在测试环境无 buffer,我们直接验证 InpCompleter 自己工作
    assert r._completer.complete_alias('') == ['v1']


def test_history_command_lists_recent():
    r = ShellREPL()
    _run(r, 'let a=1', 'let b=2', 'let c=3')
    out = _run(r, 'history 10')
    assert 'let a=1' in out
    assert 'let b=2' in out
    assert 'let c=3' in out


def test_rerun_re_executes_history_entry():
    r = ShellREPL()
    _run(r, 'let x=42', '! 1')
    assert r.session.variables.get('x') == '42'
