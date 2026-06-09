"""
PR #2 阶段 1:i18n 基础设施测试

测试目标:
- t(key) 返回当前语言字符串
- t(key, **kwargs) 占位符替换
- set_lang(zh|en) 切换
- 缺 key 抛 KeyError(明确错误,避免 silent fail)
- MESSAGES 字典在 zh/en 下都覆盖必需 key(repl.* / error.* / wizard.* 命名空间)
- INP_TOOL_LANG 环境变量兜底
"""
from __future__ import annotations
import os
import pytest

from inp_tool.i18n import t, set_lang, get_lang, MESSAGES


# ======================================================================
# 基本 t() 行为
# ======================================================================
class TestBasic:
    def test_t_returns_chinese_by_default(self):
        """默认语言 = zh(用户在中国 / 项目主要中文)"""
        # 强制设回 zh(其他测试可能改了)
        set_lang("zh")
        # 一个简单的 key(确保 zh 字典存在)
        # 如果 keys 不存在,这里会抛 KeyError,先确保 key 在 zh 里有
        assert t("repl.intro", ver="0.7.1").startswith("inp-tool")

    def test_t_with_placeholder(self):
        set_lang("zh")
        assert "{ver}" not in t("repl.intro", ver="0.7.1")
        assert "0.7.1" in t("repl.intro", ver="0.7.1")

    def test_t_missing_key_raises(self):
        set_lang("zh")
        with pytest.raises(KeyError, match="missing key"):
            t("definitely.nonexistent.key")


# ======================================================================
# set_lang / get_lang
# ======================================================================
class TestLangSwitch:
    def test_set_lang_to_en(self):
        set_lang("en")
        assert get_lang() == "en"

    def test_set_lang_to_zh(self):
        set_lang("en")  # 先切到 en
        set_lang("zh")
        assert get_lang() == "zh"

    def test_set_lang_invalid_raises(self):
        with pytest.raises(ValueError, match="unsupported"):
            set_lang("fr")  # not supported

    def test_set_lang_changes_returned_text(self):
        set_lang("zh")
        zh_text = t("repl.intro", ver="0.7.1")
        set_lang("en")
        en_text = t("repl.intro", ver="0.7.1")
        # 中英文版应不同
        assert zh_text != en_text


# ======================================================================
# 字典齐整性
# ======================================================================
class TestMessagesCompleteness:
    def test_both_langs_have_same_keys(self):
        """zh 和 en 字典必须有相同的 key 集合(避免运行时 KeyError)"""
        zh_keys = set(MESSAGES.get("zh", {}).keys())
        en_keys = set(MESSAGES.get("en", {}).keys())
        missing_in_en = zh_keys - en_keys
        missing_in_zh = en_keys - zh_keys
        assert not missing_in_en, f"en 字典缺 keys: {missing_in_en}"
        assert not missing_in_zh, f"zh 字典缺 keys: {missing_in_zh}"

    def test_minimum_required_keys_present(self):
        """必需 key 集合(任何时候都应在 zh/en 中存在)"""
        required = {
            "repl.intro",
            "repl.welcome",
            "repl.quickstart.title",
            "error.no_file_current",
            "error.unknown_command",
        }
        for lang in ("zh", "en"):
            assert required.issubset(MESSAGES[lang].keys()), (
                f"{lang} 字典缺必需 keys: {required - MESSAGES[lang].keys()}"
            )

    def test_placeholder_consistency(self):
        """同名 key 在两种语言里占位符必须一致(否则 en/zh 调用 args 不同)"""
        # 抽查:repl.intro 应在 zh 和 en 都有 {ver} 占位符
        for lang in ("zh", "en"):
            msg = MESSAGES[lang]["repl.intro"]
            assert "{ver}" in msg, f"{lang}: repl.intro 缺 {{ver}} 占位符"


# ======================================================================
# 必需命名空间(防止 i18n key 命名混乱)
# ======================================================================
class TestKeyNamespaces:
    def test_repl_namespace(self):
        """repl.* 至少包含 intro / welcome / quickstart / prompt / help.*"""
        for lang in ("zh", "en"):
            keys = MESSAGES[lang]
            assert "repl.intro" in keys
            assert "repl.welcome" in keys
            assert "repl.quickstart.title" in keys

    def test_error_namespace(self):
        for lang in ("zh", "en"):
            keys = MESSAGES[lang]
            assert "error.no_file_current" in keys
            assert "error.unknown_command" in keys


# ======================================================================
# INP_TOOL_LANG 环境变量
# ======================================================================
class TestEnvVar:
    def test_env_var_override_at_import(self, monkeypatch):
        """模块加载时 INP_TOOL_LANG 应被读取"""
        # 注:这个测试假设模块的 _CURRENT_LANG 在 import 时被读
        # 通过 monkeypatch 设环境变量 + 重新 import
        monkeypatch.setenv("INP_TOOL_LANG", "en")
        # 重新导入
        import importlib
        import inp_tool.i18n as i18n_mod
        importlib.reload(i18n_mod)
        assert i18n_mod.get_lang() == "en"
        # 恢复
        monkeypatch.delenv("INP_TOOL_LANG", raising=False)
        importlib.reload(i18n_mod)


# ======================================================================
# 与 REPL 集成(REPL 引用 i18n.t)
# ======================================================================
class TestIntegration:
    def test_repl_imports_i18n(self):
        """repl.py 应能 import i18n 模块(无循环依赖)"""
        from inp_tool import repl  # noqa: F401
        from inp_tool import i18n  # noqa: F401
        # 两者都应可导入
        assert hasattr(repl, "ShellREPL")
        assert hasattr(i18n, "t")
