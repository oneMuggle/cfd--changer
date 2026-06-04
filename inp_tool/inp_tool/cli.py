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


# ============================================================
# Shell 补全 (Phase D)
# ============================================================
_SUBCOMMANDS = ["parse", "get", "set", "diff", "info", "sweep", "completion"]


def _bash_completion() -> str:
    return r"""# bash completion for inp-tool
_inp_tool() {
    local cur prev cmds
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    cmds="parse get set diff info sweep completion --help --version"

    if [[ ${COMP_CWORD} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "${cmds}" -- "${cur}") )
        return 0
    fi

    # sweep 子命令的选项
    if [[ "${COMP_WORDS[1]}" == "sweep" ]]; then
        case "${cur}" in
            -*)
                COMPREPLY=( $(compgen -W "--alpha --beta --mach --t-inf --p-inf --out --manifest --dry-run --verbose -i" -- "${cur}") )
                return 0
                ;;
        esac
    fi
    return 0
}
complete -F _inp_tool inp-tool
"""


def _zsh_completion() -> str:
    return r"""#compdef inp-tool
# zsh completion for inp-tool
_inp_tool() {
    local -a subcommands
    subcommands=(parse:get get:set set:set diff:diff info:info sweep:batch-generate completion:shell-completion)
    if (( CURRENT == 2 )); then
        _describe 'subcommand' subcommands
        return
    fi
    case ${words[2]} in
        sweep)
            _arguments \
                '--alpha[alpha scan (deg)]:values:' \
                '--beta[beta scan (deg)]:values:' \
                '--mach[mach scan]:values:' \
                '--t-inf[freestream T K]:value:' \
                '--p-inf[freestream p Pa]:value:' \
                '--out[output dir]:dir:_files -/' \
                '--manifest[manifest path]:file:_files' \
                '--dry-run[dry run]' \
                '--verbose[verbose]' \
                '-i[interactive]'
            ;;
    esac
}
_inp_tool "$@"
"""


def _fish_completion() -> str:
    return r"""# fish completion for inp-tool
function __inp_tool_subcommands
    echo "parse\tparse mcfd.inp"
    echo "get\tget a value"
    echo "set\tset a value"
    echo "diff\tdiff two files"
    echo "info\tshow file overview"
    echo "sweep\tbatch generate cases"
    echo "completion\temit shell completion"
end

# 主命令 + 子命令
complete -c inp-tool -f -n "__fish_use_subcommand" -a "(__inp_tool_subcommands)"

# sweep 选项
complete -c inp-tool -n "__fish_seen_subcommand_from sweep" -l alpha -d "alpha scan (deg)"
complete -c inp-tool -n "__fish_seen_subcommand_from sweep" -l beta -d "beta scan (deg)"
complete -c inp-tool -n "__fish_seen_subcommand_from sweep" -l mach -d "mach scan"
complete -c inp-tool -n "__fish_seen_subcommand_from sweep" -l t-inf -d "freestream T K"
complete -c inp-tool -n "__fish_seen_subcommand_from sweep" -l p-inf -d "freestream p Pa"
complete -c inp-tool -n "__fish_seen_subcommand_from sweep" -l out -d "output dir" -r
complete -c inp-tool -n "__fish_seen_subcommand_from sweep" -l manifest -d "manifest path" -r
complete -c inp-tool -n "__fish_seen_subcommand_from sweep" -l dry-run -d "dry run"
complete -c inp-tool -n "__fish_seen_subcommand_from sweep" -l verbose -d "verbose"
complete -c inp-tool -n "__fish_seen_subcommand_from sweep" -s i -l interactive -d "interactive"
"""


def generate_completion(shell: str) -> str:
    """生成指定 shell 的补全脚本。"""
    s = shell.lower()
    if s == "bash":
        return _bash_completion()
    if s in ("zsh", "zsh-completions"):
        return _zsh_completion()
    if s == "fish":
        return _fish_completion()
    raise ValueError(
        f"unsupported shell: {shell!r} (supported: bash, zsh, fish)"
    )


def cmd_completion(args):
    shell = args.shell
    try:
        print(generate_completion(shell), end="")
        return 0
    except ValueError as e:
        print(f"completion: {e}", file=sys.stderr)
        return 2


# ============================================================
# 交互式 prompt 工具(Phase B)
# ============================================================
def _prompt(question, default=None, type_=str):
    """问用户一个问题,接受 default(回车=默认)。
    错输入(type_ 转换失败)自动重试,直到给合法值或回车。
    """
    while True:
        if default is None or default == "":
            suffix = ": "
        else:
            suffix = f" [{default}]: "
        try:
            raw = input(question + suffix)
        except EOFError:
            return default if default is not None else ""
        raw = raw.strip()
        if raw == "":
            return default
        if type_ is str:
            return raw
        try:
            return type_(raw)
        except (ValueError, TypeError):
            print(f"  无效输入: {raw!r},需要 {type_.__name__},请重试。")


