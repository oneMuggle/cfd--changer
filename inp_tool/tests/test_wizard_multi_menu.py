"""
v0.10.0+:wizard.multi_menu helper 测试

多选菜单(单行 token 输入)。choices: [(key, "label_zh", "label_en", "value"), ...]
约定:输入支持空格分隔 "1 3"、逗号分隔 "1,3"、key 别名 "sst sa" 或 value "k-omega-sst"。

测试通过 monkeypatch builtins.input 喂入响应,验证返回值(选中的 value 列表)。
"""
from __future__ import annotations
import pytest
from inp_tool.wizard import multi_menu


# 标准 choices(turbulence 4 选)
TURB_CHOICES = [
    ("1", "sst (k-omega-sst)", "sst (k-omega-sst)", "sst"),
    ("2", "sa (spalart-allmaras)", "sa (spalart-allmaras)", "sa"),
    ("3", "k-eps (realizable-k-eps)", "k-eps (realizable-k-eps)", "keps"),
    ("4", "goldberg (goldberg_rt)", "goldberg (goldberg_rt)", "goldberg"),
    ("5", "laminar", "laminar", "laminar"),
]


class TestMultiMenuEmpty:
    """空输入 → 空列表(=跳过该 axis)。"""

    def test_empty_returns_empty_list(self, monkeypatch, capsys):
        """直接回车 → []。"""
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = multi_menu("选湍流:", TURB_CHOICES)
        assert result == []

    def test_whitespace_only_returns_empty(self, monkeypatch):
        """纯空格 → []。"""
        monkeypatch.setattr("builtins.input", lambda _: "   ")
        result = multi_menu("选湍流:", TURB_CHOICES)
        assert result == []


class TestMultiMenuKeySelection:
    """用数字 key("1" "2" 等)选择。"""

    def test_single_key(self, monkeypatch):
        """'1' → ['sst']。"""
        monkeypatch.setattr("builtins.input", lambda _: "1")
        result = multi_menu("选湍流:", TURB_CHOICES)
        assert result == ["sst"]

    def test_multiple_keys_space_separated(self, monkeypatch):
        """'1 2' → ['sst', 'sa']。"""
        monkeypatch.setattr("builtins.input", lambda _: "1 2")
        result = multi_menu("选湍流:", TURB_CHOICES)
        assert result == ["sst", "sa"]

    def test_multiple_keys_comma_separated(self, monkeypatch):
        """'1,3' → ['sst', 'keps']。"""
        monkeypatch.setattr("builtins.input", lambda _: "1,3")
        result = multi_menu("选湍流:", TURB_CHOICES)
        assert result == ["sst", "keps"]


class TestMultiMenuValueSelection:
    """用 value 字符串('sst' 'sa' 等)选择 — 用户友好。"""

    def test_value_string(self, monkeypatch):
        """'sst' → ['sst'](直接匹配 value)。"""
        monkeypatch.setattr("builtins.input", lambda _: "sst")
        result = multi_menu("选湍流:", TURB_CHOICES)
        assert result == ["sst"]

    def test_multiple_values(self, monkeypatch):
        """'sst sa' → ['sst', 'sa'](value 形式多选)。"""
        monkeypatch.setattr("builtins.input", lambda _: "sst sa")
        result = multi_menu("选湍流:", TURB_CHOICES)
        assert result == ["sst", "sa"]


class TestMultiMenuInvalid:
    """无效 token → 重新 prompt(不静默接受)。"""

    def test_invalid_token_reprompts(self, monkeypatch, capsys):
        """输入含无效 token → 报错并重新 prompt。"""
        responses = iter(["9", "1"])  # 9 无效,1 有效
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        result = multi_menu("选湍流:", TURB_CHOICES)
        assert result == ["sst"]
        # 错误信息含"无效"(中文)
        captured = capsys.readouterr()
        assert "无效" in captured.out or "invalid" in captured.out.lower()

    def test_mixed_valid_and_invalid(self, monkeypatch):
        """含无效 token → 重新 prompt,选中的不全保留。"""
        responses = iter(["1 9", "1 2"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        result = multi_menu("选湍流:", TURB_CHOICES)
        assert result == ["sst", "sa"]


class TestMultiMenuAllOptions:
    """全选场景。"""

    def test_select_all_five(self, monkeypatch):
        """'1 2 3 4 5' → 全部 5 个 value。"""
        monkeypatch.setattr("builtins.input", lambda _: "1 2 3 4 5")
        result = multi_menu("选湍流:", TURB_CHOICES)
        assert result == ["sst", "sa", "keps", "goldberg", "laminar"]

    def test_dedup_no_duplicates(self, monkeypatch):
        """'1 1 2' → 不重复 ['sst', 'sa'](保序去重)。"""
        monkeypatch.setattr("builtins.input", lambda _: "1 1 2")
        result = multi_menu("选湍流:", TURB_CHOICES)
        assert result == ["sst", "sa"]
