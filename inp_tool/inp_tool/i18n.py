"""
inp_tool 国际化(i18n)模块 v0.7.1

极简设计:纯 stdlib dict + format 占位符 + 运行时语言切换。
零新依赖(符合项目"零运行时依赖"约束)。

用法:
    from inp_tool.i18n import t, set_lang
    set_lang("zh")  # 默认
    msg = t("repl.intro", ver="0.7.1")  # "inp-tool 0.7.1 交互式外壳"

环境变量:
    INP_TOOL_LANG=zh|en  # 兜底默认(模块加载时读一次)
"""
from __future__ import annotations
import os
from typing import Any, Dict

# 模块加载时读 INP_TOOL_LANG(作为兜底默认)
_DEFAULT_LANG = os.environ.get("INP_TOOL_LANG", "zh")
if _DEFAULT_LANG not in ("zh", "en"):
    _DEFAULT_LANG = "zh"  # 未知语言回退到 zh

_CURRENT_LANG: str = _DEFAULT_LANG


# ============================================================
# 字符串字典
# ============================================================
# 命名空间:
# - repl.*    REPL 提示 / banner / 快速开始 / help 文案
# - error.*   错误信息(含"建议下一步"段)
# - help.*    单命令 4 段 help(用途/语法/示例/下一步)
# - wizard.*  任务向导标题 / 步骤 / 选项
MESSAGES: Dict[str, Dict[str, str]] = {
    "zh": {
        # ---------- repl ----------
        "repl.intro": (
            "inp-tool {ver} 交互式外壳"
            "    欢迎使用 inp-tool!输入 `tutorial` 走完 5 步快速上手,"
            "`wizard` 走任务向导。"
            "    Type 'help' for commands, 'exit' to quit."
        ),
        "repl.welcome": (
            "欢迎使用 inp-tool!输入 `tutorial` 走完 5 步快速上手,"
            "`wizard` 走任务向导。"
        ),
        "repl.quickstart.title": "快速开始(5 个最常用命令):",
        "repl.quickstart.cmd_load": "load <路径>",
        "repl.quickstart.cmd_load_desc": "加载 .inp 文件",
        "repl.quickstart.cmd_info": "info",
        "repl.quickstart.cmd_info_desc": "查看当前文件结构",
        "repl.quickstart.cmd_aero": "aero Ma=0.8 alpha=5",
        "repl.quickstart.cmd_aero_desc": "设置来流参数",
        "repl.quickstart.cmd_save": "save",
        "repl.quickstart.cmd_save_desc": "保存到原文件",
        "repl.quickstart.cmd_sweep": "sweep ...",
        "repl.quickstart.cmd_sweep_desc": "批量生成算例",
        "repl.help_hint": (
            "输入 `help` 查看全部命令,`help <cmd>` 查看单命令详细帮助,"
            "`exit` 退出。"
        ),
        # ---------- error ----------
        "error.no_file_current": (
            "尚未加载文件。请先用 `load <路径>` 加载 .inp 文件"
        ),
        "error.no_file_current_with_hint": (
            "尚未加载文件。请先用 `load <路径>` 加载 .inp 文件"
            "    示例:load examples/mcfd_v2_modified.inp"
        ),
        "error.unknown_command": "未知命令 '{cmd}'",
        "error.unknown_command_with_suggest": (
            "未知命令 '{cmd}'。您是不是想用:{suggest} ?"
            "    输入 `help` 查看全部命令。"
        ),
        "error.set_value_must_be_number": (
            "'{val}' 不是有效数字。set 期望:<block> <key> <数值>"
            "    示例:set guiopts aero_alpha 5.0"
        ),
        "error.sweep_no_template": (
            "sweep 至少需要一个 .inp 模板路径。"
            "    用法 1(快速):sweep examples/mcfd_v2_modified.inp --alpha 0,5,10"
            "    用法 2(交互):sweep -i"
            "    用法 3(配置):sweep-config sweep_demo.json"
        ),
        "error.file_not_found": "文件不存在:{path}",
        "error.parse_failed": "解析失败:{err}",
        "error.write_failed": "写入失败:{path} ({err})",
        "error.alias_not_loaded": "alias '{alias}' 未加载",
        "error.alias_dirty": "alias '{alias}' 有未保存改动(-f 强制卸载)",
        "error.use_requires_alias": "use 需要一个 alias(用 `files` 查看已加载)",
        "error.unload_requires_alias": "unload 需要一个 alias",
        "error.unload_empty": "unload 需要一个 alias",
        "error.load_requires_path": "load 需要文件路径",
        "error.get_requires_key": "get 需要一个 key",
        "error.set_requires_3": "set 格式:set <block> <key> <value>",
        "error.diff_requires_other": "diff 需要另一个 alias",
        "error.let_requires_eq": "let 格式:NAME=VALUE",
        "error.prefix": "错误",
        "error.shell_empty": "shell 命令为空",
    },
    "en": {
        # ---------- repl ----------
        "repl.intro": (
            "inp-tool {ver} interactive shell. "
            "Type 'help' for commands, 'exit' to quit. "
            "Tip: type `tutorial` for 5-step onboarding, `wizard` for tasks."
        ),
        "repl.welcome": (
            "Welcome to inp-tool! Type `tutorial` for 5-step onboarding, "
            "`wizard` for task wizards."
        ),
        "repl.quickstart.title": "Quick start (5 most common commands):",
        "repl.quickstart.cmd_load": "load <path>",
        "repl.quickstart.cmd_load_desc": "Load a .inp file",
        "repl.quickstart.cmd_info": "info",
        "repl.quickstart.cmd_info_desc": "Show current file structure",
        "repl.quickstart.cmd_aero": "aero Ma=0.8 alpha=5",
        "repl.quickstart.cmd_aero_desc": "Set freestream parameters",
        "repl.quickstart.cmd_save": "save",
        "repl.quickstart.cmd_save_desc": "Save to original file",
        "repl.quickstart.cmd_sweep": "sweep ...",
        "repl.quickstart.cmd_sweep_desc": "Batch-generate cases",
        "repl.help_hint": (
            "Type `help` for all commands, `help <cmd>` for one-command help, "
            "`exit` to quit."
        ),
        # ---------- error ----------
        "error.no_file_current": (
            "No file is current. Use `load <path>` to load a .inp file."
        ),
        "error.no_file_current_with_hint": (
            "No file is current. Use `load <path>` to load a .inp file."
            "    Example: load examples/mcfd_v2_modified.inp"
        ),
        "error.unknown_command": "Unknown command '{cmd}'",
        "error.unknown_command_with_suggest": (
            "Unknown command '{cmd}'. Did you mean: {suggest}?"
            "    Type `help` for all commands."
        ),
        "error.set_value_must_be_number": (
            "'{val}' is not a valid number. set expects: <block> <key> <number>"
            "    Example: set guiopts aero_alpha 5.0"
        ),
        "error.sweep_no_template": (
            "sweep needs at least a .inp template path."
            "    Usage 1 (quick): sweep examples/mcfd_v2_modified.inp --alpha 0,5,10"
            "    Usage 2 (interactive): sweep -i"
            "    Usage 3 (config): sweep-config sweep_demo.json"
        ),
        "error.file_not_found": "File not found: {path}",
        "error.parse_failed": "Parse failed: {err}",
        "error.write_failed": "Write failed: {path} ({err})",
        "error.alias_not_loaded": "alias '{alias}' not loaded",
        "error.alias_dirty": "alias '{alias}' has unsaved changes (use -f to force)",
        "error.use_requires_alias": "use requires an alias (type `files` to see loaded)",
        "error.unload_requires_alias": "unload requires an alias",
        "error.unload_empty": "unload requires an alias",
        "error.load_requires_path": "load requires a file path",
        "error.get_requires_key": "get requires a key",
        "error.set_requires_3": "set requires: set <block> <key> <value>",
        "error.diff_requires_other": "diff requires another alias",
        "error.let_requires_eq": "let requires NAME=VALUE",
        "error.prefix": "error",
        "error.shell_empty": "empty shell command",
    },
}


