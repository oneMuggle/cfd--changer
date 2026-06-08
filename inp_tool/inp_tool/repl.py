"""inp-tool 交互式 REPL。

继承 stdlib cmd.Cmd,把每条用户输入解析后委托给 cli.py 的 cmd_* handler。
状态由 ReplSession 管理,IO 通过 stdout/stderr。
"""
import cmd
import sys
from typing import List, Optional

from .repl_state import ReplSession


# REPL 暴露的命令名集合(给 help / 补全用)
REPL_COMMANDS = {
    'load', 'unload', 'files', 'use', 'status', 'save',
    'info', 'get', 'set', 'diff', 'sweep', 'parse',
    'undo', 'let', 'help', 'history', 'exit', 'quit',
}


class ShellREPL(cmd.Cmd):
    intro = (
        "inp-tool v0.5.0 interactive shell. "
        "Type 'help' for commands, 'exit' to quit."
    )
    prompt = 'inp> '

    def __init__(self, session: Optional[ReplSession] = None, completekey: str = 'tab'):
        super().__init__(completekey=completekey)
        self.session = session or ReplSession()
        self._refresh_prompt()

    # ----- 内部辅助 -------------------------------------------------------

    def _refresh_prompt(self) -> None:
        if self.session.current:
            self.prompt = f'inp[{self.session.current}]> '
        else:
            self.prompt = 'inp> '

    def _print(self, msg: str) -> None:
        print(msg)

    def _err(self, msg: str) -> None:
        print(f'error: {msg}', file=sys.stderr)

    # ----- 占位 do_*(后续任务逐步实现) ------------------------------------

    def do_help(self, arg):
        if arg:
            cmd_method = getattr(self, f'do_{arg}', None)
            if cmd_method and callable(cmd_method):
                doc = (cmd_method.__doc__ or '').strip()
                print(f'{arg}: {doc}' if doc else arg)
            else:
                print(f'no such command: {arg}')
        else:
            print('available commands:')
            for name in sorted(REPL_COMMANDS):
                method = getattr(self, f'do_{name}', None)
                doc = (method.__doc__ or '').splitlines()[0] if method and method.__doc__ else ''
                print(f'  {name:10s} {doc}')

    def do_load(self, arg):
        """load PATH [as ALIAS] — 加载 .inp 到 session,自动设为 current"""
        if not arg.strip():
            self._err('load requires a file path')
            return
        # 拆分 'as ALIAS'(可选)
        parts = arg.strip().split()
        if 'as' in parts:
            i = parts.index('as')
            path_str = ' '.join(parts[:i])
            alias = parts[i + 1] if i + 1 < len(parts) else None
        else:
            path_str = arg.strip()
            alias = None
        from pathlib import Path
        path = Path(path_str)
        if not path.exists():
            self._err(f'file not found: {path}')
            return
        try:
            actual = self.session.load(path, alias=alias)
        except Exception as e:
            self._err(f'parse failed: {e}')
            return
        self._refresh_prompt()
        print(f'loaded: {actual}  ({path})')

    def do_files(self, arg):
        """files — 列出已加载 alias / 路径 / 状态"""
        if not self.session.files:
            print('(no files loaded)')
            return
        for a, lf in self.session.files.items():
            mark = '*' if a == self.session.current else ' '
            tag = 'dirty' if lf.dirty else 'clean'
            print(f'{mark} {a:15s} {str(lf.path):40s}  [{tag}]')

    def do_use(self, arg):
        """use ALIAS — 切换 current 指针"""
        a = arg.strip()
        if not a:
            self._err('use requires an alias')
            return
        try:
            self.session.use(a)
        except KeyError:
            self._err(f"alias '{a}' not loaded. type 'files' to see loaded.")
            return
        self._refresh_prompt()

    def do_exit(self, arg):
        """exit the REPL"""
        return True

    def do_quit(self, arg):
        """alias for exit"""
        return True


def main(preload: Optional[List[str]] = None) -> int:
    """REPL 入口。从 CLI 的 `shell` 子命令调用。

    preload: 启动时预加载的文件路径列表(自动按 basename 起 alias)。
    """
    repl = ShellREPL()
    for path in preload or []:
        repl.onecmd(f'load {path}')
    try:
        repl.cmdloop()
    except KeyboardInterrupt:
        print()  # 换行
    return 0
