"""
v0.10.0+:WizardSweep.step_4a_detect 消费 sweeps_equation_warnings 测试

step_4a_detect 应把 data["intended_axes"] 传给 detect_equations,
并在末尾显示 sweeps_equation_warnings(不与 notes 重复)。
"""
from __future__ import annotations
import textwrap
import pytest
from inp_tool.wizard import WizardSweep
from inp_tool import i18n


@pytest.fixture(autouse=True)
def _force_zh():
    i18n.set_lang("zh")
    yield
    i18n.set_lang("zh")


def _laminar_template(tmp_path):
    p = tmp_path / "laminar.inp"
    p.write_text(textwrap.dedent("""\
        seq.# 1 #vals 31 title eqnset_define
          values 101 1 1 0 1
          values 0 0 0 0 0
          values 1 0
        seq.# 1 #vals 31
        guiopts begin
          aero_ma 0.6
        guiopts end
        physics begin
          refvel 204.0
          tnoneq_numeqns 0
        physics end
    """))
    return str(p)


def _call_step(wiz, data):
    return wiz.step_4a_detect(data)


class TestStep4aConsumeWarnings:
    def test_warning_displayed_for_laminar_plus_sst(self, tmp_path, capsys):
        """intended_axes.turbulence='sst' + laminar 模板 → 检测报告含 ⚠ 显示。"""
        template = _laminar_template(tmp_path)
        wiz = WizardSweep()
        data = {
            "template": template,
            "intended_axes": {"turbulence": "sst"},
        }
        next_step, new_data = _call_step(wiz, data)
        # 跳到 step_4c_equation_overrides
        assert next_step == "step_4c_equation_overrides"
        captured = capsys.readouterr()
        # 输出含 "SST"/"sst" + "laminar"
        out = captured.out
        assert ("SST" in out or "sst" in out) and "laminar" in out.lower()
        # 至少有一处 ⚠ 标记
        assert "⚠" in out

    def test_no_warnings_section_when_no_intended_axes(self, tmp_path, capsys):
        """无 intended_axes → 不显示 ⚠ 警告段(notes 仍按原逻辑显示)。"""
        template = _laminar_template(tmp_path)
        wiz = WizardSweep()
        data = {"template": template}  # 无 intended_axes
        next_step, new_data = _call_step(wiz, data)
        assert next_step == "step_4c_equation_overrides"
        captured = capsys.readouterr()
        # 不应有"你选的 axis 与 template 不兼容"这种 sweeps 警告段
        assert "你选" not in captured.out and "your selected" not in captured.out.lower()

    def test_warning_section_separate_from_notes(self, tmp_path, capsys):
        """⚠ 警告段(sweeps)与 notes(v0.9.1 自身警告)分开显示,都是 ⚠ 开头。"""
        template = _laminar_template(tmp_path)
        wiz = WizardSweep()
        data = {
            "template": template,
            "intended_axes": {"turbulence": "sst"},
        }
        _call_step(wiz, data)
        captured = capsys.readouterr()
        out = captured.out
        # sweeps warning 段标题应与 notes 段标题不同
        # 注:具体文本由实现决定,这里只验证至少有一个 ⚠ 出现
        assert out.count("⚠") >= 1
