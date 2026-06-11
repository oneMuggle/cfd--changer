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
    assert "0.9.0" in captured.out


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
def test_python_dash_m_inp_tool(tmp_path):
    """python -m inp_tool --version 调用 __main__ 入口。

    NOTE: cwd 设到 tmp_path,避免在仓库根跑 subprocess 时
    Python 把外层 `./inp_tool/` 当作 namespace package(没 __init__.py),
    优先于 site-packages 中真正的 inp_tool package — 触发
    `ImportError: cannot import name '__version__'`。
    """
    import subprocess
    import sys
    r = subprocess.run(
        [sys.executable, "-m", "inp_tool", "--version"],
        capture_output=True, text=True, timeout=30,
        cwd=str(tmp_path),
    )
    assert r.returncode == 0
    assert "0.9.0" in r.stdout


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
        cwd=str(tmp_path),  # 避免 cwd-induced namespace package 冲突
        env={**os.environ, 'TERM': 'dumb'},  # avoid readline/prompt interference
    )
    assert cp.returncode == 0, f'shell exited with {cp.returncode}: stderr={cp.stderr}'
    # 's' is the stem of s.inp — should appear in the files listing
    assert 's' in cp.stdout


# =============================================================================
# v0.8.2:CLI deprecation warning(不传 --source-dir 时)
# =============================================================================
def test_cli_sweep_no_source_dir_emits_deprecation(capsys, sample_inp, tmp_path):
    """v0.8.2:CLI 不传 --source-dir 时,stderr 应包含 [DEPRECATION] 提示。

    行为不变:仍然生成扁平 .inp(wizard 已强制 per_dir,CLI 仅引导)。
    """
    out_dir = tmp_path / "flat_out"
    rc = cli.main([
        "sweep", str(sample_inp),
        "--alpha", "0,4",
        "--out", str(out_dir),
    ])
    assert rc == 0
    err = capsys.readouterr().err
    assert "[DEPRECATION]" in err
    assert "--source-dir" in err
    inps = list(out_dir.glob("*.inp"))
    assert len(inps) == 2


def test_cli_sweep_with_source_dir_no_deprecation(capsys, sample_inp, tmp_path):
    """v0.8.2:CLI 传 --source-dir 时,stderr 不应有 [DEPRECATION]。"""
    base = tmp_path / "base"
    base.mkdir()
    (base / "mcfd.inp").write_text(sample_inp.read_text())
    (base / "grid.bin").write_bytes(b"G")
    rc = cli.main([
        "sweep", str(sample_inp),
        "--alpha", "0,4",
        "--source-dir", str(base),
        "--out", str(tmp_path / "per_dir_out"),
    ])
    assert rc == 0
    err = capsys.readouterr().err
    assert "[DEPRECATION]" not in err
    case_dirs = sorted(d for d in (tmp_path / "per_dir_out").iterdir() if d.is_dir())
    assert len(case_dirs) == 2
    for d in case_dirs:
        assert (d / "mcfd.inp").is_file()
        assert (d / "grid.bin").is_file()


# ============================================================
# v0.9.1: info --detect 子命令测试
# ============================================================
def test_info_detect_two_temperature(tmp_path):
    """info --detect 对双温文件输出 energy=2T / gas=multi-temp / gas_code=11"""
    import subprocess
    import sys
    target = "/home/fz/project/cfd--changer/reference/inp_example/compare/双温模型+层流mcfd.inp"
    import os
    if not os.path.exists(target):
        import pytest
        pytest.skip("compare 样本不存在")
    r = subprocess.run(
        [sys.executable, "-m", "inp_tool.cli", "info", target, "--detect"],
        capture_output=True, text=True, timeout=30,
        cwd=str(tmp_path),
    )
    assert r.returncode == 0, f"stderr={r.stderr}"
    out = r.stdout
    assert "方程系统检测" in out
    assert "能量模型" in out and "2T" in out
    assert "气体类型" in out and "multi-temp" in out
    assert "v6=11" in out


def test_info_without_detect_omits_report(tmp_path):
    """无 --detect 时不显示检测段(向后兼容)"""
    import subprocess
    import sys
    # 简单合成 inp
    p = tmp_path / "x.inp"
    p.write_text("physics begin\n  refvel 1.0\nphysics end\n")
    r = subprocess.run(
        [sys.executable, "-m", "inp_tool.cli", "info", str(p)],
        capture_output=True, text=True, timeout=30,
        cwd=str(tmp_path),
    )
    assert r.returncode == 0
    assert "方程系统检测" not in r.stdout
