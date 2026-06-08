"""REPL 状态数据类:LoadedFile / UndoLog / ReplSession。

纯数据 + 状态变更方法,无 IO,无 stdout。下游由 repl.py 使用。
"""
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional


@dataclass
class LoadedFile:
    """REPL 中加载的一个 .inp 文件,含 alias、路径、解析模型、dirty 标记。"""
    alias: str
    path: Path
    inp: Any  # 故意不导入 InpFile,避免循环依赖;运行时由 parser.parse_file 填充
    dirty: bool = False
    last_saved_text: Optional[str] = None


@dataclass
class UndoEntry:
    """一次 set 改动的可回滚快照。"""
    alias: str
    block: str
    key: str
    old_values: List[Any]  # 改前 values(可能多 token)


class UndoLog:
    """线性 undo 栈,只回滚 set 改的 (alias, block, key)。"""
    def __init__(self, maxlen: int = 100):
        self._entries: Deque[UndoEntry] = deque(maxlen=maxlen)

    def push(self, entry: UndoEntry) -> None:
        self._entries.append(entry)

    def pop(self) -> Optional[UndoEntry]:
        if not self._entries:
            return None
        return self._entries.pop()

    def __len__(self) -> int:
        return len(self._entries)


@dataclass
class ReplSession:
    """整个 REPL 会话的根状态。"""
    files: Dict[str, LoadedFile] = field(default_factory=dict)
    current: Optional[str] = None
    undo: UndoLog = field(default_factory=UndoLog)
    variables: Dict[str, str] = field(default_factory=dict)

    def load(self, path: Path, alias: Optional[str] = None) -> str:
        """加载文件到 session,返回实际使用的 alias。

        alias 为 None 时用 Path(path).stem;冲突时追加 _2/_3/...。
        """
        from .parser import parse_file  # 延迟导入避免循环

        if alias is None:
            alias = path.stem
        original = alias
        n = 2
        while alias in self.files:
            alias = f'{original}_{n}'
            n += 1
        self.files[alias] = LoadedFile(alias=alias, path=path, inp=parse_file(str(path)))
        self.current = alias
        return alias

    def unload(self, alias: str, force: bool = False) -> None:
        """从 session 移除文件。dirty 状态默认拒绝;force=True 强卸。"""
        lf = self.files[alias]  # KeyError 自然抛出
        if lf.dirty and not force:
            raise RuntimeError(
                f"alias '{alias}' has unsaved changes; use unload -f to force"
            )
        del self.files[alias]
        if self.current == alias:
            self.current = None

    def use(self, alias: str) -> None:
        """切换 current 指针。alias 不存在时抛 KeyError。"""
        if alias not in self.files:
            raise KeyError(alias)
        self.current = alias
