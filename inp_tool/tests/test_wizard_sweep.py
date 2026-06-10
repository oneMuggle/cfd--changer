"""
v0.8.2 wizard sweep 测试(6 步,source_dir 必填 + 整目录模式为默认)

新 6 步顺序:
  1. source_dir  (必填,问复制策略)
  2. output       (输出目录 + manifest 选项)
  3. mode         (笛卡尔 / cases / groups / CSV)
  4. params       (填参,根据 mode)
  5. naming       (命名模板)
  6. preview      (预览 + 覆盖确认 + 执行)
"""
from __future__ import annotations
import os
import pytest

from inp_tool.wizard import WizardSweep
from inp_tool import i18n


@pytest.fixture(autouse=True)
def _force_zh():
    i18n.set_lang("zh")
    yield
    i18n.set_lang("zh")


TEMPLATE_TEXT = """\
guiopts begin
aero_alpha 0.0
aero_beta 0.0
aero_ma 0.0
aero_u 0.0
aero_v 0.0
aero_w 0.0
aero_temp 288.15
aero_pres 101325.0
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
def base_case_dir(tmp_path):
    """最小化"完整算例目录":mcfd.inp + grid.bin + config.txt。"""
    base = tmp_path / "base"
    base.mkdir()
    (base / "mcfd.inp").write_text(TEMPLATE_TEXT)
    (base / "grid.bin").write_bytes(b"GRID")
    (base / "config.txt").write_text("cfg")
    return base


class TestSweepModeCartesian:
    def test_cartesian_mode(self, monkeypatch, template_inp, base_case_dir, tmp_path):
        out_dir = str(tmp_path / "cases")
        responses = iter([
            str(base_case_dir),
            "1",
            out_dir,
            "n",
            "1",
            "{alpha: [0, 5], mach: [0.6, 0.8]}",
            "case_{alpha}_ma{mach}",
            "y",
            "n",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardSweep()
        w.run()
        from pathlib import Path
        out_path = Path(out_dir)
        case_dirs = sorted(d for d in out_path.iterdir() if d.is_dir())
        assert len(case_dirs) == 4
        for case_dir in case_dirs:
            assert (case_dir / "mcfd.inp").is_file()
            assert (case_dir / "grid.bin").is_file()
            assert (case_dir / "config.txt").is_file()
        assert (base_case_dir / "mcfd.inp").read_text() == TEMPLATE_TEXT


class TestSweepModeCases:
    def test_cases_mode_user_scenario(self, monkeypatch, template_inp, base_case_dir, tmp_path):
        out_dir = str(tmp_path / "cases")
        cases_yaml = """\
- {alpha: 10, beta: 5,  mach: 0.6, T: 288.15, p: 101325}
- {alpha: 10, beta: 8,  mach: 0.6, T: 288.15, p: 101325}
- {alpha: 20, beta: 10, mach: 0.6, T: 288.15, p: 101325}
- {alpha: 20, beta: 15, mach: 0.6, T: 288.15, p: 101325}
"""
        responses = iter([
            str(base_case_dir),
            "1",
            out_dir,
            "n",
            "2",
            cases_yaml,
            "case_a{alpha:02.0f}_b{beta:02.0f}",
            "y",
            "n",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardSweep()
        w.run()
        from pathlib import Path
        out_path = Path(out_dir)
        case_dirs = sorted(d for d in out_path.iterdir() if d.is_dir())
        assert len(case_dirs) == 4
        names = [d.name for d in case_dirs]
        assert "case_a10_b05" in names
        assert "case_a20_b15" in names
        assert (base_case_dir / "mcfd.inp").read_text() == TEMPLATE_TEXT


class TestSweepModeCSV:
    def test_csv_mode(self, monkeypatch, template_inp, base_case_dir, tmp_path):
        csv = tmp_path / "cases.csv"
        csv.write_text("alpha,beta\n0,0\n5,0\n")
        out_dir = str(tmp_path / "cases")
        responses = iter([
            str(base_case_dir),
            "1",
            out_dir,
            "n",
            "4",
            str(csv),
            "case_a{alpha}",
            "y",
            "n",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardSweep()
        w.run()
        from pathlib import Path
        out_path = Path(out_dir)
        case_dirs = sorted(d for d in out_path.iterdir() if d.is_dir())
        assert len(case_dirs) == 2
        for case_dir in case_dirs:
            assert (case_dir / "mcfd.inp").is_file()
            assert (case_dir / "grid.bin").is_file()

    def test_wizard_with_source_dir_per_dir_mode(self, monkeypatch, template_inp, base_case_dir, tmp_path):
        out_dir = str(tmp_path / "out")
        responses = iter([
            str(base_case_dir),
            "1",
            out_dir,
            "n",
            "1",
            "{alpha: [0, 4]}",
            "case_{alpha}",
            "y",
            "n",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardSweep()
        w.run()
        from pathlib import Path
        out_path = Path(out_dir)
        case_dirs = sorted(d for d in out_path.iterdir() if d.is_dir())
        assert len(case_dirs) == 2
        for case_dir in case_dirs:
            assert (case_dir / "mcfd.inp").is_file()
            assert (case_dir / "grid.bin").is_file()
            assert (case_dir / "config.txt").is_file()
        assert (base_case_dir / "mcfd.inp").read_text() == TEMPLATE_TEXT


class TestSweepCancel:
    def test_cancel_at_source_dir(self, monkeypatch):
        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        w = WizardSweep()
        w.run()
        assert w.data == {}


class TestSweepSourceDirRequired:
    def test_empty_source_dir_reprompts(self, monkeypatch, template_inp, base_case_dir, tmp_path):
        out_dir = str(tmp_path / "cases")
        responses = iter([
            "",
            str(base_case_dir),
            "1",
            out_dir,
            "n",
            "1",
            "{alpha: [0]}",
            "case_{alpha}",
            "y",
            "n",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardSweep()
        w.run()
        from pathlib import Path
        case_dirs = list(d for d in Path(out_dir).iterdir() if d.is_dir())
        assert len(case_dirs) == 1

    def test_nonexistent_source_dir_reprompts(self, monkeypatch, template_inp, base_case_dir, tmp_path):
        out_dir = str(tmp_path / "cases")
        responses = iter([
            "/no/such/path/xyz",
            str(base_case_dir),
            "1",
            out_dir,
            "n",
            "1",
            "{alpha: [0]}",
            "case_{alpha}",
            "y",
            "n",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardSweep()
        w.run()
        from pathlib import Path
        case_dirs = list(d for d in Path(out_dir).iterdir() if d.is_dir())
        assert len(case_dirs) == 1
