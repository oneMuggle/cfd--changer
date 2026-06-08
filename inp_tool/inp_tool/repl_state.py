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
