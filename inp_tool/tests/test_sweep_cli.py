"""
mcfd.inp sweep CLI — Phase 4 RED

测试目标:
- `inp-tool sweep` 子命令
- 接受 JSON 配置文件
- --dry-run 标志
- --alpha / --beta / --mach / --out 快捷参数
- exit code 语义
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import pytest

TEMPLATE_TEXT = """\
guiopts begin
aero_alpha 0.0
aero_beta 0.0
aero_ma 0.0
aero_u 0.0
aero_v 0.0
aero_w 0.0
guiopts end
physics begin
refvel 0.0
reftem 288.15
refpre 101325.0
physics end
"""


@pytest.fixture
def template_inp(tmp_path):
    p = tmp_path / "template.inp"
    p.write_text(TEMPLATE_TEXT)
    return p


@pytest.fixture
def sweep_config(tmp_path, template_inp):
    cfg = tmp_path / "sweep.json"
    cfg.write_text(json.dumps({
        "template": str(template_inp),
        "output_dir": str(tmp_path / "cases"),
        "sweeps": {
            "alpha": [0.0, 4.0],
            "mach": [0.6, 0.8],
            "T_inf": [288.15],
            "p_inf": [101325.0],
        },
    }))
    return cfg


def _run_cli(*args, cwd=None):
    """通过 python -m inp_tool.cli 调用,返回 (returncode, stdout, stderr)

    cwd: 默认 None(用 pytest 当前 cwd)。建议传 tmp_path 避免在仓库根
    跑 subprocess 时 Python 把外层 `./inp_tool/` 当 namespace package。
    """
    proc = subprocess.run(
        [sys.executable, "-m", "inp_tool.cli", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else None,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestSweepCLI:
    def test_sweep_help_shows_subcommand(self, tmp_path):
        rc, out, err = _run_cli("--help", cwd=tmp_path)
        assert rc == 0
        assert "sweep" in out

    def test_sweep_runs_with_config_file(self, sweep_config, tmp_path):
        rc, out, err = _run_cli("sweep", str(sweep_config), cwd=tmp_path)
        assert rc == 0
        out_dir = tmp_path / "cases"
        assert out_dir.is_dir()
        inps = list(out_dir.glob("*.inp"))
        assert len(inps) == 4  # 2 alpha * 2 mach

    def test_sweep_dry_run_does_not_write(self, sweep_config, tmp_path):
        rc, out, err = _run_cli("sweep", str(sweep_config), "--dry-run", cwd=tmp_path)
        assert rc == 0
        out_dir = tmp_path / "cases"
        # dry-run 不应写盘
        inps = list(out_dir.glob("*.inp")) if out_dir.exists() else []
        assert inps == []
        # 应打印"dry run"或类似字样
        assert "dry" in (out + err).lower()

    def test_sweep_quick_args_override(self, template_inp, tmp_path):
        # 用 --alpha / --beta / --mach 快捷方式(免去写 JSON)
        out_dir = str(tmp_path / "quick")
        rc, out, err = _run_cli(
            "sweep", str(template_inp),
            "--alpha", "0,4,8",
            "--mach", "0.6,0.8",
            "--t-inf", "288.15",
            "--p-inf", "101325.0",
            "--out", out_dir,
            cwd=tmp_path,
        )
        assert rc == 0, f"stderr: {err}"
        inps = list((tmp_path / "quick").glob("*.inp"))
        assert len(inps) == 6  # 3 alpha * 2 mach

    def test_sweep_missing_template_returns_nonzero(self, tmp_path):
        nonexistent = tmp_path / "missing.inp"
        cfg = tmp_path / "sweep.json"
        cfg.write_text(json.dumps({
            "template": str(nonexistent),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0]},
        }))
        rc, out, err = _run_cli("sweep", str(cfg), cwd=tmp_path)
        assert rc != 0
        assert "not found" in err.lower() or "no such" in err.lower()

    def test_sweep_manifest_path_creates_file(self, sweep_config, tmp_path):
        manifest = tmp_path / "cases" / "manifest.json"
        rc, out, err = _run_cli(
            "sweep", str(sweep_config),
            "--manifest", str(manifest),
            cwd=tmp_path,
        )
        assert rc == 0
        assert manifest.is_file()
        with open(manifest) as f:
            data = json.load(f)
        assert data["total"] == 4

    def test_sweep_invalid_json_returns_nonzero(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        rc, out, err = _run_cli("sweep", str(bad), cwd=tmp_path)
        assert rc != 0

    def test_sweep_bare_template_requires_sweeps(self, template_inp, tmp_path):
        # 只给 template 不给任何 sweep 也不给 JSON
        rc, out, err = _run_cli(
            "sweep", str(template_inp),
            "--out", str(tmp_path / "out"),
            cwd=tmp_path,
        )
        # 缺少 sweeps 应该报错
        assert rc != 0

    def test_sweep_cli_alpha_only_preserves_template_ma(self, tmp_path):
        """Bug fix regression: --alpha alone should preserve template's aero_ma/u/v/w/temp."""
        import re as _re
        template = tmp_path / "t.inp"
        template.write_text(
            "system begin\n"
            "system end\n"
            "guiopts begin\n"
            "aero_pres 1.013250e+005\n"
            "aero_temp 2.880000e+002\n"
            "aero_u 3.000000e+001\n"
            "aero_v 0.0\n"
            "aero_w 0.0\n"
            "aero_ma 8.000000e-001\n"
            "aero_alpha 0.000000e+000\n"
            "aerobeta 0.000000e+000\n"
            "aero_re 1.000000e+006\n"
            "guiopts end\n"
            "physics begin\n"
            "refvel -1.0\n"
            "reftem 2.880000e+002\n"
            "refpre 1.013250e+005\n"
            "physics end\n"
        )
        out_dir = tmp_path / "out"
        rc, out, err = _run_cli(
            "sweep", str(template),
            "--alpha", "0,10",
            "--out", str(out_dir),
            cwd=tmp_path,
        )
        assert rc == 0, f"stderr={err}"
        # 检查生成的 case_10.0.inp: aero_ma 必须仍是 0.8
        case_10 = out_dir / "case_10.0.inp"
        assert case_10.exists(), f"未生成 case_10.0.inp,目录={list(out_dir.glob('*'))}"
        text = case_10.read_text()

        # 1. aero_ma 应保留模板的 0.8
        ma_line = next(l for l in text.splitlines() if l.startswith("aero_ma "))
        assert "8.000000e-001" in ma_line or "0.8" in ma_line, \
            f"aero_ma 未保留(模板=0.8),实际行={ma_line!r}"

        # 2. aero_temp 应保留模板的 288.0
        temp_line = next(l for l in text.splitlines() if l.startswith("aero_temp "))
        assert "2.880000e+002" in temp_line or "288" in temp_line, \
            f"aero_temp 未保留(模板=288),实际行={temp_line!r}"

        # 3. aero_u 应被重算为 Ma=0.8, alpha=10° 的值
        # a = sqrt(1.4*287.05*288) ≈ 340.29
        # U = 0.8*340.29*cos(10°) ≈ 268.0
        u_line = next(l for l in text.splitlines() if l.startswith("aero_u "))
        m = _re.search(r"(-?\d+\.?\d*[eE]?[+-]?\d*)", u_line[len("aero_u "):])
        u_val = float(m.group(1))
        assert 260 < u_val < 280, f"aero_u 应 ≈ 268 (Ma=0.8, alpha=10),实得 {u_val}"

        # 4. case_0.0.inp 也应保留 Ma=0.8
        case_0 = out_dir / "case_0.0.inp"
        assert case_0.exists()
        text0 = case_0.read_text()
        ma0_line = next(l for l in text0.splitlines() if l.startswith("aero_ma "))
        assert "8.000000e-001" in ma0_line or "0.8" in ma0_line, \
            f"case_0.0.inp 的 aero_ma 未保留,实际行={ma0_line!r}"
