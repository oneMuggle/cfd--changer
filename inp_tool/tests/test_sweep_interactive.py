"""
mcfd.inp sweep 交互式 CLI — Phase B RED

测试目标:
- inp-tool sweep -i 走 prompt 序列
- 全部字段有 default
- 回车=接受 default
- 错输入有友好重试
- 最后 confirm 跑/不跑
"""
from __future__ import annotations
import pytest
from inp_tool.cli import (
    _prompt,
    _confirm,
    build_sweep_config_interactive,
)


class TestPrompt:
    def test_returns_default_on_empty(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert _prompt("q?", default="hello") == "hello"

    def test_returns_user_input(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "  world  ")
        assert _prompt("q?", default="hello") == "world"

    def test_converts_to_int(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "42")
        assert _prompt("q?", default=0, type_=int) == 42

    def test_converts_to_float(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "3.14")
        assert _prompt("q?", default=0.0, type_=float) == 3.14


class TestConfirm:
    def test_yes(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert _confirm("跑吗?", default=False) is True

    def test_no(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert _confirm("跑吗?", default=False) is False

    def test_default_yes_empty(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert _confirm("跑吗?", default=True) is True

    def test_default_no_empty(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert _confirm("跑吗?", default=False) is False


class TestBuildInteractiveConfig:
    def test_minimal_run(self, monkeypatch, tmp_path):
        tpl = tmp_path / "t.inp"
        tpl.write_text("guiopts begin\naero_alpha 0\nguiopts end\n")

        answers = iter([
            str(tpl),
            str(tmp_path / "out"),
            "0,4,8",
            "0",
            "0.6,0.8",
            "",
            "",
            "",
            "",
            "n",
            "y",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(answers))

        cfg = build_sweep_config_interactive()
        assert cfg["template"] == str(tpl)
        assert cfg["sweeps"]["alpha"] == [0.0, 4.0, 8.0]
        assert cfg["sweeps"]["mach"] == [0.6, 0.8]
        assert cfg["sweeps"]["T_inf"] == [288.15]
        assert cfg["sweeps"]["p_inf"] == [101325.0]
        assert cfg.get("dry_run") is False

    def test_dry_run_yes(self, monkeypatch, tmp_path):
        tpl = tmp_path / "t.inp"
        tpl.write_text("x")
        answers = iter([
            str(tpl),
            str(tmp_path / "out"),
            "0",
            "0",
            "0.6",
            "",
            "",
            "",
            "",
            "y",
            "y",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(answers))
        cfg = build_sweep_config_interactive()
        assert cfg["dry_run"] is True

    def test_cancelled(self, monkeypatch, tmp_path):
        tpl = tmp_path / "t.inp"
        tpl.write_text("x")
        answers = iter([
            str(tpl),
            str(tmp_path / "out"),
            "0",
            "0",
            "0.6",
            "",
            "",
            "",
            "",
            "n",
            "n",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(answers))
        cfg = build_sweep_config_interactive()
        assert cfg is None
