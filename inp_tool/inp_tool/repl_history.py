"""REPL 命令历史持久化。

存到 ~/.inp_history,每行一条,纯文本。Unix/macOS 接 readline,Windows 降级到纯内存。
"""
import sys
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional


def _history_path() -> Path:
    return Path.home() / '.inp_history'


class HistoryStore:
    """内存 deque + 磁盘 FIFO 同步。"""

    def __init__(self, maxlen: int = 1000, path: Optional[Path] = None):
        self._maxlen = maxlen
        self._path = path or _history_path()
        self._buf: Deque[str] = deque(maxlen=maxlen)

    def load(self) -> List[str]:
        """从磁盘读入到内存。返回加载的命令列表(也存到 self._buf)。"""
        self._buf.clear()
        if self._path.exists():
            try:
                lines = self._path.read_text(encoding='utf-8').splitlines()
            except OSError:
                lines = []
            for line in lines[-self._maxlen:]:
                if line:
                    self._buf.append(line)
        return list(self._buf)

    def append(self, line: str) -> None:
        if line:
            self._buf.append(line)

    def save(self) -> None:
        """把内存命令一次性写回磁盘。"""
        try:
            self._path.write_text(
                '\n'.join(self._buf) + ('\n' if self._buf else ''),
                encoding='utf-8',
            )
        except OSError:
            pass  # 静默:写失败不应阻塞退出

    def __iter__(self):
        return iter(self._buf)

    def recent(self, n: int = 20) -> List[str]:
        return list(self._buf)[-n:]

    # ----- readline 集成(Unix/macOS) ------------------------------------

    def bind_readline(self) -> bool:
        """把历史接进 readline buffer(若有)。返回是否成功。"""
        if sys.platform.startswith('win'):
            return False
        # 下面的 readline 集成只跑在 Unix 且 readline 可用时,Windows CI 不可达
        try:  # pragma: no cover
            import readline
            for line in self._buf:
                readline.add_history(line)
            import atexit
            def _save_on_exit():  # pragma: no cover
                try:
                    for i in range(readline.get_current_history_length()):
                        self._buf.append(readline.get_history_item(i + 1))
                except Exception:
                    pass
                self.save()
            atexit.register(_save_on_exit)
            return True
        except (ImportError, Exception):
            return False
