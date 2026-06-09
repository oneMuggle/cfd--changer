"""
PR #2 阶段 2:REPL 中文化测试

测试目标:
- zh 模式下 REPL intro 含中文
- zh 模式下错误信息含中文
- zh 模式下快速开始面板打印(5 命令)
- zh 模式下 help 输出含中文分组
- 切回 en 模式仍能工作
- "tutorial" 命令保留
- "wizard" 命令新增
"""
from __future__ import annotations
import io
from contextlib import redirect_stderr, redirect_stdout
import pytest

from inp_tool.repl import ShellREPL
from inp_tool import i18n


# autouse: 切到 zh 模式(本文件所有测试)
@pytest.fixture(autouse=True)
def _force_zh():
    i18n.set_lang("zh")
    yield
    i18n.set_lang("zh")  # 保持 zh


def _run(repl, *lines):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        for line in lines:
            repl.onecmd(line)
    return out.getvalue() + err.getvalue()


# ======================================================================
# intro / banner
# ======================================================================
class TestIntroZh:
    def test_intro_contains_chinese(self):
        r = ShellREPL()
        # 包含"交互式"或"外壳"
        assert "交互式" in r.intro or "外壳" in r.intro

    def test_intro_mentions_version(self):
        r = ShellREPL()
        from inp_tool import __version__
        assert __version__ in r.intro

    def test_intro_mentions_tutorial(self):
        r = ShellREPL()
        assert "tutorial" in r.intro  # 命令名英文,但提示中文


# ======================================================================
# 错误信息
# ======================================================================
class TestErrorMessagesZh:
    def test_load_nonexistent_file_zh(self, tmp_path):
        r = ShellREPL()
        out = _run(r, f"load {tmp_path}/nope.inp")
        # zh 错误:含"不存在"或"文件"
        assert "不存在" in out or "文件" in out

    def test_get_without_file_loaded_zh(self):
        r = ShellREPL()
        out = _run(r, "get foo")
        # zh 错误:含"加载"或"文件"
        assert "加载" in out or "文件" in out

    def test_set_without_file_loaded_zh(self):
        r = ShellREPL()
        out = _run(r, "set guiopts aero_alpha 5.0")
        assert "加载" in out or "文件" in out


# ======================================================================
# 命令列表
# ======================================================================
class TestCommandsAvailable:
    def test_tutorial_command_registered(self):
        r = ShellREPL()
        # 通过 help 列表确认
        out = _run(r, "help")
        assert "tutorial" in out

    def test_wizard_command_registered(self):
        r = ShellREPL()
        out = _run(r, "help")
        assert "wizard" in out

    def test_aero_command_still_registered(self):
        r = ShellREPL()
        out = _run(r, "help")
        assert "aero" in out

    def test_help_zh_contains_chinese_groups(self):
        r = ShellREPL()
        out = _run(r, "help")
        # 至少含一个中文分组标题
        assert "文件" in out or "编辑" in out or "批量" in out


# ======================================================================
# 中英切换
# ======================================================================
class TestLangSwitch:
    def test_switch_to_en_then_back_to_zh(self):
        r = ShellREPL()
        i18n.set_lang("en")
        en_intro = r.intro
        i18n.set_lang("zh")
        zh_intro = r.intro
        # 切换后 intro 改变
        assert en_intro != zh_intro

    def test_help_zh_differs_from_help_en(self):
        r = ShellREPL()
        i18n.set_lang("zh")
        zh_help = _run(r, "help")
        i18n.set_lang("en")
        en_help = _run(r, "help")
        # 至少一处不同(中文分组 vs 英文分组)
        assert zh_help != en_help


# ======================================================================
# 快速开始面板(REPL 启动后打印)
# ======================================================================
class TestQuickStartPanel:
    def test_quickstart_keys_present(self):
        """验证字典里有 quickstart 相关 key"""
        from inp_tool.i18n import MESSAGES
        zh = MESSAGES["zh"]
        assert "repl.quickstart.title" in zh
        assert "repl.quickstart.cmd_load" in zh
        assert "repl.quickstart.cmd_aero" in zh
