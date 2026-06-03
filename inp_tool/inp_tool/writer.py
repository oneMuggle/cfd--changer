"""
mcfd.inp 序列化 v0.2

变更:
- 多行 values 复合 Stmt 正确输出(children 按行输出)
- comment_after 始终接回
- 重复同名块按出现顺序都输出
- 顶层复合语句(infsets + seq.# + values)正确输出
"""
from __future__ import annotations
from .model import InpFile, Block, Stmt, Value
from typing import TextIO


def _format_stmt(stmt: Stmt) -> str:
    """把一条 Stmt 格式化为原始行(不含行尾换行)"""
    parts = [stmt.keyword] + stmt.values_raw
    line = ' '.join(parts)
    if stmt.comment_after:
        line += stmt.comment_after
    return line


def _format_comments(comments: list[str]) -> list[str]:
    """把注释列表规范化为带 # 前缀的行"""
    out = []
    for c in comments:
        if c == '':
            out.append('')
        elif c.startswith('#'):
            out.append(c)
        else:
            out.append('# ' + c)
    return out


def _block_to_text(block: Block) -> str:
    lines = []
    # pre_comments
    lines.extend(_format_comments(block.pre_comments))
    lines.append(f'{block.name} begin')
    # 块内 statements
    for s in block.statements:
        lines.append(_format_stmt(s))
        # 复合语句的 children(后续多行 values)
        for child in s.children:
            lines.append(_format_stmt(child))
    # trailing_comments(end 前)
    lines.extend(_format_comments(block.trailing_comments))
    lines.append(f'{block.name} end')
    return '\n'.join(lines)


def to_text(inp: InpFile) -> str:
    """把 InpFile 序列化为文本(总是重构造,保证确定性)"""
    out = []
    # 头部
    out.extend(_format_comments(inp.header_comments))
    # 块 + 顶层语句:按出现顺序(line 升序)
    segments = []  # (line, kind, payload)
    for b in inp.block_list:
        segments.append((b.begin_line, 'block', b))
    for s in inp.top_stmts:
        segments.append((s.line, 'top', s))
    # 同一 line 的多个 top_stmts 保持原顺序
    segments.sort(key=lambda x: (x[0], 0 if x[1] == 'block' else 1))

    # 找到每个段前后需要插入的装饰注释(top_decor)
    decor_by_line = {}
    for ln, txt in inp.top_decor:
        decor_by_line.setdefault(ln, []).append(txt)

    last_line = 0
    for line_no, kind, payload in segments:
        # 输出该段之前的装饰
        for dln, dtxts in sorted(decor_by_line.items()):
            if last_line < dln < line_no:
                for dt in dtxts:
                    if dt == '':
                        out.append('')
                    elif dt.startswith('#'):
                        out.append(dtxts[0] if isinstance(dtxts, list) else dt)
                    else:
                        out.append('# ' + dt)
        last_line = line_no
        if kind == 'block':
            out.append(_block_to_text(payload))
        else:
            stmt = payload
            out.append(_format_stmt(stmt))
            for child in stmt.children:
                out.append(_format_stmt(child))
    # 尾部
    for tl in inp.tail_lines:
        out.append(tl)
    return '\n'.join(out)


def write(inp: InpFile, path: str):
    """写入文件(UTF-8, 不带 BOM, LF 换行)"""
    text = to_text(inp)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def write_bytes(inp: InpFile, path: str):
    """保留原始换行符(读时是什么就写什么)"""
    text = to_text(inp)
    with open(path, 'wb') as f:
        f.write(text.encode('utf-8'))
