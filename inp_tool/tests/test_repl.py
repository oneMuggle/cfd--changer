"""ShellREPL 行为测试。onecmd 模拟用户输入,捕获 stdout/stderr 断言。"""
import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from inp_tool.repl import ShellREPL
from inp_tool import i18n


SAMPLE_V1 = Path(__file__).parent / 'data' / 'sample_v1.inp'
SAMPLE_V2 = Path(__file__).parent / 'data' / 'sample_v2.inp'


@pytest.fixture(autouse=True)
def _force_en_for_default_tests():
    """本文件所有测试强制英文模式(中文化在 test_repl_zh.py 单独测)。

    PR #2 默认语言改为 zh,为了不破坏现有英文断言,这里 autouse 切到 en。
    """
    i18n.set_lang("en")
    yield
    i18n.set_lang("zh")  # 恢复默认


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


def test_main_runs_script_from_non_tty_stdin(monkeypatch, tmp_path):
    """Bug 2 回归测试:非 tty stdin 应逐行处理并返回 0。"""
    from inp_tool.repl import main
    import sys
    import io
    p = tmp_path / 's.inp'
    p.write_text('physics begin\n  refvel 1.0\nphysics end\n')
    monkeypatch.setattr(sys, 'stdin', io.StringIO('files\nexit\n'))
    monkeypatch.setattr(sys, 'stdout', io.StringIO())
    # isatty() 需要返回 False,默认 StringIO 的 isatty() 就是 False
    rc = main()
    assert rc == 0


def test_module_importable_without_readline(monkeypatch):
    """Bug 1 回归测试:repl 模块在 readline 不可用时仍能 import。"""
    import sys
    # 模拟 readline 不存在
    saved_readline = sys.modules.get('readline')
    sys.modules['readline'] = None  # 让 import readline 失败
    try:
        # 强制重新 import
        if 'inp_tool.repl' in sys.modules:
            del sys.modules['inp_tool.repl']
        import inp_tool.repl  # 应当不抛 ModuleNotFoundError
        assert hasattr(inp_tool.repl, 'ShellREPL')
    finally:
        if saved_readline is not None:
            sys.modules['readline'] = saved_readline
        elif 'readline' in sys.modules:
            del sys.modules['readline']
        if 'inp_tool.repl' in sys.modules:
            del sys.modules['inp_tool.repl']


# ============================================================
# aero command tests
# ============================================================

# 一个最小可用的 .inp 模板,含 guiopts + physics
AERO_TEMPLATE = """\
# aero test fixture
system begin
title "aero test"
system end
guiopts begin
  aero_alpha 0.0
  aerobeta 0.0
  aero_ma 0.8
  aero_u 272.16
  aero_v 0.0
  aero_w 0.0
  aero_temp 288.0
  aero_pres 101325.0
guiopts end
physics begin
  refvel 272.16
  reftem 288.0
  refpre 101325.0
  cfl 0.001
physics end
"""


def _aero_load(tmp_path, name='case.inp', body=None):
    """写一个含 guiopts+physics 的 .inp,返回 path。"""
    p = tmp_path / name
    p.write_text(body if body is not None else AERO_TEMPLATE)
    return p


def test_aero_show_no_args(tmp_path):
    p = _aero_load(tmp_path)
    r = ShellREPL()
    out = _run(r, f'load {p} as v1', 'aero')
    # 摘要含关键 token
    assert 'Ma=0.8' in out
    assert 'α=0.0°' in out
    assert 'refvel=' in out
    # 不应报错
    assert 'error' not in out.lower()


def test_aero_set_alpha(tmp_path):
    p = _aero_load(tmp_path)
    r = ShellREPL()
    _run(r, f'load {p} as v1', 'aero alpha=5')
    lf = r.session.files['v1']
    # aero_alpha 改到 5.0
    gb = lf.inp.get_block('guiopts', 0)
    v = gb.get_value('aero_alpha').typed
    assert abs(float(v) - 5.0) < 1e-6
    # U/W 应被重算(alpha=5° 时 W != 0)
    u = float(gb.get_value('aero_u').typed)
    w = float(gb.get_value('aero_w').typed)
    assert abs(u) > 0
    assert abs(w) > 0
    # V 仍为 0(beta=0)
    v_val = float(gb.get_value('aero_v').typed)
    assert abs(v_val) < 1e-6


