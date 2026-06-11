"""v0.9.1: REPL 方程感知命令(detect / turb / 2t)测试"""
from pathlib import Path
import io
from contextlib import redirect_stdout, redirect_stderr

import pytest

from inp_tool.repl import ShellREPL, REPL_COMMANDS

COMPARE_DIR = Path(__file__).parent / "fixtures" / "compare"
SST_FILE = COMPARE_DIR / "可压缩理想气体+2方程SST mcfd.inp"
TWOT_FILE = COMPARE_DIR / "双温模型+层流mcfd.inp"
LAMINAR_FILE = COMPARE_DIR / "可压缩理想气体+层流mcfd.inp"


def _capture(repl, cmd):
    """跑命令,返回 (stdout, stderr)"""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        repl.onecmd(cmd)
    return out.getvalue(), err.getvalue()


# ============================================================
# REPL_COMMANDS / 分组注册
# ============================================================
def test_repl_commands_registered():
    """3 个新命令进 REPL_COMMANDS"""
    assert 'detect' in REPL_COMMANDS
    assert 'turb' in REPL_COMMANDS
    assert '2t' in REPL_COMMANDS


# ============================================================
# do_detect
# ============================================================
class TestDoDetect:
    def test_detect_no_file_loaded(self):
        """无 file → 报错"""
        repl = ShellREPL()
        out, err = _capture(repl, 'detect')
        assert 'no file is current' in err.lower() or 'detect:' in err

    def test_detect_sst_file(self):
        if not SST_FILE.exists():
            pytest.skip("compare 样本不存在")
        repl = ShellREPL()
        _capture(repl, f'load {SST_FILE}')
        out, _ = _capture(repl, 'detect')
        assert '方程系统检测' in out
        assert 'k-omega-sst' in out
        assert 'perfect-gas' in out
        assert 'v6=0' in out

    def test_detect_two_temperature_file(self):
        if not TWOT_FILE.exists():
            pytest.skip("compare 样本不存在")
        repl = ShellREPL()
        _capture(repl, f'load {TWOT_FILE}')
        out, _ = _capture(repl, 'detect')
        assert '2T' in out
        assert 'multi-temp' in out
        assert 'v6=11' in out


# ============================================================
# do_turb
# ============================================================
class TestDoTurb:
    def test_turb_no_file(self):
        repl = ShellREPL()
        _, err = _capture(repl, 'turb I=0.01 L=0.01')
        assert 'no file is current' in err.lower() or 'turb:' in err

    def test_turb_missing_args(self):
        if not SST_FILE.exists():
            pytest.skip("compare 样本不存在")
        repl = ShellREPL()
        _capture(repl, f'load {SST_FILE}')
        _, err = _capture(repl, 'turb')
        assert '需要参数' in err or 'I=' in err

    def test_turb_missing_I(self):
        if not SST_FILE.exists():
            pytest.skip("compare 样本不存在")
        repl = ShellREPL()
        _capture(repl, f'load {SST_FILE}')
        _, err = _capture(repl, 'turb L=0.01')
        assert '必填' in err or 'I' in err

    def test_turb_laminar_rejects(self):
        """层流不能用 turb preset"""
        if not LAMINAR_FILE.exists():
            pytest.skip("compare 样本不存在")
        repl = ShellREPL()
        _capture(repl, f'load {LAMINAR_FILE}')
        _, err = _capture(repl, 'turb I=0.01 L=0.01 U=100')
        assert '层流' in err or 'laminar' in err

    def test_turb_sst_applies(self):
        """SST 文件 turb 应用,写 guiopts.turbi_*"""
        if not SST_FILE.exists():
            pytest.skip("compare 样本不存在")
        repl = ShellREPL()
        _capture(repl, f'load {SST_FILE}')
        out, _ = _capture(repl, 'turb I=0.01 L=0.01 U=204')
        assert 'k-omega-sst' in out
        assert 'guiopts.turbi_lev' in out
        assert 'guiopts.turbi_tlen' in out
        # k = 1.5 * (204 * 0.01)^2 ≈ 6.2424
        assert '6.24' in out or '6.2424' in out


# ============================================================
# do_2t
# ============================================================
class TestDo2T:
    def test_2t_no_file(self):
        repl = ShellREPL()
        _, err = _capture(repl, '2t T=300 Tvib=200')
        assert 'no file is current' in err.lower() or '2t:' in err

    def test_2t_missing_args(self):
        if not TWOT_FILE.exists():
            pytest.skip("compare 样本不存在")
        repl = ShellREPL()
        _capture(repl, f'load {TWOT_FILE}')
        _, err = _capture(repl, '2t T=300')
        assert '必填' in err or 'Tvib' in err

    def test_2t_applies(self):
        if not TWOT_FILE.exists():
            pytest.skip("compare 样本不存在")
        repl = ShellREPL()
        _capture(repl, f'load {TWOT_FILE}')
        out, _ = _capture(repl, '2t T=300 Tvib=200')
        assert 'T_trans=300' in out
        assert 'T_vib=200' in out
        assert 'physics.tnoneq_numeqns' in out
        assert 'physics.reftem' in out
        assert 'physics.vibtem' in out

    def test_2t_negative_temperature_rejects(self):
        if not TWOT_FILE.exists():
            pytest.skip("compare 样本不存在")
        repl = ShellREPL()
        _capture(repl, f'load {TWOT_FILE}')
        _, err = _capture(repl, '2t T=-100 Tvib=200')
        assert '2t:' in err
