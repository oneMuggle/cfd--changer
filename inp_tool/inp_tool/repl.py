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

    def do_unload(self, arg):
        """unload ALIAS [-f] — 移除 alias(默认拒绝 dirty)"""
        parts = arg.strip().split()
        if not parts:
            self._err('unload requires an alias')
            return
        non_flags = [p for p in parts if p != '-f']
        if not non_flags:
            self._err('unload requires an alias')
            return
        alias = non_flags[0]
        force = '-f' in parts
        try:
            self.session.unload(alias, force=force)
        except KeyError:
            self._err(f"alias '{alias}' not loaded.")
            return
        except RuntimeError as e:
            self._err(str(e))
            return
        if self.session.current is None:
            self._refresh_prompt()

    def do_status(self, arg):
        """status — 列出每个 alias 的未保存改动

        TODO: 与 do_files 共享输出格式;若 status 演化(undo count, save time 等),可分裂
        """
        if not self.session.files:
            print('(no files loaded)')
            return
        for a, lf in self.session.files.items():
            mark = '*' if a == self.session.current else ' '
            if lf.dirty:
                print(f'{mark} {a:15s} {str(lf.path):40s}  [unsaved changes]')
            else:
                print(f'{mark} {a:15s} {str(lf.path):40s}  [clean]')

    def do_save(self, arg):
        """save [ALIAS] / save as PATH — 写回磁盘"""
        from .writer import to_text, write
        from pathlib import Path as P
        arg = arg.strip()
        if not arg:
            # 默认写 current
            target = self.session.current
            if not target:
                self._err('no file is current. use `use <alias>` or pass an alias.')
                return
            alias = target
            path = self.session.files[alias].path
        elif arg.startswith('as '):
            # save as <path>
            if not self.session.current:
                self._err('save as requires a current file')
                return
            alias = self.session.current
            path = P(arg[3:].strip())
        else:
            # save <alias>
            alias = arg.split()[0]
            if alias not in self.session.files:
                self._err(f"alias '{alias}' not loaded.")
                return
            path = self.session.files[alias].path
        try:
            write(self.session.files[alias].inp, str(path))
        except PermissionError as e:
            self._err(f'permission denied: {path} ({e})')
            return
        except OSError as e:
            self._err(f'write failed: {path} ({e})')
            return
        self.session.files[alias].dirty = False
        self.session.files[alias].last_saved_text = to_text(self.session.files[alias].inp)
        self.session.files[alias].path = path
        print(f'saved: {alias} -> {path}')

    def do_exit(self, arg):
        """exit the REPL"""
        return True

    def do_quit(self, arg):
        """alias for exit"""
        return True

    # ----- 委托给 cli.py 的 cmd_* ----------------------------------------

    def _ns(self, **kwargs):
        """构造 argparse.Namespace 包装,subcommands 期待这个类型。"""
        from argparse import Namespace
        return Namespace(**kwargs)

    def do_info(self, arg):
        """info — 显示当前文件的结构(委托 cmd_info)"""
        if not self.session.current:
            self._err('no file is current. type `load <path>` first.')
            return
        from .cli import cmd_info
        ns = self._ns(file=str(self.session.files[self.session.current].path))
        rc = cmd_info(ns)
        if rc:
            self._err(f'cmd_info returned {rc}')

    def do_get(self, arg):
        """get KEY [-b BLOCK] [-i IDX] — 读一个值(委托 cmd_get)"""
        if not self.session.current:
            self._err('no file is current.')
            return
        from .cli import cmd_get
        import shlex
        try:
            tokens = shlex.split(arg)
        except ValueError as e:
            self._err(f'parse error: {e}')
            return
        block = None
        block_idx = None
        if '-b' in tokens:
            i = tokens.index('-b')
            block = tokens[i + 1] if i + 1 < len(tokens) else None
        if '-i' in tokens:
            i = tokens.index('-i')
            block_idx = int(tokens[i + 1]) if i + 1 < len(tokens) else None
        # 第一个非 flag 的 token 是 key
        key = next((t for t in tokens if not t.startswith('-') and t != block), None)
        if not key:
            self._err('get requires a key')
            return
        ns = self._ns(
            file=str(self.session.files[self.session.current].path),
            block=block, block_idx=block_idx, key=key,
        )
        rc = cmd_get(ns)
        if rc:
            self._err(f'cmd_get returned {rc}')

    def do_set(self, arg):
        """set BLOCK KEY VALUE — 改一个值,标记 dirty(委托 cmd_set)"""
        if not self.session.current:
            self._err('no file is current.')
            return
        from .cli import cmd_set
        import shlex
        try:
            tokens = shlex.split(arg)
        except ValueError as e:
            self._err(f'parse error: {e}')
            return
        if len(tokens) < 3:
            self._err('set requires: set <block> <key> <value>')
            return
        block, key, value = tokens[0], tokens[1], tokens[2]
        alias = self.session.current
        lf = self.session.files[alias]
        # 拍旧值
        b = lf.inp.get_block(block, 0)
        old_values = []
        if b is not None:
            v = b.get_value(key)
            if v is not None:
                old_values = list(v.raw) if isinstance(v.raw, list) else [v.raw]
        # 调 handler(不写盘,handler 写盘逻辑靠 args.output,默认会写)
        ns = self._ns(
            file=str(lf.path), block=block, block_idx=0, key=key, value=value,
            output=None, force=False,
        )
        rc = cmd_set(ns)
        if rc == 0:
            lf.dirty = True
            from .repl_state import UndoEntry
            self.session.undo.push(UndoEntry(
                alias=alias, block=block, key=key, old_values=old_values,
            ))

    def do_diff(self, arg):
        """diff ALIAS — current vs 指定 alias(委托 cmd_diff)"""
        if not self.session.current:
            self._err('no file is current.')
            return
        from .cli import cmd_diff
        other = arg.strip()
        if not other:
            self._err('diff requires another alias')
            return
        if other not in self.session.files:
            self._err(f"alias '{other}' not loaded.")
            return
        a_path = str(self.session.files[self.session.current].path)
        b_path = str(self.session.files[other].path)
        ns = self._ns(a=a_path, b=b_path, unified=False)
        rc = cmd_diff(ns)
        if rc:
            self._err(f'cmd_diff returned {rc}')

    def do_parse(self, arg):
        """parse — 显示当前文件完整结构(委托 cmd_parse)"""
        if not self.session.current:
            self._err('no file is current.')
            return
        from .cli import cmd_parse
        ns = self._ns(file=str(self.session.files[self.session.current].path))
        rc = cmd_parse(ns)
        if rc:
            self._err(f'cmd_parse returned {rc}')


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