# ============================================================
# 公共 API
# ============================================================
def get_lang() -> str:
    """当前语言(返回 'zh' 或 'en')"""
    return _CURRENT_LANG


def set_lang(lang: str) -> None:
    """切换语言:zh / en

    Raises:
        ValueError: 未知语言(防止 typo silently 用错的字典)
    """
    global _CURRENT_LANG
    if lang not in MESSAGES:
        raise ValueError(
            f"i18n: unsupported language {lang!r} "
            f"(supported: {sorted(MESSAGES.keys())})"
        )
    _CURRENT_LANG = lang


def t(key: str, **kwargs: Any) -> str:
    """取当前语言字符串,支持 {name} 占位符

    Args:
        key: 字符串 key(如 "repl.intro")
        **kwargs: 模板占位符替换

    Returns:
        替换后的字符串

    Raises:
        KeyError: 缺 key(显式错误,避免 silent fail)
    """
    msg = MESSAGES[_CURRENT_LANG].get(key)
    if msg is None:
        # 检查另一语言有没有(给出更友好的 debug 信息)
        other = "en" if _CURRENT_LANG == "zh" else "zh"
        if key in MESSAGES[other]:
            raise KeyError(
                f"i18n: missing key {key!r} in language {_CURRENT_LANG!r} "
                f"(present in {other!r})"
            )
        raise KeyError(f"i18n: missing key {key!r} in any language")
    if kwargs:
        try:
            return msg.format(**kwargs)
        except KeyError as e:
            raise KeyError(
                f"i18n: key {key!r} needs placeholder {e}, "
                f"got kwargs={list(kwargs.keys())}"
            ) from e
    return msg
