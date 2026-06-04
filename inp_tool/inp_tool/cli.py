"""
mcfd.inp CLI v0.2
"""
from __future__ import annotations
import argparse
import os
import sys
from typing import Any, Dict
from . import __version__
from .parser import parse_file
from .writer import write as write_inp
from .diff import diff
from .model import infer_type


def cmd_parse(args):
    inp = parse_file(args.file)
    print(f'文件: {inp.path}')
    print(f'头部注释: {len(inp.header_comments)} 行')
    print(f'块: {len(inp.block_list)} 个')
    for i, b in enumerate(inp.block_list):
        print(f'  [{i}] {b.name}  L{b.begin_line}-{b.end_line}  ({len(b.statements)} stmts)')
    print(f'顶层语句: {len(inp.top_stmts)} 条')
    if args.block is not None:
        b = inp.get_block(args.block, args.block_idx) if isinstance(args.block, str) else None
        if args.block_idx is not None and isinstance(args.block, int):
            b = inp.block_list[args.block_idx] if args.block_idx < len(inp.block_list) else None
        elif args.block:
            b = inp.get_block(args.block, args.block_idx or 0)
        if b is None:
            print(f'  ! 块 {args.block!r} (idx={args.block_idx}) 不存在')
            return 1
        print(f'\n=== {b.name} (L{b.begin_line}-{b.end_line}, {len(b.statements)} stmts) ===')
        stmts_to_show = b.statements if args.full else b.statements[:30]
        for s in stmts_to_show:
            extra = f' + {len(s.children)} child lines' if s.children else ''
            print(f'  L{s.line:4d} {s.keyword} {" ".join(s.values_raw)}{extra}')
            for c in s.children:
                print(f'    L{c.line:4d} {c.keyword} {" ".join(c.values_raw)}')
        if not args.full and len(b.statements) > 30:
            print(f'  ... +{len(b.statements)-30} 条')
    if args.top:
        print(f'\n=== 顶层语句 ===')
        for s in inp.top_stmts:
            extra = f' + {len(s.children)} child lines' if s.children else ''
            print(f'  L{s.line:4d} {s.keyword} {" ".join(s.values_raw)}{extra}')
    return 0


def cmd_get(args):
    inp = parse_file(args.file)
    if args.block:
        b = inp.get_block(args.block, args.block_idx or 0)
        if b is None:
            print(f'块 {args.block!r}[{args.block_idx or 0}] 不存在', file=sys.stderr)
            return 1
        v = b.get_value(args.key)
        if v is None:
            print(f'关键字 {args.key!r} 在块 {args.block!r}[{args.block_idx or 0}] 中不存在', file=sys.stderr)
            return 1
        print(f'{args.block}[{args.block_idx or 0}].{args.key} = {v.typed!r}  (raw: {v.raw!r})')
    else:
        # 顶层 + 所有块
        for s in inp.top_stmts:
            if s.keyword == args.key and s.values:
                v = s.values[0]
                print(f'top.{args.key} = {v.typed!r}  (raw: {v.raw!r})')
                return 0
        for b in inp.block_list:
            v = b.get_value(args.key)
            if v is not None:
                idx = inp.block_list.index(b)
                print(f'{b.name}[{idx}].{args.key} = {v.typed!r}  (raw: {v.raw!r})')
                return 0
        print(f'关键字 {args.key!r} 不存在', file=sys.stderr)
        return 1
    return 0


def cmd_set(args):
    inp = parse_file(args.file)
    typed = infer_type(args.value)
    idx = args.block_idx or 0
    b = inp.get_block(args.block, idx)
    if b is None:
        print(f'块 {args.block!r}[{idx}] 不存在', file=sys.stderr)
        return 1
    if not b.set(args.key, typed):
        print(f'关键字 {args.key!r} 在块 {args.block!r}[{idx}] 中不存在', file=sys.stderr)
        if not args.force:
            return 1
        b.append(args.key, typed)
        print(f'  (appended new entry {args.key} = {typed!r})', file=sys.stderr)
    out_path = args.output or args.file
    write_inp(inp, out_path)
    print(f'已写入: {out_path}')
    print(f'  {args.block}[{idx}].{args.key} = {typed!r}')
    return 0


def cmd_diff(args):
    a = parse_file(args.a)
    b = parse_file(args.b)
    r = diff(a, b)
    if args.unified:
        print(r.unified(args.a, args.b))
    else:
        print(f'=== {args.a} -> {args.b} ===')
        print(f'差异条数: {len(r)}')
        for e in r.changes:
            print(f'  {e}')
    return 0


def cmd_info(args):
    inp = parse_file(args.file)
    print(f'文件: {inp.path}')
    print(f'头部注释行: {len(inp.header_comments)}')
    print(f'顶层语句: {len(inp.top_stmts)}')
    print(f'\n块列表:')
    from collections import Counter
    for i, b in enumerate(inp.block_list):
        kw_counter = Counter(s.keyword for s in b.statements)
        print(f'  [{i:2d}] {b.name:15s} L{b.begin_line:4d}-{b.end_line:4d}  '
              f'{len(b.statements):4d} stmts  {len(kw_counter):3d} unique keys')
    return 0


def _parse_csv_floats(s: str):
    """把 '0,4,8' 或 '0 4 8' 解析为 float 列表"""
    parts = [p for p in s.replace(",", " ").split() if p]
    return [float(p) for p in parts]


