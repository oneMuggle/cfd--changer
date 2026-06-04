"""
mcfd.inp shell 补全 — Phase D RED

测试目标:
- inp-tool completion bash 输出 bash 补全脚本
- inp-tool completion zsh 输出 zsh 补全脚本
- inp-tool completion fish 输出 fish 补全脚本
- 输出含正确的 complete 指令
"""
from __future__ import annotations
import pytest
from inp_tool.cli import generate_completion


class TestGenerateCompletion:
    def test_bash_contains_complete(self):
        out = generate_completion("bash")
        assert "complete -F" in out
        assert "inp-tool" in out

    def test_bash_lists_subcommands(self):
        out = generate_completion("bash")
        for sub in ("parse", "get", "set", "diff", "info", "sweep", "completion"):
            assert sub in out, f"bash completion should list {sub!r}"

    def test_zsh_contains_compdef(self):
        out = generate_completion("zsh")
        assert "#compdef" in out
        assert "inp-tool" in out

    def test_fish_contains_complete_c(self):
        out = generate_completion("fish")
        assert "complete -c" in out
        assert "inp-tool" in out

    def test_unknown_shell_raises(self):
        with pytest.raises(ValueError, match="shell"):
            generate_completion("tcsh")

    def test_sweep_subcommand_options_completed(self):
        out = generate_completion("bash")
        for opt in ("--alpha", "--beta", "--mach", "--out", "--dry-run", "-i"):
            assert opt in out, f"sweep completion should list {opt!r}"