def test_aero_set_multiple_keys(tmp_path):
    p = _aero_load(tmp_path)
    r = ShellREPL()
    _run(r, f'load {p} as v1', 'aero Ma=0.85 alpha=10 beta=2')
    lf = r.session.files['v1']
    gb = lf.inp.get_block('guiopts', 0)
    assert abs(float(gb.get_value('aero_ma').typed) - 0.85) < 1e-6
    assert abs(float(gb.get_value('aero_alpha').typed) - 10.0) < 1e-6
    assert abs(float(gb.get_value('aerobeta').typed) - 2.0) < 1e-6
    # U/V/W 都应非零
    u = float(gb.get_value('aero_u').typed)
    v_val = float(gb.get_value('aero_v').typed)
    w = float(gb.get_value('aero_w').typed)
    assert abs(u) > 0 and abs(v_val) > 0 and abs(w) > 0


def test_aero_set_T(tmp_path):
    p = _aero_load(tmp_path)
    r = ShellREPL()
    _run(r, f'load {p} as v1', 'aero T=300')
    lf = r.session.files['v1']
    gb = lf.inp.get_block('guiopts', 0)
    pb = lf.inp.get_block('physics', 0)
    # T 改了
    assert abs(float(gb.get_value('aero_temp').typed) - 300.0) < 1e-6
    # reftem 也跟改
    assert abs(float(pb.get_value('reftem').typed) - 300.0) < 1e-6
    # refvel 被重算(T 变了声速变了,即使 Ma/alpha/beta 不变,refvel 也变)
    refvel = float(pb.get_value('refvel').typed)
    assert refvel > 0
    # 与 |V| 一致
    import math
    u = float(gb.get_value('aero_u').typed)
    v_val = float(gb.get_value('aero_v').typed)
    w = float(gb.get_value('aero_w').typed)
    assert abs(refvel - math.sqrt(u*u + v_val*v_val + w*w)) < 1e-3


def test_aero_preserves_unchanged_fields(tmp_path):
    """v0.5.1 fix 风格:只改 alpha 时,Ma 仍为模板值 0.8。"""
    p = _aero_load(tmp_path)
    r = ShellREPL()
    _run(r, f'load {p} as v1', 'aero alpha=5')
    lf = r.session.files['v1']
    gb = lf.inp.get_block('guiopts', 0)
    # Ma 应保留 0.8(模板值)
    assert abs(float(gb.get_value('aero_ma').typed) - 0.8) < 1e-6
    # T/p 也保留
    assert abs(float(gb.get_value('aero_temp').typed) - 288.0) < 1e-6
    assert abs(float(gb.get_value('aero_pres').typed) - 101325.0) < 1e-6


def test_aero_marks_dirty_and_undoable(tmp_path):
    p = _aero_load(tmp_path)
    r = ShellREPL()
    _run(r, f'load {p} as v1', 'aero alpha=10')
    lf = r.session.files['v1']
    # 标 dirty
    assert lf.dirty is True
    # undo 应能恢复
    out = _run(r, 'undo')
    assert 'undone' in out.lower() or 'restored' in out.lower() or '回滚' in out
    # 验证 alpha 恢复
    lf = r.session.files['v1']
    gb = lf.inp.get_block('guiopts', 0)
    assert abs(float(gb.get_value('aero_alpha').typed) - 0.0) < 1e-6


def test_aero_unknown_key_errors(tmp_path):
    p = _aero_load(tmp_path)
    r = ShellREPL()
    out = _run(r, f'load {p} as v1', 'aero foo=1')
    assert 'unknown key' in out
    assert 'foo' in out
    # 状态未变
    lf = r.session.files['v1']
    gb = lf.inp.get_block('guiopts', 0)
    assert abs(float(gb.get_value('aero_ma').typed) - 0.8) < 1e-6
    assert lf.dirty is False


def test_aero_no_current_file_errors():
    r = ShellREPL()
    out = _run(r, 'aero alpha=5')
    assert 'no file is current' in out
    assert 'load' in out


def test_aero_malformed_key_value_errors(tmp_path):
    p = _aero_load(tmp_path)
    r = ShellREPL()
    out = _run(r, f'load {p} as v1', 'aero alpha')
    assert 'expected KEY=VALUE' in out
    assert "'alpha'" in out
    lf = r.session.files['v1']
    assert lf.dirty is False


