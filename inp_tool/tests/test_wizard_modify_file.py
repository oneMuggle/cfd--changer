"""
PR #2 阶段 4:wizard modify-file 测试

5 步走通:
  1. 选文件
  2. 选字段
  3. 输值
  4. 预览
  5. 输出

用 monkeypatch 模拟 input。
"""
from __future__ import annotations
import io
import os
from contextlib import redirect_stdout
from unittest.mock import patch
import pytest

from inp_tool import wizard
from inp_tool.wizard import (
    WizardModifyFile, WizardBase, WizardCancel,
    input_text, confirm, menu,
)
from inp_tool import i18n


@pytest.fixture(autouse=True)
def _force_zh():
    i18n.set_lang("zh")
    yield
    i18n.set_lang("zh")


# ======================================================================
# 通用 UI 组件
# ======================================================================
class TestInputText:
    def test_input_text_with_default(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = input_text("Q?", default="hello")
        assert result == "hello"

    def test_input_text_with_value(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "user_input")
        result = input_text("Q?")
        assert result == "user_input"

    def test_input_text_validator_retry(self, monkeypatch, capsys):
        responses = iter(["bad", "good"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        result = input_text("Q?", validator=lambda x: None if x == "good" else "必须是 good")
        assert result == "good"

    def test_input_text_eof_raises_cancel(self, monkeypatch):
        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        with pytest.raises(WizardCancel):
            input_text("Q?")


class TestConfirm:
    def test_confirm_yes(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert confirm("Q?") is True

    def test_confirm_no(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert confirm("Q?") is False

    def test_confirm_default_yes(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert confirm("Q?", default=True) is True

    def test_confirm_default_no(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert confirm("Q?", default=False) is False

    def test_confirm_chinese_yes(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "是")
        assert confirm("Q?") is True


class TestMenu:
    def test_menu_picks_first(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda _: "1")
        choices = [
            ("1", "选项一", "Option 1"),
            ("2", "选项二", "Option 2"),
            ("Q", "退出", "(quit)"),
        ]
        result = menu("Q?", choices, default="1")
        assert result == "1"

    def test_menu_picks_2(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "2")
        choices = [
            ("1", "选项一", "Option 1"),
            ("2", "选项二", "Option 2"),
            ("Q", "退出", "(quit)"),
        ]
        result = menu("Q?", choices)
        assert result == "2"

    def test_menu_quit_raises_cancel(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "q")
        choices = [
            ("1", "选项一", "Option 1"),
            ("Q", "退出", "(quit)"),
        ]
        with pytest.raises(WizardCancel):
            menu("Q?", choices)


# ======================================================================
# WizardBase 框架
# ======================================================================
class TestWizardBase:
    def test_empty_steps_raises(self):
        class Empty(WizardBase):
            steps = []
        with pytest.raises(NotImplementedError):
            Empty().run()

    def test_missing_step_method_raises(self):
        class Bad(WizardBase):
            steps = ["step_1_doesnt_exist"]
        with pytest.raises(NotImplementedError):
            Bad().run()


# ======================================================================
# WizardModifyFile
# ======================================================================
class TestWizardModifyFile:
    def test_full_run_happy_path(self, monkeypatch, tmp_path, capsys):
        """完整走通 5 步"""
        inp = tmp_path / "test.inp"
        inp.write_text("placeholder\n")
        responses = iter([
            str(inp),    # step_1 file path
            "1 2",       # step_2 fields
            "0.8",       # step_3 Ma
            "5",         # step_3 alpha
            "y",         # step_4 confirm
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardModifyFile()
        w.run()
        assert w.data["file"] == str(inp)
        assert w.data["fields"] == ["Ma", "alpha"]
        assert w.data["values"] == {"Ma": 0.8, "alpha": 5.0}
        assert "output" in w.data

    def test_cancel_at_step1(self, monkeypatch, tmp_path):
        def raise_eof(_):
            raise EOFError
        monkeypatch.setattr("builtins.input", raise_eof)
        w = WizardModifyFile()
        w.run()
        assert w.data == {}

    def test_skip_all_fields(self, monkeypatch, tmp_path):
        inp = tmp_path / "t.inp"
        inp.write_text("x")
        responses = iter([
            str(inp),
            "all",
            "0.8", "5", "0", "288.15", "101325",
            "y",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardModifyFile()
        w.run()
        assert w.data["fields"] == ["Ma", "alpha", "beta", "T", "p"]
        assert len(w.data["values"]) == 5

    def test_invalid_value_skipped(self, monkeypatch, tmp_path):
        """step_3 输入非数字 → 跳过该字段"""
        inp = tmp_path / "t.inp"
        inp.write_text("x")
        # 选 2 个 field 都给非数字,values 为空 → 取消
        responses = iter([str(inp), "1 2", "abc", "xyz", "y"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        w = WizardModifyFile()
        w.run()
        assert "values" not in w.data or w.data.get("values") == {}
