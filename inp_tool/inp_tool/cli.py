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
    # v0.9.1: --detect 输出方程系统/湍流模型/气体类型报告
    if getattr(args, 'detect', False):
        from .equations import detect_equations
        rep = detect_equations(inp)
        print(f'\n方程系统检测 (detect_equations):')
        print(f'  能量模型     : {rep.energy.value:12s}'
              f' (physics.tnoneq_numeqns)')
        print(f'  湍流模型     : {rep.turbulence.value:20s}'
              f' (eqnset_define v4={rep.ntrbst_family}, v5={rep.ntrbst_code})')
        print(f'  气体类型     : {rep.gas.value:12s}'
              f' (eqnset_define v6={rep.gas_code})')
        print(f'  物种数 (infsets) : {rep.n_species}')
        if rep.gasnam:
            print(f'  physics.gasnam   : {rep.gasnam}  (仅参考,不用于判别)')
        if rep.notes:
            print(f'\n  一致性告警:')
            for n in rep.notes:
                print(f'    ⚠ {n}')
    return 0


def _parse_csv_floats(s: str):
    """把 '0,4,8' 或 '0 4 8' 解析为 float 列表"""
    parts = [p for p in s.replace(",", " ").split() if p]
    return [float(p) for p in parts]


# ============================================================
# Shell 补全 (Phase D)
# ============================================================
_SUBCOMMANDS = ["parse", "get", "set", "diff", "info", "sweep", "completion", "shell"]


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
# 交互式 REPL (Phase B: 委托给 repl.main)
# ============================================================
def cmd_shell(args):
    """inp-tool shell [files...] — 启动交互式 REPL。

    可选地预加载 0 或多个 .inp 文件(自动按 basename 起 alias)。
    """
    from .repl import main as repl_main
    return repl_main(args.files)


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

    v0.8.2 起:source_dir 必填(template 自动取 source_dir/mcfd.inp)。
    """
    print("=== sweep 交互式配置(回车=接受默认值)===\n")
    print("  v0.8.2 起:扁平模式已从交互式 prompt 移除,必须指定基础算例目录(整目录生成)。\n")

    # v0.8.2:先问 source_dir(template 自动取其下 mcfd.inp)
    source_dir = _prompt("基础算例目录 source_dir (必填,完整算例根目录)", default="")
    while not source_dir or not os.path.isdir(source_dir):
        if not source_dir:
            print("  错误:基础算例目录为必填项。")
        else:
            print(f"  目录不存在: {source_dir}")
        source_dir = _prompt("基础算例目录 source_dir (必填)", default="")
        if not source_dir:
            return None
    template = os.path.join(source_dir, "mcfd.inp")
    if not os.path.isfile(template):
        print(f"  错误:目录下找不到 mcfd.inp: {template}")
        return None

    copy_strategy = _prompt(
        "复制策略 copy/hardlink/symlink (默认 hardlink)",
        default="hardlink",
    )

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
        "source_dir": source_dir,
        "copy_strategy": copy_strategy,
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
        # v0.8.0:CLI flag 也应用到 interactive 模式
        _apply_v080_overrides(cs, args)
        # v0.10.0:CLI flag → cs.equation_switches 覆盖
        _apply_v100_equation_overrides(cs, args)
        if args.dry_run:
            print("[sweep] DRY RUN: no files will be written")
        report = generate(cs, dry_run=args.dry_run, force=getattr(args, "force", False))
        print(f"[sweep] generated {report.total} cases -> {cs.output_dir}")
        if report.total <= 20 or args.verbose:
            for c in report.cases:
                params_str = " ".join(f"{k}={v}" for k, v in c.params.items())
                print(f"  - {c.case_id}  ({params_str})")
        if cs.manifest_path and not args.dry_run:
            print(f"[sweep] manifest -> {cs.manifest_path}")
        return 0

    # 解析 first/config: 1 个参数按 config 处理;2 个参数按 template+config
    if args.config is None and args.first is not None and args.first.lower().endswith((".json", ".yaml", ".yml", ".csv")):
        template = None
        config = args.first
    else:
        template = args.first
        config = args.config

    if config is not None:
        if not os.path.isfile(config):
            print(f"sweep: config not found: {config}", file=sys.stderr)
            return 2
        if config.lower().endswith(".csv"):
            # PR #1:CSV 模式,需要 --template 提供模板路径
            csv_template = getattr(args, "template", None)
            if not csv_template:
                print(
                    "sweep: CSV mode requires --template <template.inp>",
                    file=sys.stderr,
                )
                return 2
            if not os.path.isfile(csv_template):
                print(
                    f"sweep: template not found: {csv_template}",
                    file=sys.stderr,
                )
                return 2
            # 默认输出目录 = CSV 文件所在目录的 ./sweep_cases
            csv_out = args.out or os.path.join(
                os.path.dirname(os.path.abspath(config)) or ".",
                "sweep_cases",
            )
            try:
                cs = CaseSweep.from_csv(
                    config,
                    template=csv_template,
                    output_dir=csv_out,
                    naming=getattr(args, "naming", None),
                    manifest_path=args.manifest,
                )
            except (KeyError, ValueError, FileNotFoundError) as e:
                print(f"sweep: invalid CSV: {e}", file=sys.stderr)
                return 2
        elif config.lower().endswith((".yaml", ".yml")):
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

    # v0.8.0:应用 CLI 覆盖到 cs(整算例目录模式)
    _apply_v080_overrides(cs, args)

    # v0.10.0:应用方程改写 CLI 覆盖(开关/严格度)
    _apply_v100_equation_overrides(cs, args)

    # v0.8.2:wizard 已强制 per_dir,CLI 不传 --source-dir 视为遗留用法,打 deprecation 提示
    if not getattr(args, "source_dir", None) and not cs.source_dir:
        print(
            "[DEPRECATION] 不传 --source-dir 将只生成 mcfd.inp,跑不动。"
            "推荐使用 --source-dir <基础算例目录>(wizard v0.8.2+ 已强制要求)。",
            file=sys.stderr,
        )

    if args.dry_run:
        print("[sweep] DRY RUN: no files will be written")

    report = generate(cs, dry_run=args.dry_run, force=getattr(args, "force", False))

    print(f"[sweep] generated {report.total} cases -> {cs.output_dir}")
    if report.total <= 20 or args.verbose:
        for c in report.cases:
            params_str = " ".join(f"{k}={v}" for k, v in c.params.items())
            print(f"  - {c.case_id}  ({params_str})")
    if cs.manifest_path and not args.dry_run:
        print(f"[sweep] manifest -> {cs.manifest_path}")
    return 0


def _apply_v080_overrides(cs, args):
    """v0.8.0:把 CLI 传入的 --source-dir/--copy-strategy/--exclude 应用到 cs。

    优先级:CLI flag > config 文件 > 默认值
    --exclude: 累加到 cs.exclude(不替换默认),用户用 --no-default-exclude 清空
    """
    if getattr(args, "source_dir", None):
        cs.source_dir = args.source_dir
    if getattr(args, "copy_strategy", None):
        from .sweep import CopyStrategy
        cs.copy_strategy = CopyStrategy(args.copy_strategy)
    excl = getattr(args, "exclude", None)
    if excl:
        # 累加到现有规则(保留默认),避免用户写 --exclude foo 时静默丢 *.bak 等
        cs.exclude = list(cs.exclude) + list(excl)
    # v0.9.0:pbs 注入
    from .pbs import PbsConfig
    pbs_enabled = getattr(args, "pbs", True)
    pbs_naming = getattr(args, "pbs_naming", "") or ""
    if pbs_enabled or pbs_naming:
        cs.pbs = PbsConfig(enabled=pbs_enabled, naming=pbs_naming)


def _apply_v100_equation_overrides(cs, args):
    """v0.10.0:把 CLI 传入的 --strict-equations / --no-switch-* 应用到 cs。

    优先级:CLI flag > config 文件 > 默认值
    --no-switch-*:默认切(True),传 flag 后变 False
    --strict-equations:目前仅占位(后续 v0.10.0 启用 raise-on-residual)
    """
    if cs is None:
        return  # 上游已报错,这里不重复 raise
    if getattr(args, "no_switch_turbulence", False):
        cs.equation_switches.turbulence = False
    if getattr(args, "no_switch_energy", False):
        cs.equation_switches.energy = False
    if getattr(args, "no_switch_gas", False):
        cs.equation_switches.gas = False
    # --strict-equations 当前仅占位;后续 v0.10.0 子任务在 generate() 末尾
    # 把残留字段警告升为 EquationRewriteError。当前不消费此 flag,只是注册。
    _ = getattr(args, "strict_equations", False)


# ============================================================================
# v0.14.0:cluster 子命令(PBS 集群配置 / 探测 / 测试)
# ============================================================================

def cmd_cluster_probe(args):
    """``inp-tool cluster probe`` — ssh 远端探测调度器类型。"""
    from .cluster import ClusterConfig, SshClusterClient

    cfg = ClusterConfig.load()
    if args.host:
        cfg.host = args.host
    if args.user:
        cfg.user = args.user
    if args.ssh_key:
        cfg.ssh_key = args.ssh_key
        cfg.auth_method = "ssh-key"
    if args.port:
        cfg.port = args.port

    print(f"Probing {cfg.user}@{cfg.host}:{cfg.port} ...")
    try:
        client = SshClusterClient(cfg)
        info = client.probe()
    except Exception as e:
        print(f"❌ 探测失败: {e}", file=sys.stderr)
        return 1

    # 探测成功 → 自动写回 cluster.json
    cfg.detected_scheduler = info.scheduler.value
    cfg.save()
    print(f"✅ scheduler: {info.scheduler.value}")
    print(f"   queues: {', '.join(info.queues) or '(未列出)'}")
    print(f"   user: {info.user}")
    print(f"   配置已写回: {cfg._config_path()}")
    return 0


def cmd_cluster_config(args):
    """``inp-tool cluster config`` — 读/写 cluster.json。"""
    from .cluster import ClusterConfig

    cfg_path = ClusterConfig._config_path()
    cfg = ClusterConfig.load()

    if args.path:
        print(cfg_path)
        return 0

    if args.set_kv:
        # --set key=value 多次
        for kv in args.set_kv:
            if "=" not in kv:
                print(f"❌ --set 格式错误: {kv!r} (期望 KEY=VALUE)", file=sys.stderr)
                return 1
            k, v = kv.split("=", 1)
            k = k.strip()
            if not hasattr(cfg, k):
                print(f"❌ 未知字段: {k!r}", file=sys.stderr)
                return 1
            # 按字段类型转换(int / bool / list / str)
            from dataclasses import fields
            field_types = {f.name: f.type for f in fields(cfg)}
            type_str = str(field_types.get(k, "str"))
            if "int" in type_str:
                v = int(v)
            elif "bool" in type_str:
                v = v.lower() in ("true", "1", "yes", "y")
            elif k == "available_queues" and v.startswith("["):
                import json as _json
                v = _json.loads(v)
            setattr(cfg, k, v)
        cfg.save()
        print(f"✅ 已写入 {cfg_path}")
        return 0

    if args.show or not (args.init or args.set_kv):
        import json as _json
        print(_json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if args.init:
        # 简化:不真交互,提示用户用 --set
        print("用 --set KEY=VALUE 配置字段,例:")
        print("  inp-tool cluster config --set host=10.10.10.251")
        print("  inp-tool cluster config --set ssh_key=C:/Users/me/.ssh/id_rsa")
        print("  inp-tool cluster config --set default_queue=q01")
        print(f"配置文件路径: {cfg_path}")
        return 0

    return 0


def cmd_cluster_test(args):
    """``inp-tool cluster test`` — ssh + 调度器识别跑通测试。"""
    from .cluster import ClusterConfig, SshClusterClient
    from pathlib import Path

    cfg = ClusterConfig.load()
    if args.host:
        cfg.host = args.host
    if args.user:
        cfg.user = args.user
    if args.ssh_key:
        cfg.ssh_key = args.ssh_key

    print(f"Testing SSH to {cfg.user}@{cfg.host}:{cfg.port} ...")
    try:
        client = SshClusterClient(cfg)
        info = client.probe()
    except Exception as e:
        print(f"❌ SSH 失败: {e}", file=sys.stderr)
        return 1

    print(f"✅ scheduler: {info.scheduler.value}")
    print(f"   queues: {', '.join(info.queues) or '(未列出)'}")

    # 检查 ssh_key 文件存在(若指定)
    if cfg.ssh_key and not Path(cfg.ssh_key).is_file():
        print(f"⚠️ ssh_key 不存在: {cfg.ssh_key}", file=sys.stderr)
        return 1
    if cfg.ssh_key:
        print(f"   ssh_key: {cfg.ssh_key} (存在)")

    # 写回 cluster.json
    cfg.detected_scheduler = info.scheduler.value
    cfg.save()
    print(f"✅ 配置已写回: {cfg._config_path()}")
    print("(本次不真提交,只验证连接 + 调度器识别;用 'inp-tool pbs submit' 提交)")
    return 0


# ============================================================================
# v0.14.0:pbs submit 子命令(Phase 2)
# ============================================================================

def cmd_pbs_submit(args):
    """``inp-tool pbs submit`` — 批量提交 sweep_report.json 中所有 case。"""
    from pathlib import Path
    from .cluster import ClusterConfig, SshClusterClient, LocalDryRunClient
    from .batch import submit_sweep

    # 1. 解析 sweep_report 路径
    sweep_path = args.sweep_report
    if not sweep_path:
        print("❌ 缺少 sweep_report.json 路径(用法: inp-tool pbs submit <sweep_report.json>)", file=sys.stderr)
        return 1
    sweep_p = Path(sweep_path)
    if args.from_sweep_dir or sweep_p.is_dir():
        # 自动找 manifest.json
        if sweep_p.is_dir():
            manifest = sweep_p / "manifest.json"
        else:
            manifest = sweep_p / "manifest.json"
        if not manifest.is_file():
            print(f"❌ {sweep_p} 下找不到 manifest.json", file=sys.stderr)
            return 1
        sweep_p = manifest
    if not sweep_p.is_file():
        print(f"❌ sweep_report.json 不存在: {sweep_p}", file=sys.stderr)
        return 1

    # 2. 加载 cluster config + 覆盖
    cfg = ClusterConfig.load()
    if args.host:
        cfg.host = args.host
    if args.user:
        cfg.user = args.user
    if args.ssh_key:
        cfg.ssh_key = args.ssh_key
        cfg.auth_method = "ssh-key"
    if args.max_concurrent_jobs is not None:
        cfg.max_concurrent_jobs = args.max_concurrent_jobs

    # 3. dry-run 用 LocalDryRunClient,否则 SshClusterClient
    if args.dry_run:
        print("🏃 dry-run 模式:不真提交,只记录命令")
        client = LocalDryRunClient(cfg)
    else:
        client = SshClusterClient(cfg)

    # 4. pbs_overrides
    pbs_overrides: Dict[str, str] = {}
    if args.queue:
        pbs_overrides["-q"] = args.queue
    if args.walltime:
        pbs_overrides["-l walltime"] = args.walltime
    if args.nodes or args.ppn:
        nodes = args.nodes or cfg.default_nodes
        ppn = args.ppn or cfg.default_ppn
        pbs_overrides["-l nodes"] = f"{nodes}:ppn={ppn}"

    # 5. submit
    print(f"提交 {sweep_p} 到 {cfg.user}@{cfg.host} ...")
    result = submit_sweep(
        sweep_p,
        client,
        dry_run=args.dry_run,
        limit=args.limit,
        skip_existing=args.skip_existing,
        pbs_overrides=pbs_overrides or None,
        respect_concurrency=args.respect_concurrency,
    )

    # 6. 报告
    print(f"\n📊 提交结果(用时 {result.elapsed_seconds:.1f}s):")
    print(f"   ✅ 成功: {len(result.submissions)}")
    for s in result.submissions:
        print(f"      {s.case_name} → job_id={s.job_id} (queue={s.queue})")
    print(f"   ⏭ 跳过: {len(result.skipped)}")
    for sk in result.skipped[:5]:  # 最多 5 条
        print(f"      {sk}")
    if len(result.skipped) > 5:
        print(f"      ... ({len(result.skipped) - 5} more)")
    print(f"   ❌ 失败: {len(result.failed)}")
    for case_dir, err in result.failed:
        print(f"      {case_dir}: {err}")

    if result.failed:
        return 1
    return 0


def cmd_pbs_status(args):
    """``inp-tool pbs status`` — 查询 sweep_report.json 中所有 case 的 PBS 状态。"""
    import json as _json
    import time as _time
    from pathlib import Path
    from .cluster import ClusterConfig, SshClusterClient
    from .batch import query_sweep_status, summarize_states, format_status_table

    # 1. 解析 sweep_report 路径(同 submit)
    sweep_path = args.sweep_report
    if not sweep_path:
        print("❌ 缺少 sweep_report.json 路径(用法: inp-tool pbs status <sweep_report.json>)", file=sys.stderr)
        return 1
    sweep_p = Path(sweep_path)
    if args.from_sweep_dir or sweep_p.is_dir():
        if sweep_p.is_dir():
            manifest = sweep_p / "manifest.json"
        else:
            manifest = sweep_p / "manifest.json"
        if not manifest.is_file():
            print(f"❌ {sweep_p} 下找不到 manifest.json", file=sys.stderr)
            return 1
        sweep_p = manifest
    if not sweep_p.is_file():
        print(f"❌ sweep_report.json 不存在: {sweep_p}", file=sys.stderr)
        return 1

    # 2. 加载 cluster config + 覆盖
    cfg = ClusterConfig.load()
    if args.host:
        cfg.host = args.host
    if args.user:
        cfg.user = args.user
    if args.ssh_key:
        cfg.ssh_key = args.ssh_key
        cfg.auth_method = "ssh-key"

    client = SshClusterClient(cfg)

    # 3. filter
    filter_states = None
    if args.filter_states:
        filter_states = [s.strip().upper() for s in args.filter_states.split(",") if s.strip()]

    # 4. 循环(--watch) 或 单次
    def _do_query() -> list:
        return query_sweep_status(sweep_p, client, filter_states=filter_states)

    if args.watch:
        # --watch: Ctrl-C 退出
        try:
            while True:
                _print_status(_do_query(), sweep_p, cfg, args)
                _time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n(用户中断)")
            return 0
    else:
        entries = _do_query()
        _print_status(entries, sweep_p, cfg, args)
    return 0


def _print_status(entries, sweep_p, cfg, args) -> None:
    """辅助函数:打印 status 结果(表格 / JSON)。"""
    from .batch import summarize_states, format_status_table
    if args.output_json:
        import json as _json
        print(_json.dumps(
            {
                "sweep_report": str(sweep_p),
                "host": cfg.host,
                "filter": args.filter_states or None,
                "total": len(entries),
                "summary": summarize_states(entries),
                "entries": [e.to_dict() for e in entries],
            },
            indent=2, ensure_ascii=False,
        ))
        return
    # 表格
    summary = summarize_states(entries)
    summary_str = " ".join(f"{k}={v}" for k, v in sorted(summary.items()))
    print(f"\n📊 {sweep_p} 状态({len(entries)} case; {summary_str}):")
    print(format_status_table(entries))


# ============================================================================
# v0.14.0:pbs watch 子命令(Phase 4)
# ============================================================================

def cmd_pbs_watch(args):
    """``inp-tool pbs watch`` — 运行中监控 case 进度。"""
    from pathlib import Path
    from .cluster import ClusterConfig, SshClusterClient
    from .monitor import SweepMonitor, format_progress_table

    # 1. 解析 sweep_report 路径(同 submit/status)
    sweep_path = args.sweep_report
    if not sweep_path:
        print("❌ 缺少 sweep_report.json 路径(用法: inp-tool pbs watch <sweep_report.json>)", file=sys.stderr)
        return 1
    sweep_p = Path(sweep_path)
    if args.from_sweep_dir or sweep_p.is_dir():
        if sweep_p.is_dir():
            manifest = sweep_p / "manifest.json"
        else:
            manifest = sweep_p / "manifest.json"
        if not manifest.is_file():
            print(f"❌ {sweep_p} 下找不到 manifest.json", file=sys.stderr)
            return 1
        sweep_p = manifest
    if not sweep_p.is_file():
        print(f"❌ sweep_report.json 不存在: {sweep_p}", file=sys.stderr)
        return 1

    # 2. 加载 cluster config + 覆盖
    cfg = ClusterConfig.load()
    if args.host:
        cfg.host = args.host
    if args.user:
        cfg.user = args.user
    if args.ssh_key:
        cfg.ssh_key = args.ssh_key
        cfg.auth_method = "ssh-key"
    # 列覆盖
    if args.col_step is not None:
        cfg.col_step = args.col_step
    if args.col_time is not None:
        cfg.col_time = args.col_time
    if args.col_cfl_global is not None:
        cfg.col_cfl_global = args.col_cfl_global
    if args.info_file:
        cfg.info_file = args.info_file
    if args.info_meta_file:
        cfg.info_meta_file = args.info_meta_file

    client = SshClusterClient(cfg)

    # 3. info_meta_path: 远端 meta 文件,本地可读位置(用户事先下载 或用 SSH)
    # 简化:若 sweep_dir/case_xxx/ 下能找到 minfo0.mpf1d,本地用之;否则用 fallback
    import json as _json
    manifest_data = _json.loads(sweep_p.read_text())
    local_meta_path: str = ""
    cases = manifest_data.get("cases", [])
    if cases:
        first_case = Path(cases[0].get("path", ""))
        candidate = first_case / cfg.info_meta_file
        if candidate.is_file():
            local_meta_path = str(candidate)

    # 4. SweepMonitor.watch 循环
    monitor = SweepMonitor(
        sweep_p, client, info_meta_path=local_meta_path or None,
    )

    def _render(progresses):
        if args.output_json:
            import json as _json
            print(_json.dumps(
                {
                    "sweep_report": str(sweep_p),
                    "host": cfg.host,
                    "interval": args.interval,
                    "total": len(progresses),
                    "cases": [p.to_dict() for p in progresses],
                },
                indent=2, ensure_ascii=False,
            ))
        else:
            print(f"\n⏱  监控 {sweep_p} (interval={args.interval}s; {len(progresses)} case):")
            print(format_progress_table(progresses))

    if args.once:
        progresses = monitor.refresh_all()
        _render(progresses)
    else:
        # 持续循环(Ctrl-C 退出)
        try:
            monitor.watch(interval=args.interval, once=False, callback=_render)
        except KeyboardInterrupt:
            print("\n(用户中断)")
    return 0


def main(argv=None):
    # v0.7.1:--lang 顶层 flag(必须最早解析,因为 i18n 影响后续所有 help/description)
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument(
        '--lang', choices=['zh', 'en'], default=None,
        help='界面语言(zh 中文 / en English),默认 zh',
    )
    pre_args, rest_argv = pre_parser.parse_known_args(argv)
    if pre_args.lang is not None:
        from . import i18n
        i18n.set_lang(pre_args.lang)

    p = argparse.ArgumentParser(
        prog='inp',
        description='mcfd.inp 解析、修改、diff 工具',
    )
    p.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    p.add_argument(
        '--lang', choices=['zh', 'en'], default=None,
        help='界面语言(zh 中文 / en English),默认 zh',
    )
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
    si.add_argument('--detect', action='store_true',
                    help='额外输出方程系统/湍流模型/气体类型检测报告 (v0.9.1)')
    si.set_defaults(func=cmd_info)

    # === sweep 子命令 ===
    sw = sub.add_parser(
        'sweep',
        help='基于样例批量生成 mcfd.inp 算例(扫描攻角/侧滑角/来流等)',
    )
    sw.add_argument('first', nargs='?', help='模板 .inp 路径 / 或唯一参数:JSON config')
    sw.add_argument('config', nargs='?', help='可选: JSON 配置文件')
    # PR #1:CSV 模式专用
    sw.add_argument('--template', help='模板 .inp 路径(CSV 模式必填)')
    sw.add_argument('--naming', help='命名模板(CSV 模式专用,如 case_a{alpha}.inp)')
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
    # v0.8.0:整算例目录模式
    sw.add_argument(
        '--source-dir', dest='source_dir',
        help='基础算例目录(设置后每个 case = 完整子目录,默认只写 mcfd.inp)',
    )
    sw.add_argument(
        '--copy-strategy', dest='copy_strategy',
        choices=['copy', 'hardlink', 'symlink'],
        help='source_dir 复制策略(默认 hardlink)',
    )
    sw.add_argument(
        '--exclude', dest='exclude', action='append', default=[],
        help='排除规则(fnmatch 风格),可多次传,默认 *.bak mlog nodesout.bin *.log',
    )
    sw.add_argument(
        '--force', action='store_true',
        help='per_dir 模式时覆盖已存在的子目录(默认报错)',
    )
    # v0.9.0:pbs 脚本生成相关 flag
    sw.add_argument(
        '--pbs/--no-pbs', dest='pbs', default=True,
        help='per_dir 模式时是否生成 pbs 脚本(默认 yes)',
    )
    sw.add_argument(
        '--pbs-naming', dest='pbs_naming', default='',
        help='pbs 任务名模板(空 = 自动短名,例: Mars-{alpha}-{mach})',
    )
    # v0.10.0:方程改写相关 flag
    sw.add_argument(
        '--strict-equations', dest='strict_equations', action='store_true',
        default=False,
        help='v0.10.0: 残留字段(如 SST→SA 后 turbi_tlev)改为 error,默认 warning。',
    )
    sw.add_argument(
        '--no-switch-turbulence', dest='no_switch_turbulence', action='store_true',
        default=False,
        help='v0.10.0: 不切湍流模型(只写初始化),默认切。',
    )
    sw.add_argument(
        '--no-switch-energy', dest='no_switch_energy', action='store_true',
        default=False,
        help='v0.10.0: 不切能量模型,默认切。',
    )
    sw.add_argument(
        '--no-switch-gas', dest='no_switch_gas', action='store_true',
        default=False,
        help='v0.10.0: 不切气体类型,默认切。',
    )
    sw.set_defaults(func=cmd_sweep)

    sc = sub.add_parser('completion', help='输出 shell 补全脚本 (bash/zsh/fish)')
    sc.add_argument('shell', choices=['bash', 'zsh', 'fish'], help='目标 shell')
    sc.set_defaults(func=cmd_completion)

    # === shell 子命令(交互式 REPL) ===
    ssh = sub.add_parser(
        'shell',
        help='启动交互式 REPL(可预加载 0 或多个 .inp)',
    )
    ssh.add_argument('files', nargs='*', help='启动时预加载的 .inp 文件(可选)')
    ssh.set_defaults(func=cmd_shell)

    # === v0.14.0:cluster 子命令(PBS 集群配置 + 探测) ===
    sc = sub.add_parser(
        'cluster',
        help='PBS 集群配置 / 探测 / 连接测试',
    )
    sc_sub = sc.add_subparsers(dest='cluster_cmd', required=True)

    # cluster probe — 探测远端调度器
    scp = sc_sub.add_parser(
        'probe',
        help='ssh 远端探测调度器类型(自动识别 torque / slurm)',
    )
    scp.add_argument('--host', help='覆盖 cluster.json 的 host')
    scp.add_argument('--user', help='覆盖 user')
    scp.add_argument('--ssh-key', dest='ssh_key', help='SSH 私钥路径(显式)')
    scp.add_argument('--port', type=int, help='SSH 端口(默认 22)')
    scp.set_defaults(func=cmd_cluster_probe)

    # cluster config — 读/写 ~/.inp_tool/cluster.json
    scc = sc_sub.add_parser(
        'config',
        help='集群配置持久化(.inp_tool/cluster.json)',
    )
    scc.add_argument('--init', dest='init', action='store_true',
                    help='交互式生成配置(写到 ~/.inp_tool/cluster.json)')
    scc.add_argument('--show', dest='show', action='store_true',
                    help='打印当前配置(JSON)')
    scc.add_argument('--set', dest='set_kv', action='append', default=[],
                    metavar='KEY=VALUE',
                    help='设置单个字段(可多次),如 --set host=10.10.10.251')
    scc.add_argument('--path', dest='path', action='store_true',
                    help='打印配置文件路径')
    scc.set_defaults(func=cmd_cluster_config)

    # cluster test — 真 ssh 跑通连接(暂不提交,只验证)
    sct = sc_sub.add_parser(
        'test',
        help='测试 ssh 连接 + 调度器识别(读/写 cluster.json)',
    )
    sct.add_argument('--host', help='覆盖 host')
    sct.add_argument('--user', help='覆盖 user')
    sct.add_argument('--ssh-key', dest='ssh_key', help='SSH 私钥路径')
    sct.set_defaults(func=cmd_cluster_test)

    # === v0.14.0:pbs submit 子命令(Phase 2) ===
    spbs = sub.add_parser(
        'pbs',
        help='PBS 批量提交 / 状态查询 / 监控(Phase 2+)',
    )
    spbs_sub = spbs.add_subparsers(dest='pbs_cmd', required=True)

    # pbs submit — 批量提交 sweep_report.json 中所有 case
    spbs_submit = spbs_sub.add_parser(
        'submit',
        help='批量提交 sweep_report.json 中所有 case 到 PBS 集群',
    )
    spbs_submit.add_argument(
        'sweep_report', nargs='?',
        help='sweep_report.json 路径(或 sweep 目录,自动找 manifest.json)',
    )
    spbs_submit.add_argument(
        '--from-sweep-dir', dest='from_sweep_dir', action='store_true',
        help='sweep_report 是 sweep 目录,自动找 manifest.json',
    )
    spbs_submit.add_argument('--host', help='覆盖 cluster.json 的 host')
    spbs_submit.add_argument('--user', help='覆盖 user')
    spbs_submit.add_argument('--ssh-key', dest='ssh_key', help='SSH 私钥路径')
    spbs_submit.add_argument('--queue', help='覆盖 -q (PBS queue)')
    spbs_submit.add_argument('--walltime', help='覆盖 -l walltime')
    spbs_submit.add_argument('--nodes', type=int, help='覆盖 -l nodes')
    spbs_submit.add_argument('--ppn', type=int, help='覆盖 -l ppn')
    spbs_submit.add_argument(
        '--max-concurrent-jobs', dest='max_concurrent_jobs', type=int,
        help='覆盖 cluster.json 的 max_concurrent_jobs',
    )
    spbs_submit.add_argument(
        '--dry-run', dest='dry_run', action='store_true',
        help='不真提交,只记录(配合 LocalDryRunClient)',
    )
    spbs_submit.add_argument('--limit', type=int, help='只提交前 N 个 case')
    spbs_submit.add_argument(
        '--skip-existing', dest='skip_existing', action='store_true', default=True,
        help='跳过 manifest 中已存在的 case(默认 True)',
    )
    spbs_submit.add_argument(
        '--no-skip-existing', dest='skip_existing', action='store_false',
        help='强制重提,即使 manifest 中已有记录',
    )
    spbs_submit.add_argument(
        '--no-respect-concurrency', dest='respect_concurrency',
        action='store_false', default=True,
        help='Q3: 忽略 max_concurrent_jobs 限流,直接提交',
    )
    spbs_submit.set_defaults(func=cmd_pbs_submit)

    # pbs status — 状态查询(Phase 3)
    spbs_status = spbs_sub.add_parser(
        'status',
        help='查询 sweep_report.json 中所有 case 的 PBS 状态(qstat)',
    )
    spbs_status.add_argument(
        'sweep_report', nargs='?',
        help='sweep_report.json 路径(或 sweep 目录,自动找 manifest.json)',
    )
    spbs_status.add_argument(
        '--from-sweep-dir', dest='from_sweep_dir', action='store_true',
        help='sweep_report 是 sweep 目录,自动找 manifest.json',
    )
    spbs_status.add_argument('--host', help='覆盖 cluster.json 的 host')
    spbs_status.add_argument('--user', help='覆盖 user')
    spbs_status.add_argument('--ssh-key', dest='ssh_key', help='SSH 私钥路径')
    spbs_status.add_argument(
        '--filter', dest='filter_states', default='',
        help='按 state 过滤(逗号分隔,如 R,Q 只看运行+排队)',
    )
    spbs_status.add_argument(
        '--json', dest='output_json', action='store_true',
        help='输出 JSON(机器可读)',
    )
    spbs_status.add_argument(
        '--watch', dest='watch', action='store_true',
        help='持续刷新(每 5s)',
    )
    spbs_status.add_argument(
        '--interval', dest='interval', type=int, default=5,
        help='--watch 刷新间隔(秒,默认 5)',
    )
    spbs_status.add_argument('--no-color', dest='no_color', action='store_true')
    spbs_status.set_defaults(func=cmd_pbs_status)

    # pbs watch — 运行中监控(Phase 4):读 mcfd.info0 显示 step / CFL / 残差
    spbs_watch = spbs_sub.add_parser(
        'watch',
        help='运行中监控 sweep_report.json 中所有 case 的 mcfd.info0(步数/CFL/残差)',
    )
    spbs_watch.add_argument(
        'sweep_report', nargs='?',
        help='sweep_report.json 路径(或 sweep 目录)',
    )
    spbs_watch.add_argument(
        '--from-sweep-dir', dest='from_sweep_dir', action='store_true',
        help='sweep_report 是 sweep 目录',
    )
    spbs_watch.add_argument('--host', help='覆盖 cluster.json 的 host')
    spbs_watch.add_argument('--user', help='覆盖 user')
    spbs_watch.add_argument('--ssh-key', dest='ssh_key', help='SSH 私钥路径')
    spbs_watch.add_argument(
        '--interval', dest='interval', type=int, default=30,
        help='刷新间隔秒(默认 30)',
    )
    spbs_watch.add_argument(
        '--info-file', dest='info_file', default='mcfd.info0',
        help='mcfd.info0 文件名(默认 mcfd.info0)',
    )
    spbs_watch.add_argument(
        '--info-meta-file', dest='info_meta_file', default='minfo0.mpf1d',
        help='列名元数据文件名(默认 minfo0.mpf1d)',
    )
    spbs_watch.add_argument(
        '--col-step', dest='col_step', type=int, default=0,
        help='step# 列索引(默认 0)',
    )
    spbs_watch.add_argument(
        '--col-time', dest='col_time', type=int, default=1,
        help='time 列索引(默认 1)',
    )
    spbs_watch.add_argument(
        '--col-cfl-global', dest='col_cfl_global', type=int, default=5,
        help='CFL_global 列索引(默认 5)',
    )
    spbs_watch.add_argument(
        '--res-cols', dest='res_cols', default='3,4',
        help='要显示的残差列索引(逗号分隔,默认 3,4=RHS_avg,RHS_max)',
    )
    spbs_watch.add_argument(
        '--once', dest='once', action='store_true',
        help='只跑一次不循环',
    )
    spbs_watch.add_argument(
        '--json', dest='output_json', action='store_true',
        help='输出 JSON',
    )
    spbs_watch.add_argument('--no-color', dest='no_color', action='store_true')
    spbs_watch.set_defaults(func=cmd_pbs_watch)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