def cmd_sweep(args):
    """
    inp-tool sweep <template.inp> [sweep.json]
    也支持:  --alpha 0,4,8  --beta -2,0,2  --mach 0.6,0.8  --t-inf 288.15  --p-inf 101325
    仅有 1 个位置参数且是 .json 时,直接按 config 调用。
    """
    from .sweep import CaseSweep, generate

    # 解析 first/config: 1 个参数按 config 处理;2 个参数按 template+config
    if args.config is None and args.first.lower().endswith(".json"):
        template = None
        config = args.first
    else:
        template = args.first
        config = args.config

    if config is not None:
        if not os.path.isfile(config):
            print(f"sweep: config not found: {config}", file=sys.stderr)
            return 2
        try:
            cs = CaseSweep.from_json(config)
        except (KeyError, ValueError) as e:
            print(f"sweep: invalid config: {e}", file=sys.stderr)
            return 2
        if args.out:
            cs.output_dir = args.out
        if args.manifest:
            cs.manifest_path = args.manifest
    else:
        # template 模式
        if not os.path.isfile(template):
            print(f"sweep: template not found: {template}", file=sys.stderr)
            return 2
        sweeps: Dict[str, Any] = {}
        if args.alpha is not None:
            sweeps["alpha"] = _parse_csv_floats(args.alpha)
        if args.beta is not None:
            sweeps["beta"] = _parse_csv_floats(args.beta)
        if args.mach is not None:
            sweeps["mach"] = _parse_csv_floats(args.mach)
        if args.t_inf is not None:
            sweeps["T_inf"] = _parse_csv_floats(args.t_inf)
        if args.p_inf is not None:
            sweeps["p_inf"] = _parse_csv_floats(args.p_inf)

        if not sweeps:
            print(
                "sweep: no sweep axes provided. Use a JSON config or "
                "--alpha/--beta/--mach/--t-inf/--p-inf.",
                file=sys.stderr,
            )
            return 2

        out_dir = args.out or "."
        cfg: Dict[str, Any] = {
            "template": template,
            "output_dir": out_dir,
            "sweeps": sweeps,
        }
        if args.manifest:
            cfg["manifest"] = {"path": args.manifest}

        try:
            cs = CaseSweep.from_dict(cfg)
        except (KeyError, ValueError) as e:
            print(f"sweep: invalid config: {e}", file=sys.stderr)
            return 2

    if args.dry_run:
        print("[sweep] DRY RUN: no files will be written")

    report = generate(cs, dry_run=args.dry_run)

    print(f"[sweep] generated {report.total} cases -> {cs.output_dir}")
    if report.total <= 20 or args.verbose:
        for c in report.cases:
            params_str = " ".join(f"{k}={v}" for k, v in c.params.items())
            print(f"  - {c.case_id}  ({params_str})")
    if cs.manifest_path and not args.dry_run:
        print(f"[sweep] manifest -> {cs.manifest_path}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(
        prog='inp',
        description='mcfd.inp 解析、修改、diff 工具 v0.2',
    )
    p.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    sub = p.add_subparsers(dest='cmd', required=True)

    sp = sub.add_parser('parse', help='解析并显示结构')
    sp.add_argument('file')
    sp.add_argument('-b', '--block', help='显示某个块(按名)')
    sp.add_argument('-i', '--block-idx', type=int, default=0, help='同名块索引(0-based)')
    sp.add_argument('-t', '--top', action='store_true', help='显示顶层语句')
    sp.add_argument('-f', '--full', action='store_true', help='完整列出')
    sp.set_defaults(func=cmd_parse)

    sg = sub.add_parser('get', help='取一个值')
    sg.add_argument('file')
    sg.add_argument('key')
    sg.add_argument('-b', '--block', help='块名')
    sg.add_argument('-i', '--block-idx', type=int, default=0)
    sg.set_defaults(func=cmd_get)

    ss = sub.add_parser('set', help='改一个值并写回')
    ss.add_argument('file')
    ss.add_argument('block')
    ss.add_argument('key')
    ss.add_argument('value')
    ss.add_argument('-i', '--block-idx', type=int, default=0)
    ss.add_argument('-o', '--output')
    ss.add_argument('-f', '--force', action='store_true', help='不存在时 append')
    ss.set_defaults(func=cmd_set)

    sd = sub.add_parser('diff', help='两个 .inp 的 diff')
    sd.add_argument('a')
    sd.add_argument('b')
    sd.add_argument('-u', '--unified', action='store_true')
    sd.set_defaults(func=cmd_diff)

    si = sub.add_parser('info', help='文件概览')
    si.add_argument('file')
    si.set_defaults(func=cmd_info)

    # === sweep 子命令 ===
    sw = sub.add_parser(
        'sweep',
        help='基于样例批量生成 mcfd.inp 算例(扫描攻角/侧滑角/来流等)',
    )
    sw.add_argument('first', help='模板 .inp 路径 / 或唯一参数:JSON config')
    sw.add_argument('config', nargs='?', help='可选: JSON 配置文件')
    sw.add_argument('--alpha', help='攻角扫描(逗号分隔,deg)')
    sw.add_argument('--beta', help='侧滑角扫描(逗号分隔,deg)')
    sw.add_argument('--mach', help='马赫数扫描(逗号分隔)')
    sw.add_argument('--t-inf', dest='t_inf', help='来流温度 K(单值或逗号列表)')
    sw.add_argument('--p-inf', dest='p_inf', help='来流压强 Pa(单值或逗号列表)')
    sw.add_argument('--out', help='输出目录(覆盖 config)')
    sw.add_argument('--manifest', help='manifest.json 路径(覆盖 config)')
    sw.add_argument('--dry-run', action='store_true', help='只打印不写盘')
    sw.add_argument('-v', '--verbose', action='store_true', help='列出所有 case')
    sw.set_defaults(func=cmd_sweep)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
