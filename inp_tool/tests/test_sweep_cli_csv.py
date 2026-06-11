"""
PR #1 阶段 6:CLI 文件后缀自动路由(CSV 路径)

测试目标:
- `inp-tool sweep cases.csv --template template.inp` 走 from_csv
- `inp-tool sweep cases.json` 继续走 from_json(向后兼容)
- `inp-tool sweep cases.yaml` 继续走 from_yaml(向后兼容)
- `inp-tool sweep cases.csv --out X` 输出目录可覆盖
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
def cases_csv(tmp_path):
    p = tmp_path / "cases.csv"
    p.write_text(
        "alpha,beta,mach\n"
        "10,5,0.6\n"
        "10,8,0.6\n"
        "20,10,0.6\n"
        "20,15,0.6\n",
        encoding="utf-8",
    )
    return p


def _run_cli(*args, cwd=None):
    """通过 python -m inp_tool.cli 调用,返回 (returncode, stdout, stderr)

    cwd: 默认 None。建议传 tmp_path 避免在仓库根跑 subprocess 时
    Python 把外层 `./inp_tool/` 当 namespace package。
    """
    proc = subprocess.run(
        [sys.executable, "-m", "inp_tool.cli", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else None,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestSweepCLI_CsvRouting:
    def test_sweep_csv_with_template_flag(self, cases_csv, template_inp, tmp_path):
        out_dir = str(tmp_path / "out")
        rc, out, err = _run_cli(
            "sweep", str(cases_csv),
            "--template", str(template_inp),
            "--out", out_dir,
            "--naming", "case_a{alpha:02.0f}_b{beta:02.0f}.inp",
            cwd=tmp_path,
        )
        assert rc == 0, f"stderr={err}"
        # 4 个 case 应生成
        out_path = tmp_path / "out"
        inps = sorted(out_path.glob("*.inp"))
        assert len(inps) == 4
        names = [p.name for p in inps]
        assert names == [
            "case_a10_b05.inp",
            "case_a10_b08.inp",
            "case_a20_b10.inp",
            "case_a20_b15.inp",
        ]

    def test_sweep_csv_missing_template_flag_errors(self, cases_csv, tmp_path):
        """CSV 模式必须给 --template,否则报错"""
        rc, out, err = _run_cli(
            "sweep", str(cases_csv),
            "--out", str(tmp_path / "out"),
            cwd=tmp_path,
        )
        assert rc != 0
        # 错误应提到 template
        assert "template" in err.lower()

    def test_sweep_json_still_works(self, template_inp, tmp_path):
        """向后兼容:JSON 仍走老路径"""
        cfg = tmp_path / "sweep.json"
        cfg.write_text(json.dumps({
            "template": str(template_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0, 4]},
        }))
        rc, out, err = _run_cli("sweep", str(cfg), cwd=tmp_path)
        assert rc == 0
        inps = list((tmp_path / "out").glob("*.inp"))
        assert len(inps) == 2  # 老用法:2 cases

    def test_sweep_yaml_still_works(self, template_inp, tmp_path):
        """向后兼容:YAML 仍走老路径"""
        import yaml
        cfg = tmp_path / "sweep.yaml"
        cfg.write_text(yaml.safe_dump({
            "template": str(template_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0, 4]},
        }))
        rc, out, err = _run_cli("sweep", str(cfg), cwd=tmp_path)
        assert rc == 0
        inps = list((tmp_path / "out").glob("*.inp"))
        assert len(inps) == 2

    def test_sweep_csv_uses_naming_in_csv_or_default(self, cases_csv, template_inp, tmp_path):
        """CSV 模式:naming 由 --naming 提供(CSV 本身无 naming)"""
        out_dir = str(tmp_path / "out")
        rc, _, err = _run_cli(
            "sweep", str(cases_csv),
            "--template", str(template_inp),
            "--out", out_dir,
            cwd=tmp_path,
        )
        assert rc == 0, f"stderr={err}"
        # 默认 naming:case_{alpha}
        inps = sorted((tmp_path / "out").glob("*.inp"))
        names = [p.name for p in inps]
        assert "case_10.0.inp" in names
        assert "case_20.0.inp" in names
