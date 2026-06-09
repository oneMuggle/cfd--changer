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

        # v0.8.0:source_dir 空时,copy_strategy prompt 跳过(只在 source_dir 非空时问)
        # 所以 12 个 prompt
        answers = iter([
            str(tpl),         # 1. template
            str(tmp_path / "out"),  # 2. output_dir
            "",               # 3. source_dir (v0.8.0 新加,空=flat 模式)
            "0,4,8",          # 4. alpha
            "0",              # 5. beta
            "0.6,0.8",        # 6. mach
            "",               # 7. T_inf
            "",               # 8. p_inf
            "",               # 9. naming
            "",               # 10. manifest
            "n",              # 11. dry_run confirm
            "y",              # 12. final confirm
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(answers))

        cfg = build_sweep_config_interactive()
        assert cfg["template"] == str(tpl)
        assert cfg["sweeps"]["alpha"] == [0.0, 4.0, 8.0]
        assert cfg["sweeps"]["mach"] == [0.6, 0.8]
        assert cfg["sweeps"]["T_inf"] == [288.15]
        assert cfg["sweeps"]["p_inf"] == [101325.0]
        assert cfg.get("dry_run") is False
        # v0.8.0:source_dir 空时 cfg 不含 source_dir(走 flat 模式)
        assert "source_dir" not in cfg

    def test_dry_run_yes(self, monkeypatch, tmp_path):
        tpl = tmp_path / "t.inp"
        tpl.write_text("x")
        answers = iter([
            str(tpl),
            str(tmp_path / "out"),
            "",               # source_dir
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
            "",               # source_dir
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

    def test_with_source_dir(self, monkeypatch, tmp_path):
        """v0.8.0:用户输入 source_dir 时,cfg 含 source_dir + copy_strategy"""
        tpl = tmp_path / "t.inp"
        tpl.write_text("x")
        base = tmp_path / "base"
        base.mkdir()
        answers = iter([
            str(tpl),
            str(tmp_path / "out"),
            str(base),        # source_dir(非空)
            "copy",           # copy_strategy
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
        assert cfg["source_dir"] == str(base)
        assert cfg["copy_strategy"] == "copy"
