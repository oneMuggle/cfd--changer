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
        from pathlib import Path as P
        # 简化:仅支持 load PATH,无 'as' 语法(Task 4 完善)
        path_str = arg.strip()
        if not path_str:
            return
        try:
            self.session.load(P(path_str))
            self._refresh_prompt()
            print(f'loaded: {self.session.current}  ({path_str})')
        except Exception as e:
            print(f'error: {e}', file=sys.stderr)

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
