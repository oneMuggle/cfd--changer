"""
PR #2 阶段 6:wizard diff 测试

3 步走通:
  1. 基准
  2. 对比
  3. 输出格式

最后 execute 调 diff 函数。
"""
from __future__ import annotations
import os
import pytest

from inp_tool.wizard import WizardDiff
from inp_tool import i18n


@pytest.fixture(autouse=True)
def _force_zh():
    i18n.set_lang("zh")
    yield
    i18n.set_lang("zh")


@pytest.fixture
def two_inps(tmp_path):
    a = tmp_path / "a.inp"
    a.write_text(
        "guiopts begin\n"
        "aero_alpha 0.0\n"
        "aero_beta 0.0\n"
        "aero_ma 0.6\n"
        "guiopts end\n"
    )
    b = tmp_path / "b.inp"
    b.write_text(
        "guiopts begin\n"
        "aero_alpha 5.0\n"
        "aero_beta 0.0\n"
        "aero_ma 0.8\n"
        "guiopts end\n"
    )
    return a, b


class TestWizardDiff:
    def test_full_run(self, monkeypatch, two_inps, capsys):
        a, b = two_inps
        responses = iter([
            str(a),
            str(b),
            "1",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardDiff()
        w.run()
        assert w.data["baseline"] == str(a)
        assert w.data["other"] == str(b)
        out = capsys.readouterr().out
        assert "差异" in out or "change" in out.lower()

    def test_cancel_at_baseline(self, monkeypatch):
        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        w = WizardDiff()
        w.run()
        assert w.data == {}