def _confirm(question, default=False):
    """y/N 确认。default=False 时回车=N,True 时回车=Y。"""
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        try:
            raw = input(question + suffix)
        except EOFError:
            return default
        raw = raw.strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes", "是", "好"):
            return True
        if raw in ("n", "no", "否", "不"):
            return False
        print(f"  请输入 y 或 n(收到: {raw!r})")


def build_sweep_config_interactive():
    """
    走一遍 prompt 序列,返回 CaseSweep config dict。
    全部字段有 default,一路回车可走完。
    用户在 confirm 选 n 时返回 None(取消)。
    """
    print("=== sweep 交互式配置(回车=接受默认值)===\n")

    template = _prompt("模板 .inp 路径", default="")
    while not template or not os.path.isfile(template):
        if not template:
            print("  模板路径必填。")
        else:
            print(f"  文件不存在: {template}")
        template = _prompt("模板 .inp 路径", default="")
        if not template:
            return None

    output_dir = _prompt("输出目录", default="./sweep_cases")
    alpha_s = _prompt("攻角 alpha 扫描 (deg,逗号分隔)", default="0,4,8")
    beta_s = _prompt("侧滑角 beta 扫描 (deg,逗号分隔)", default="0")
    mach_s = _prompt("马赫 mach 扫描 (逗号分隔)", default="0.6,0.8")
    T_inf_s = _prompt("来流温度 T_inf K (单值或逗号列表)", default="288.15")
    p_inf_s = _prompt("来流压强 p_inf Pa (单值或逗号列表)", default="101325.0")
    naming = _prompt("命名模板 (空=auto)", default="")
    manifest = _prompt("manifest 路径 (空=不写)", default="")

    dry = _confirm("dry-run?(只打印不写盘)", default=False)
    if not _confirm("确认按上面配置生成?", default=True):
        print("[sweep] 已取消。")
        return None

    cfg: Dict[str, Any] = {
        "template": template,
        "output_dir": output_dir,
        "sweeps": {
            "alpha": _parse_csv_floats(alpha_s),
            "beta": _parse_csv_floats(beta_s),
            "mach": _parse_csv_floats(mach_s),
            "T_inf": _parse_csv_floats(T_inf_s),
            "p_inf": _parse_csv_floats(p_inf_s),
        },
        "dry_run": dry,
    }
    if naming:
        cfg["naming"] = naming
    if manifest:
        cfg["manifest"] = {"path": manifest}
    return cfg


def cmd_sweep(args):
    """
    inp-tool sweep <template.inp> [sweep.json]
    也支持:  --alpha 0,4,8  --beta -2,0,2  --mach 0.6,0.8  --t-inf 288.15  --p-inf 101325
    仅有 1 个位置参数且是 .json 时,直接按 config 调用。
    加 -i/--interactive 走 prompt 序列。
    """
    from .sweep import CaseSweep, generate

    # 交互式模式
    if getattr(args, "interactive", False):
        # TTY 检测:仅在 stdin 完全不存在时报错(piped stdin 在 CI/测试中是合法的)
        if sys.stdin is None:
            print("sweep -i: no stdin available.", file=sys.stderr)
            return 2
        cfg = build_sweep_config_interactive()
        if cfg is None:
            return 0  # 用户取消
        try:
            cs = CaseSweep.from_dict(cfg)
        except (KeyError, ValueError) as e:
            print(f"sweep: invalid config: {e}", file=sys.stderr)
            return 2
        if args.manifest:
            cs.manifest_path = args.manifest
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

    # 解析 first/config: 1 个参数按 config 处理;2 个参数按 template+config
    if args.config is None and args.first is not None and args.first.lower().endswith((".json", ".yaml", ".yml")):
        template = None
        config = args.first
    else:
        template = args.first
        config = args.config

    if config is not None:
        if not os.path.isfile(config):
            print(f"sweep: config not found: {config}", file=sys.stderr)
            return 2
        if config.lower().endswith((".yaml", ".yml")):
            try:
                cs = CaseSweep.from_yaml(config)
            except ImportError as e:
                print(f"sweep: {e}", file=sys.stderr)
                return 2
        else:
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
        if template is None:
            print(
                "sweep: no template given. Provide <template.inp> or a config, "
                "or use -i for interactive.",
                file=sys.stderr,
            )
            return 2
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
    sw.add_argument('first', nargs='?', help='模板 .inp 路径 / 或唯一参数:JSON config')
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
    sw.add_argument('-i', '--interactive', action='store_true', help='走 prompt 序列')
    sw.set_defaults(func=cmd_sweep)

    sc = sub.add_parser('completion', help='输出 shell 补全脚本 (bash/zsh/fish)')
    sc.add_argument('shell', choices=['bash', 'zsh', 'fish'], help='目标 shell')
    sc.set_defaults(func=cmd_completion)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
