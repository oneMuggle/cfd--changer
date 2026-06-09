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
            out_dir,
            "n",
            "y",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardSweep()
        w.run()
        inps = sorted(os.listdir(out_dir))
        assert len(inps) == 2


class TestSweepCancel:
    def test_cancel_at_template(self, monkeypatch):
        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        w = WizardSweep()
        w.run()
        assert w.data == {}
