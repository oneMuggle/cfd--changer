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


def _run_cli(*args):
    """通过 python -m inp_tool.cli 调用,返回 (returncode, stdout, stderr)"""
    proc = subprocess.run(
        [sys.executable, "-m", "inp_tool.cli", *args],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestSweepCLI:
    def test_sweep_help_shows_subcommand(self):
        rc, out, err = _run_cli("--help")
        assert rc == 0
        assert "sweep" in out

    def test_sweep_runs_with_config_file(self, sweep_config, tmp_path):
        rc, out, err = _run_cli("sweep", str(sweep_config))
        assert rc == 0
        out_dir = tmp_path / "cases"
        assert out_dir.is_dir()
        inps = list(out_dir.glob("*.inp"))
        assert len(inps) == 4  # 2 alpha * 2 mach

    def test_sweep_dry_run_does_not_write(self, sweep_config, tmp_path):
        rc, out, err = _run_cli("sweep", str(sweep_config), "--dry-run")
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
        rc, out, err = _run_cli("sweep", str(cfg))
        assert rc != 0
        assert "not found" in err.lower() or "no such" in err.lower()

    def test_sweep_manifest_path_creates_file(self, sweep_config, tmp_path):
        manifest = tmp_path / "cases" / "manifest.json"
        rc, out, err = _run_cli(
            "sweep", str(sweep_config),
            "--manifest", str(manifest),
        )
        assert rc == 0
        assert manifest.is_file()
        with open(manifest) as f:
            data = json.load(f)
        assert data["total"] == 4

    def test_sweep_invalid_json_returns_nonzero(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        rc, out, err = _run_cli("sweep", str(bad))
        assert rc != 0

    def test_sweep_bare_template_requires_sweeps(self, template_inp, tmp_path):
        # 只给 template 不给任何 sweep 也不给 JSON
        rc, out, err = _run_cli(
            "sweep", str(template_inp),
            "--out", str(tmp_path / "out"),
        )
        # 缺少 sweeps 应该报错
        assert rc != 0
