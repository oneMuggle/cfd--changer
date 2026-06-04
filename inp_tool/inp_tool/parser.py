"""
mcfd.inp 解析器 v0.2

变更:
- 识别多行 values 模式(seq.# + 后续 values 行合并为复合 Stmt)
- 重复同名块都保留(在 block_list 里)
- 行尾注释(comment_after)始终保留
- 顶层复合语句也支持(顶层有 infsets + seq.# + values)
"""
from __future__ import annotations
from .model import InpFile, Block, Stmt, Value
from typing import Iterator
import re


_COMMENT_RE = re.compile(r'\s+#.*$')


def _split_comment(line: str) -> tuple[str, str]:
    """分离行尾注释,返回 (no_comment, comment_with_leading_space)"""
    # 找空白后接 # 的位置
    for i in range(len(line) - 1):
        if line[i] in ' \t' and line[i+1] == '#':
            return line[:i], line[i:]
    return line, ''


def _tokenize_line(line: str) -> tuple[str, list[str], str]:
    """把一行分成 (keyword, [values...], tail_comment_with_space)"""
    stripped, comment = _split_comment(line)
    s = stripped.strip()
    if not s:
        return '', [], comment
    parts = s.split()
    kw = parts[0]
    vals = parts[1:]
    return kw, vals, comment


def _is_block_marker(s: str) -> tuple[str, str] | None:
    parts = s.split()
    if len(parts) == 2 and parts[1] in ('begin', 'end'):
        return parts[0], parts[1]
    return None


def _make_stmt(kw: str, raw_vals: list[str], line_no: int, raw: str, comment: str,
               leading_ws: str = '', trailing_ws: str = '') -> Stmt:
    vals = [Value(raw=v) for v in raw_vals]
    return Stmt(
        keyword=kw, values=vals, line=line_no, raw=raw, comment_after=comment,
        raw_with_ws=raw,
        leading_ws=leading_ws,
        trailing_ws=trailing_ws,
    )


# === 复合语句识别 ===
def _is_seq_header(kw: str) -> bool:
    """seq.# / seq# / seq — info set 的序号头"""
    return kw.startswith('seq')


def _is_values_line(kw: str) -> bool:
    return kw == 'values'


def parse(text: str, path: str = '') -> InpFile:
    """
    解析 .inp 文本 → InpFile
    """
    inp = InpFile(path=path)
    lines = text.split('\n')

    # 状态机
    # 'header' : 起始
    # 'top'    : 顶层非块区
    # 'block:NAME' : 在 NAME 块内
    state = 'header'
    current_block: Block | None = None
    pending_comments: list[str] = []  # 累积注释(头部/块前)

    # 复合语句累积:顶层 or 块内,上一行是不是复合头(seq.#)
    last_composite: Stmt | None = None  # 当前正在累积的复合语句

    def flush_composite():
        nonlocal last_composite
        last_composite = None

    for i, raw_line in enumerate(lines, 1):
        stripped, comment = _split_comment(raw_line)
        s = stripped.strip()
        # 提取 leading_ws / trailing_ws(preserve_format 用)
        leading_ws = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        # trailing_ws 是 stripped 后面到 comment 之前的空白
        tail_start = len(stripped)
        tail_end = len(raw_line) - (len(comment) if comment else 0)
        trailing_ws = raw_line[tail_start:tail_end] if tail_end > tail_start else ''
        # 提取 leading_ws / trailing_ws(preserve_format 用)
        leading_ws = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        # trailing_ws 是 stripped 后面到 comment 之前的空白
        tail_start = len(stripped)
        tail_end = len(raw_line) - (len(comment) if comment else 0)
        trailing_ws = raw_line[tail_start:tail_end] if tail_end > tail_start else ''

        # 块标记
        m = _is_block_marker(s)
        if m:
            name, kind = m
            # 切块前先 flush 当前复合语句
            flush_composite()
            if kind == 'begin':
                if state == 'header':
                    inp.header_comments = pending_comments
                    pending_comments = []
                current_block = Block(name=name, begin_line=i, end_line=0)
                current_block.pre_comments = pending_comments
                pending_comments = []
                state = f'block:{name}'
            else:  # 'end'
                if state == f'block:{name}' and current_block is not None:
                    current_block.end_line = i
                    inp.block_list.append(current_block)
                    current_block = None
                    state = 'top'
            continue

        # 空行
        if not s:
            if state == 'header':
                pending_comments.append('')
            elif state == 'top':
                # 空行可能是复合语句间的分隔,flush
                flush_composite()
                inp.top_decor.append((i, ''))
            elif state.startswith('block:') and current_block is not None:
                # 块内空行:flush 复合语句
                flush_composite()
                # 记录到 trailing_comments(将在 end 前输出)
                current_block.trailing_comments.append('')
            continue

        # 注释行(整行)
        if comment and not s:
            if state == 'header':
                pending_comments.append(comment.lstrip())
            elif state == 'top':
                inp.top_decor.append((i, comment.lstrip()))
            elif state.startswith('block:') and current_block is not None:
                current_block.trailing_comments.append(comment.lstrip())
            continue

        # 纯注释行(stripped 以 # 开头)
        if s.startswith('#'):
            if state == 'header':
                pending_comments.append(s)
            elif state == 'top':
                inp.top_decor.append((i, s))
            elif state.startswith('block:') and current_block is not None:
                current_block.trailing_comments.append(s)
            continue

        # 普通语句
        kw, vals, _ = _tokenize_line(s)
        if not kw:
            continue
        stmt = _make_stmt(kw, vals, i, raw_line, comment,
                          leading_ws=leading_ws, trailing_ws=trailing_ws)

        # 复合语句累积逻辑
        if _is_seq_header(kw):
            # 新的复合头
            flush_composite()
            last_composite = stmt
            if state == 'header':
                inp.header_comments = pending_comments
                pending_comments = []
                inp.top_stmts.append(stmt)
                state = 'top'
            elif state == 'top':
                inp.top_stmts.append(stmt)
            elif state.startswith('block:') and current_block is not None:
                current_block.statements.append(stmt)
        elif _is_values_line(kw) and last_composite is not None:
            # values 行,且前一个是复合头:加入 children
            last_composite.children.append(stmt)
        else:
            # 普通语句
            flush_composite()
            if state == 'header':
                inp.header_comments = pending_comments
                pending_comments = []
                inp.top_stmts.append(stmt)
                state = 'top'
            elif state == 'top':
                inp.top_stmts.append(stmt)
            elif state.startswith('block:') and current_block is not None:
                current_block.statements.append(stmt)

    # 收尾
    if state == 'header':
        inp.header_comments = pending_comments
    flush_composite()
    if state.startswith('block:') and current_block is not None:
        # 块未闭合,容错
        current_block.end_line = len(lines)
        inp.block_list.append(current_block)

    return inp


def parse_file(path: str) -> InpFile:
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    return parse(text, path=path)