def test_aero_non_numeric_value_errors(tmp_path):
    p = _aero_load(tmp_path)
    r = ShellREPL()
    out = _run(r, f'load {p} as v1', 'aero alpha=abc')
    assert 'must be a number' in out
    assert "'abc'" in out
    lf = r.session.files['v1']
    assert lf.dirty is False


def test_aero_does_not_write_to_disk_without_save(tmp_path):
    """Bug fix: 'aero' command must NOT write to disk without 'save'.

    REPL 合约:`aero` 只改 in-memory 状态 + 标 dirty,`save` 才是显式
    commit。'aero' 偷偷写盘会破坏 `undo`,也与 `set` / `let` 行为不一致。
    """
    import hashlib
    p = tmp_path / 's.inp'
    p.write_text('system begin\nsystem end\nguiopts begin\n'
                 'aero_pres 1.013250e+005\naero_temp 2.880000e+002\n'
                 'aero_u 3.000000e+001\naero_v 0.0\naero_w 0.0\n'
                 'aero_ma 8.000000e-001\naero_alpha 0.000000e+000\n'
                 'aerobeta 0.000000e+000\naero_re 1.000000e+006\n'
                 'guiopts end\n'
                 'physics begin\nrefvel -1.0\nreftem 2.880000e+002\n'
                 'refpre 1.013250e+005\nphysics end\n')
    before_hash = hashlib.md5(p.read_bytes()).hexdigest()
    r = ShellREPL()
    _run(r, f'load {p} as v1', 'aero alpha=5')
    after_hash = hashlib.md5(p.read_bytes()).hexdigest()
    assert before_hash == after_hash, (
        f"aero secretly wrote to disk! before={before_hash[:8]} after={after_hash[:8]}"
    )
    # dirty 标志应仍被设置(in-memory 状态已变)
    assert r.session.files['v1'].dirty is True
    # in-memory 状态确实改了(通过 aero 查询验证)
    out = _run(r, 'aero')
    assert 'α=5.0' in out or 'α=5' in out


# ======================================================================
# sweep-config 命令(2026-06-09 计划:项 3)
# ======================================================================
import json as _json


def test_sweep_config_valid_shows_preview(tmp_path, monkeypatch):
    """sweep-config <valid.json> 应先打印 case 清单再问 y/N,默认 N 时不写盘"""
    cfg = tmp_path / "s.json"
    cfg.write_text(_json.dumps({
        "template":   str(SAMPLE_V1),
        "output_dir": str(tmp_path / "out"),
        "sweeps":     {"alpha": [0, 5]},
    }))
    r = ShellREPL()
    # mock input() 返回 'n' 拒绝
    monkeypatch.setattr('builtins.input', lambda *_a, **_k: 'n')
    out = _run(r, f'sweep-config {cfg}')
    assert 'PREVIEW' in out
    assert 'alpha=0' in out
    assert 'alpha=5' in out
    # N 拒绝 → 不写盘
    assert 'cancelled' in out.lower()
    assert not (tmp_path / "out").exists()


def test_sweep_config_invalid_prints_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"template": "x"}')  # 缺 output_dir / sweeps
    r = ShellREPL()
    out = _run(r, f'sweep-config {bad}')
    assert 'error' in out.lower() or 'invalid' in out.lower()


def test_sweep_config_yes_flag_skips_confirm(tmp_path, monkeypatch):
    """-y/--yes 应直接写盘不询问"""
    cfg = tmp_path / "s.json"
    cfg.write_text(_json.dumps({
        "template":   str(SAMPLE_V1),
        "output_dir": str(tmp_path / "out"),
        "sweeps":     {"alpha": [0, 5]},  # 2 值,默认 naming 才会含 {alpha}
    }))
    r = ShellREPL()
    # 防御:即使 input() 被 monkeypatch,也不应被调用
    import builtins
    def _explode(*_a, **_k):
        raise AssertionError("input() should not be called with -y")
    monkeypatch.setattr(builtins, 'input', _explode)
    out = _run(r, f'sweep-config -y {cfg}')
    assert 'generated' in out.lower()
    # 默认 naming = "case_{alpha}" → case_0.inp, case_5.inp
    assert (tmp_path / "out" / "case_0.inp").exists()
    assert (tmp_path / "out" / "case_5.inp").exists()


def test_sweep_config_missing_file_errors():
    r = ShellREPL()
    out = _run(r, 'sweep-config /no/such/file.json')
    assert 'not found' in out.lower() or 'error' in out.lower()
