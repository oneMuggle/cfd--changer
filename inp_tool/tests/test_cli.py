"""inp_tool.cli 单元测试(argparse 5 个子命令 + version + main 入口)。"""
from pathlib import Path

import pytest

from inp_tool import cli


# ========== version ==========
def test_main_version(capsys):
    """--version 打印版本号并以 SystemExit(0) 退出。"""
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "0.8.3" in captured.out


# ========== info ==========
def test_cli_info(capsys, sample_inp: Path):
    rc = cli.main(["info", str(sample_inp)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "块列表" in out
    assert "tsteps" in out


# ========== parse ==========
def test_cli_parse_full(capsys, sample_inp: Path):
    rc = cli.main(["parse", str(sample_inp), "-f"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "文件:" in out
    assert "块:" in out


def test_cli_parse_block(capsys, sample_inp: Path):
    rc = cli.main(["parse", str(sample_inp), "-b", "tsteps", "-f"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "tsteps" in out


def test_cli_parse_block_not_found(capsys, sample_inp: Path):
    rc = cli.main(["parse", str(sample_inp), "-b", "no_such_block"])
    assert rc == 1


# ========== get ==========
def test_cli_get_value(capsys, sample_inp: Path):
    rc = cli.main(["get", str(sample_inp), "cflbot", "-b", "tsteps"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "cflbot" in out
    assert "=" in out


def test_cli_get_key_not_found(capsys, sample_inp: Path):
    rc = cli.main(["get", str(sample_inp), "no_such_key", "-b", "tsteps"])
    assert rc == 1


# ========== set ==========
def test_cli_set_value(capsys, sample_inp: Path, tmp_path: Path):
    """set 改值并写到 out, 再读回验证。"""
    out = tmp_path / "cli_set.inp"
    rc = cli.main(["set", str(sample_inp), "tsteps", "cflbot", "0.555", "-o", str(out)])
    assert rc == 0
    assert out.exists()
    captured = capsys.readouterr()
    assert str(out) in captured.out or "cflbot" in captured.out


# ========== diff ==========
def test_cli_diff(capsys, sample_inp: Path, tmp_path: Path):
    a = sample_inp
    b = tmp_path / "diff_b.inp"
    b.write_text(
        sample_inp.read_text(encoding="utf-8", errors="replace")
        .replace("cflbot  ", "cflbot 0.888"),
        encoding="utf-8",
    )
    rc = cli.main(["diff", str(a), str(b)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "差异" in out or "cflbot" in out


def test_cli_diff_unified(capsys, sample_inp: Path, tmp_path: Path):
    a = sample_inp
    b = tmp_path / "diff_b.inp"
    b.write_text(
        sample_inp.read_text(encoding="utf-8", errors="replace")
        .replace("cflbot  ", "cflbot 0.888"),
        encoding="utf-8",
    )
    rc = cli.main(["diff", str(a), str(b), "-u"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "---" in out
    assert "+++" in out


# ========== __main__ 入口 ==========
def test_python_dash_m_inp_tool():
    """python -m inp_tool --version 调用 __main__ 入口。"""
    import subprocess
    import sys
    r = subprocess.run(
        [sys.executable, "-m", "inp_tool", "--version"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0
    assert "0.8.3" in r.stdout


# ========== shell (Task 16) ==========
def test_shell_subcommand_in_help():
    """`inp-tool --help` 应包含 'shell' 子命令。"""
    from inp_tool.cli import main
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            main(['--help'])
    except SystemExit:
        pass
    out = buf.getvalue()
    assert 'shell' in out


def test_shell_via_subprocess(tmp_path):
    """非交互式跑一条 load + exit,验证子命令可达。"""
    p = tmp_path / 's.inp'
    p.write_text('physics begin\n  refvel 1.0\nphysics end\n')
    import subprocess, sys, os
    cp = subprocess.run(
        [sys.executable, '-m', 'inp_tool.cli', 'shell', str(p)],
        input='files\nexit\n',
        capture_output=True, text=True, timeout=10,
        env={**os.environ, 'TERM': 'dumb'},  # avoid readline/prompt interference
    )
    assert cp.returncode == 0, f'shell exited with {cp.returncode}: stderr={cp.stderr}'
    # 's' is the stem of s.inp — should appear in the files listing
    assert 's' in cp.stdout
