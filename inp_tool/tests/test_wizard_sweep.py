"""
PR #2 阶段 5:wizard sweep 测试

7 步走通:
  1. 模板
  2. 模式(笛卡尔/cases/groups/CSV)
  3. 填参
  4. 命名
  5. 输出
  6. 预览
  7. 执行
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


class TestSweepModeCartesian:
    def test_cartesian_mode(self, monkeypatch, template_inp, tmp_path):
        out_dir = str(tmp_path / "cases")
        responses = iter([
            str(template_inp),
            "1",
            "{alpha: [0, 5], mach: [0.6, 0.8]}",
            "case_a{alpha}_ma{mach}.inp",
            "",              # v0.8.0 step_5 source_dir (空=flat)
            out_dir,
            "n",
            "y",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardSweep()
        w.run()
        inps = sorted(os.listdir(out_dir))
        assert len(inps) == 4
        assert "case_a0_ma0.6.inp" in inps
        assert "case_a5_ma0.8.inp" in inps


class TestSweepModeCases:
    def test_cases_mode_user_scenario(self, monkeypatch, template_inp, tmp_path):
        """用户原话 4-case:流场 1 攻角 10/20,各攻角下不同侧滑"""
        out_dir = str(tmp_path / "cases")
        cases_yaml = """\
- {alpha: 10, beta: 5,  mach: 0.6, T: 288.15, p: 101325}
- {alpha: 10, beta: 8,  mach: 0.6, T: 288.15, p: 101325}
- {alpha: 20, beta: 10, mach: 0.6, T: 288.15, p: 101325}
- {alpha: 20, beta: 15, mach: 0.6, T: 288.15, p: 101325}
"""
        responses = iter([
            str(template_inp),
            "2",
            cases_yaml,
            "case_a{alpha:02.0f}_b{beta:02.0f}.inp",
            "",              # v0.8.0 source_dir
            out_dir,
            "n",
            "y",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardSweep()
        w.run()
        inps = sorted(os.listdir(out_dir))
        assert len(inps) == 4
        assert "case_a10_b05.inp" in inps
        assert "case_a20_b15.inp" in inps


class TestSweepModeCSV:
    def test_csv_mode(self, monkeypatch, template_inp, tmp_path):
        csv = tmp_path / "cases.csv"
        csv.write_text("alpha,beta\n0,0\n5,0\n")
        out_dir = str(tmp_path / "cases")
        responses = iter([
            str(template_inp),
            "4",
            str(csv),
            "case_a{alpha}.inp",
            "",              # v0.8.0 source_dir
            out_dir,
            "n",
            "y",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardSweep()
        w.run()
        inps = sorted(os.listdir(out_dir))
        assert len(inps) == 2

    def test_wizard_with_source_dir_per_dir_mode(self, monkeypatch, template_inp, tmp_path):
        """v0.8.0:wizard 加 source_dir 后,生成 per_dir 整目录(不是孤立 mcfd.inp)"""
        from pathlib import Path
        # 基础算例目录
        base = tmp_path / "base"
        base.mkdir()
        (base / "mcfd.inp").write_text(TEMPLATE_TEXT)
        (base / "grid.bin").write_bytes(b"GRID")
        (base / "config.txt").write_text("cfg")
        out_dir = str(tmp_path / "out")
        responses = iter([
            str(template_inp),
            "1",                                  # 笛卡尔模式
            "{alpha: [0, 4]}",                    # 2 cases
            "case_{alpha}",                       # 命名
            str(base),                            # v0.8.0 source_dir
            "1",                                  # hardlink
            out_dir,                              # 输出目录
            "n",                                  # 不要 manifest
            "y",                                  # 预览确认
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardSweep()
        w.run()
        # 验证:per_dir 模式 → 2 个子目录,每个含 grid.bin
        out_path = Path(out_dir)
        case_dirs = [d for d in out_path.iterdir() if d.is_dir()]
        assert len(case_dirs) == 2
        for case_dir in case_dirs:
            assert (case_dir / "mcfd.inp").is_file()
            assert (case_dir / "grid.bin").is_file()
            assert (case_dir / "config.txt").is_file()
        # 关键:源 mcfd.inp 不能被损坏(回归 C1)
        assert (base / "mcfd.inp").read_text() == TEMPLATE_TEXT


class TestSweepCancel:
    def test_cancel_at_template(self, monkeypatch):
        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        w = WizardSweep()
        w.run()
        assert w.data == {}
