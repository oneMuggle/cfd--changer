"""REPL Tab 补全器。

纯函数式:接受 session + 参数,返回候选词列表。
由 repl.ShellREPL.complete() 调度。
"""
import os
import shutil
from typing import List, Optional

from .repl import REPL_COMMANDS
from .repl_state import ReplSession


class InpCompleter:
    def __init__(self, session: ReplSession):
        self.session = session

    # ----- 静态 ----------------------------------------------------------

    def complete_command(self, text: str) -> List[str]:
        cmds = sorted(REPL_COMMANDS)
        return [c for c in cmds if c.startswith(text)]

    def complete_shell(self, text: str) -> List[str]:
        # PATH 中所有可执行名
        path = os.environ.get('PATH', '')
        seen = set()
        out = []
        for d in path.split(os.pathsep):
            if not d:
                continue
            try:
                for name in os.listdir(d):
                    full = os.path.join(d, name)
                    if name in seen:
                        continue
                    if os.access(full, os.X_OK) and not os.path.isdir(full):
                        seen.add(name)
                        if name.startswith(text):
                            out.append(name)
            except OSError:
                continue
        return sorted(out)[:50]  # 限制数量

    # ----- 状态相关 ------------------------------------------------------

    def complete_alias(self, text: str) -> List[str]:
        return sorted(a for a in self.session.files if a.startswith(text))

    def complete_block(self, alias: str, text: str) -> List[str]:
        lf = self.session.files.get(alias)
        if lf is None:
            return []
        names = sorted({b.name for b in lf.inp.block_list})
        return [n for n in names if n.startswith(text)]

    def complete_key(self, alias: str, block: str, text: str) -> List[str]:
        lf = self.session.files.get(alias)
        if lf is None:
            return []
        keys = set()
        for b in lf.inp.block_list:
            if b.name == block:
                for s in b.statements:
                    keys.add(s.keyword)
        return sorted(k for k in keys if k.startswith(text))
