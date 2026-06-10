"""
mcfd.inp sweep 交互式 CLI — v0.8.2

v0.8.2 起:`build_sweep_config_interactive` 必填 source_dir(template 自动取 source_dir/mcfd.inp)。
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
    @pytest.fixture
    def base_case_dir(self, tmp_path):
        """v0.8.2:source_dir 是目录,内含 mcfd.inp"""
        base = tmp_path / "base"
        base.mkdir()
        (base / "mcfd.inp").write_text("guiopts begin\naero_alpha 0\nguiopts end\n")
        return base

    def test_minimal_run(self, monkeypatch, base_case_dir, tmp_path):
        """v0.8.2:新顺序 — source_dir 必填第一位,template 自动取其下 mcfd.inp。"""
        answers = iter([
            str(base_case_dir),
            "hardlink",
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
        assert cfg["template"] == str(base_case_dir / "mcfd.inp")
        assert cfg["sweeps"]["alpha"] == [0.0, 4.0, 8.0]
        assert cfg["sweeps"]["mach"] == [0.6, 0.8]
        assert cfg["sweeps"]["T_inf"] == [288.15]
        assert cfg["sweeps"]["p_inf"] == [101325.0]
        assert cfg.get("dry_run") is False
        assert cfg["source_dir"] == str(base_case_dir)
        assert cfg["copy_strategy"] == "hardlink"

    def test_dry_run_yes(self, monkeypatch, base_case_dir, tmp_path):
        answers = iter([
            str(base_case_dir),
            "hardlink",
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
        assert cfg["source_dir"] == str(base_case_dir)

    def test_cancelled(self, monkeypatch, base_case_dir, tmp_path):
        answers = iter([
            str(base_case_dir),
            "hardlink",
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

    def test_with_source_dir(self, monkeypatch, base_case_dir, tmp_path):
        """v0.8.2:用户输入 source_dir 时,cfg 含 source_dir + copy_strategy(template 自动取)。"""
        answers = iter([
            str(base_case_dir),
            "copy",
            str(tmp_path / "out"),
            "0,4",
            "0",
            "0.6",
            "",
            "",
            "",
            "",
            "n",
            "y",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(answers))
        cfg = build_sweep_config_interactive()
        assert cfg["source_dir"] == str(base_case_dir)
        assert cfg["copy_strategy"] == "copy"
        assert cfg["template"] == str(base_case_dir / "mcfd.inp")
