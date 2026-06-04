"""
mcfd.inp 数据模型 v0.2

变更:
- Block 列表(支持同名多次出现)
- Stmt 复合语句(支持多行 values,例如 info set 的 seq.# + 多行 values)
- comment_after 字段在所有地方都保留
- InpFile.blocks 改为 OrderedDict-like 的 list 存储
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any, Union
import re


def infer_type(raw: str) -> Union[int, float, str]:
    s = raw.strip()
    if not s:
        return s
    try:
        s_norm = s.replace('d', 'e').replace('D', 'E')
        if '.' in s_norm or 'e' in s_norm or 'E' in s_norm:
            return float(s_norm)
        return int(s)
    except ValueError:
        return s


@dataclass
class Value:
    raw: str
    typed: Any = None

    def __post_init__(self):
        if self.typed is None:
            self.typed = infer_type(self.raw)

    def __str__(self):
        return self.raw


@dataclass
class Stmt:
    """
    一条语句。
    - 普通语句:keyword + values (1 行)
    - 复合语句:keyword + values (1 行) + children (后续多行,典型是 info set 的 seq.# + values)
    """
    keyword: str
    values: list[Value] = field(default_factory=list)
    children: list['Stmt'] = field(default_factory=list)  # 后续多行 values
    line: int = 0
    raw: str = ''
    comment_after: str = ''
    # preserve_format 字段(v0.4+):
    raw_with_ws: str = ''     # 完整一行(含前导空白 + 行尾空白 + 注释)
    leading_ws: str = ''      # 行首空白(缩进/对齐)
    trailing_ws: str = ''     # 行尾空白(罕见但保留)

    @property
    def values_raw(self) -> list[str]:
        return [v.raw for v in self.values]

    @property
    def values_typed(self) -> list[Any]:
        return [v.typed for v in self.values]

    def get(self, i: int, default=None):
        if 0 <= i < len(self.values):
            return self.values[i].typed
        return default

    def set(self, i: int, value):
        if 0 <= i < len(self.values):
            v = self.values[i]
            v.raw = str(value)
            v.typed = infer_type(str(value))

    def child_values(self) -> list[list[Value]]:
        """返回所有 children 的 values 列表(每行一个)"""
        return [c.values for c in self.children if c.keyword == 'values']

    def all_values(self) -> list[Value]:
        """返回主行 + 所有 children 的 values(扁平)"""
        result = list(self.values)
        for c in self.children:
            result.extend(c.values)
        return result

    def __repr__(self):
        vs = ' '.join(self.values_raw)
        if self.children:
            vs += f' + {len(self.children)} child lines'
        return f'Stm({self.keyword!r} {vs!r} L{self.line})'


@dataclass
class Block:
    """一个 begin/end 块。多个同名块都保留。"""
    name: str
    begin_line: int
    end_line: int
    statements: list[Stmt] = field(default_factory=list)
    pre_comments: list[str] = field(default_factory=list)
    trailing_comments: list[str] = field(default_factory=list)  # end 行前的注释

    def get(self, keyword: str, default=None):
        for s in self.statements:
            if s.keyword == keyword and s.values:
                return s.values[0].typed
        return default

    def get_value(self, keyword: str) -> Optional[Value]:
        for s in self.statements:
            if s.keyword == keyword and s.values:
                return s.values[0]
        return None

    def get_stmt(self, keyword: str) -> Optional[Stmt]:
        for s in self.statements:
            if s.keyword == keyword:
                return s
        return None

    def get_all(self, keyword: str) -> list[Stmt]:
        return [s for s in self.statements if s.keyword == keyword]

    def set(self, keyword: str, value) -> bool:
        for s in self.statements:
            if s.keyword == keyword and s.values:
                s.set(0, value)
                return True
        return False

    def set_all(self, keyword: str, value) -> int:
        n = 0
        for s in self.statements:
            if s.keyword == keyword and s.values:
                s.set(0, value)
                n += 1
        return n

    def append(self, keyword: str, *values) -> Stmt:
        vals = [Value(raw=str(v)) for v in values]
        stmt = Stmt(keyword=keyword, values=vals, line=0)
        self.statements.append(stmt)
        return stmt

    def remove(self, keyword: str) -> int:
        before = len(self.statements)
        self.statements = [s for s in self.statements if s.keyword != keyword]
        return before - len(self.statements)

    def __repr__(self):
        return f'Block({self.name!r}, {len(self.statements)} stmts, L{self.begin_line}-{self.end_line})'


@dataclass
class InpFile:
    """整个 .inp 文件"""
    path: str = ''
    header_comments: list[str] = field(default_factory=list)
    # 块列表(按出现顺序;同名块多次出现都保留)
    block_list: list[Block] = field(default_factory=list)
    # 顶层非块语句
    top_stmts: list[Stmt] = field(default_factory=list)
    # 顶层语句之间的装饰注释
    top_decor: list[tuple[int, str]] = field(default_factory=list)
    # 文件末尾的 wrapper 行
    tail_lines: list[str] = field(default_factory=list)

    # === 兼容性:blocks 字典访问 ===
    @property
    def blocks(self) -> dict[str, list[Block]]:
        """返回 {name: [Block...]} 字典(同名多个实例)"""
        d: dict[str, list[Block]] = {}
        for b in self.block_list:
            d.setdefault(b.name, []).append(b)
        return d

    def get_block(self, name: str, idx: int = 0) -> Optional[Block]:
        """取同名块的第 idx 个(默认第一个)"""
        lst = self.blocks.get(name, [])
        if idx < len(lst):
            return lst[idx]
        return None

    def all_blocks(self, name: str) -> list[Block]:
        return self.blocks.get(name, [])

    def get(self, block: str, keyword: str, default=None):
        b = self.get_block(block)
        if b is not None:
            v = b.get(keyword, default)
            if v is not None:
                return v
        return default

    def set(self, block: str, keyword: str, value, idx: int = 0) -> bool:
        b = self.get_block(block, idx)
        if b is not None:
            return b.set(keyword, value)
        return False

    def __repr__(self):
        return f'InpFile({len(self.block_list)} blocks, {len(self.top_stmts)} top_stmts)'


# 兼容旧版 InpFile 构造:blocks 改为 list
def _to_old(inp: InpFile):
    """把新 InpFile 转成旧接口 (blocks: dict[name, Block])
    旧接口:blocks[name] -> Block(同名的取第一个,后续的丢掉)
    仅用于向后兼容测试。"""
    class _OldInp:
        pass
    o = _OldInp()
    o.path = inp.path
    o.header_comments = inp.header_comments
    o.top_stmts = inp.top_stmts
    o.top_decor = inp.top_decor
    o.tail_lines = inp.tail_lines
    o.blocks = {}
    o.block_order = []
    for b in inp.block_list:
        if b.name not in o.blocks:
            o.blocks[b.name] = b
            o.block_order.append(b.name)
        else:
            o.block_order.append(b.name + '___DUP')
    o.get_block = inp.get_block
    o.get = inp.get
    o.set = inp.set
    return o
