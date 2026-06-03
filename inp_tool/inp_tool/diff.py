"""
mcfd.inp diff v0.2

变更:
- 适配新模型(InpFile.block_list 而非 dict)
- 复合 Stmt 比较(主行 + children 一起看)
- 重复同名块按索引配对
"""
from __future__ import annotations
from .model import InpFile, Block, Stmt, Value
from dataclasses import dataclass, field
from typing import Optional
from collections import Counter


@dataclass
class DiffEntry:
    kind: str  # 'add' | 'remove' | 'modify' | 'same'
    location: str
    keyword: str
    old: object = None
    new: object = None
    line_old: int = 0
    line_new: int = 0

    def __str__(self):
        if self.kind == 'same':
            return f'  {self.location} {self.keyword}: same'
        if self.kind == 'add':
            return f'+ {self.location} {self.keyword}: {self.new!r}  (L{self.line_new})'
        if self.kind == 'remove':
            return f'- {self.location} {self.keyword}: {self.old!r}  (L{self.line_old})'
        return f'~ {self.location} {self.keyword}: {self.old!r} -> {self.new!r}  (L{self.line_old} -> L{self.line_new})'


@dataclass
class DiffReport:
    entries: list[DiffEntry] = field(default_factory=list)

    @property
    def changes(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.kind != 'same']

    def __len__(self):
        return len(self.changes)

    def __bool__(self):
        return bool(self.changes)

    def __str__(self):
        if not self.changes:
            return '(no changes)'
        return '\n'.join(str(e) for e in self.entries)

    def unified(self, a_path: str = 'a.inp', b_path: str = 'b.inp') -> str:
        lines = [f'--- {a_path}', f'+++ {b_path}']
        for e in self.changes:
            if e.kind == 'add':
                lines.append(f'@@ +{b_path}:{e.line_new} @@')
                lines.append(f'+ {e.location} {e.keyword} = {e.new!r}')
            elif e.kind == 'remove':
                lines.append(f'@@ -{a_path}:{e.line_old} @@')
                lines.append(f'- {e.location} {e.keyword} = {e.old!r}')
            elif e.kind == 'modify':
                lines.append(f'@@ -{a_path}:{e.line_old} +{b_path}:{e.line_new} @@')
                lines.append(f'- {e.location} {e.keyword} = {e.old!r}')
                lines.append(f'+ {e.location} {e.keyword} = {e.new!r}')
        return '\n'.join(lines)


def _stmt_key(s: Stmt) -> tuple:
    """用作配对的 key:keyword + 主行 values"""
    return (s.keyword, tuple(s.values_raw))


def _diff_stmts(a_stmts: list[Stmt], b_stmts: list[Stmt], loc_prefix: str) -> list[DiffEntry]:
    out = []
    # 按位置配对
    n = min(len(a_stmts), len(b_stmts))
    for i in range(n):
        a_s = a_stmts[i]
        b_s = b_stmts[i]
        if _stmt_key(a_s) == _stmt_key(b_s) and len(a_s.children) == len(b_s.children):
            # 完全相同
            out.append(DiffEntry('same', loc_prefix, a_s.keyword,
                                 old=a_s.values_typed, new=b_s.values_typed,
                                 line_old=a_s.line, line_new=b_s.line))
        else:
            # modify(包括 children 不同的复合语句,或 keyword 不同)
            old_repr = (a_s.values_typed, [c.values_typed for c in a_s.children])
            new_repr = (b_s.values_typed, [c.values_typed for c in b_s.children])
            # 同一位置 keyword 不同:把 a 的"旧"和 b 的"新"分别记录为 remove/add
            if a_s.keyword != b_s.keyword:
                out.append(DiffEntry('remove', loc_prefix, a_s.keyword,
                                     old=a_s.values_typed, new=None,
                                     line_old=a_s.line, line_new=0))
                out.append(DiffEntry('add', loc_prefix, b_s.keyword,
                                     old=None, new=b_s.values_typed,
                                     line_old=0, line_new=b_s.line))
            else:
                out.append(DiffEntry('modify', loc_prefix, a_s.keyword,
                                     old=old_repr, new=new_repr,
                                     line_old=a_s.line, line_new=b_s.line))
    # 剩余 a
    for i in range(n, len(a_stmts)):
        s = a_stmts[i]
        out.append(DiffEntry('remove', loc_prefix, s.keyword,
                             old=s.values_typed, new=None,
                             line_old=s.line, line_new=0))
    # 剩余 b
    for i in range(n, len(b_stmts)):
        s = b_stmts[i]
        out.append(DiffEntry('add', loc_prefix, s.keyword,
                             old=None, new=s.values_typed,
                             line_old=0, line_new=s.line))
    return out


def diff(a: InpFile, b: InpFile) -> DiffReport:
    out = []
    # 块配对:按出现顺序,同名索引对齐
    a_blocks = a.block_list
    b_blocks = b.block_list
    n = min(len(a_blocks), len(b_blocks))
    for i in range(n):
        ab = a_blocks[i]
        bb = b_blocks[i]
        if ab.name == bb.name:
            loc = f'block:{ab.name}[{i}]'
            out.extend(_diff_stmts(ab.statements, bb.statements, loc))
        else:
            # 块名不匹配:一个删一个加
            out.append(DiffEntry('remove', f'block:{ab.name}[{i}]', '<block>',
                                 old=ab.name, new=None,
                                 line_old=ab.begin_line, line_new=0))
            out.append(DiffEntry('add', f'block:{bb.name}[{i}]', '<block>',
                                 old=None, new=bb.name,
                                 line_old=0, line_new=bb.begin_line))
            # 简化:不递归比较内容
    for i in range(n, len(a_blocks)):
        ab = a_blocks[i]
        out.append(DiffEntry('remove', f'block:{ab.name}[{i}]', '<block>',
                             old=ab.name, new=None,
                             line_old=ab.begin_line, line_new=0))
    for i in range(n, len(b_blocks)):
        bb = b_blocks[i]
        out.append(DiffEntry('add', f'block:{bb.name}[{i}]', '<block>',
                             old=None, new=bb.name,
                             line_old=0, line_new=bb.begin_line))
    # 顶层语句
    out.extend(_diff_stmts(a.top_stmts, b.top_stmts, 'top'))
    return DiffReport(entries=out)
