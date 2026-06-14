"""``inp-tool post {extract,convergence,report,plot,all}`` 子命令实现。

把 ``inp_tool.postprocess`` 子包暴露给命令行。每个子命令各 1 个
``cmd_post_*`` 函数,通过 ``_register_post_subparser`` 注册到顶层
``cli.main()`` 的 subparser 上。

依赖边界:
- 核心子命令(``extract`` / ``convergence``)走纯 stdlib 路径
- ``report`` / ``plot`` / ``all`` 走 ``[post]`` extras,缺包时给清晰
  ``ImportError`` 提示 ``pip install inp-tool[post]``

参考:
- reference/code/CFDPlus_V4.py:1093-1141 (cmd_extract_one / cmd_extract_all)
- reference/code/CFDPlus_extract.py:716-786 (extract + 收敛分析的 CLI 入口)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Sequence

from .postprocess.convergence import (
    DEFAULT_CV_THRESHOLD,
    DEFAULT_MIN_WINDOW,
    DEFAULT_WINDOW_FRACTION,
    compute_convergence,
    format_convergence_report,
)
from .postprocess.forces import (
    ReferenceGeometry,
    summarize_forces,
)
from .postprocess.info1 import read_info1


# ============================================================================
# 公共辅助
# ============================================================================

def _parse_op_ibd(s: str) -> List[int]:
    """解析 ``--op "1,2,3"`` → [1, 2, 3]。空串 → 抛错。"""
    if not s or not s.strip():
        raise ValueError("--op cannot be empty; pass e.g. --op 1 or --op 1,2,3")
    parts = [p.strip() for p in s.split(",") if p.strip()]
    try:
        return [int(p) for p in parts]
    except ValueError:
        raise ValueError(f"--op must be comma-separated integers, got: {s!r}")


def _validate_case_dirs(case_dirs: Sequence[str]) -> List[Path]:
    """每个 case_dir 必须存在;否则 stderr + 返回空 list 让调用方退出。"""
    result = []
    for cd in case_dirs:
        p = Path(cd)
        if not p.is_dir():
            print(f"Error: case directory not found: {cd}", file=sys.stderr)
            return []
        result.append(p)
    return result


def _build_ref_geom(args) -> ReferenceGeometry:
    """从 args 提取 Sref/Lref/Xref/Yref/Zref(默认值 1.0 / 0.0)。"""
    return ReferenceGeometry(
        Sref=args.sref,
        Lref=args.lref,
        Xref=args.xref,
        Yref=args.yref,
        Zref=args.zref,
    )


def _print_coefficient_row(row, quiet: bool = False) -> None:
    """简洁打印一行系数(供 extract 子命令)。"""
    if quiet:
        return
    print(f"\n[Case: {row.case}]")
    print(f"  Ma = {row.Ma:.4g}, H = {row.H:.2f} km, "
          f"α = {row.alpha_deg:.3f}°, β = {row.beta_deg:.3f}°")
    print(f"  Fx = {row.Fx:.4e} N, Fy = {row.Fy:.4e} N, Fz = {row.Fz:.4e} N")
    print(f"  Mx = {row.Mx:.4e} N·m, My = {row.My:.4e} N·m, Mz = {row.Mz:.4e} N·m")
    print(f"  D  = {row.D:.4e} N, L  = {row.L:.4e} N, L/D = {row.L_over_D:.4f}")
    print(f"  CD = {row.CD:.5f}, CY = {row.CY:.5f}, CL = {row.CL:.5f}")
    print(f"  Cmx = {row.Cmx:.5f}, Cmy = {row.Cmy:.5f}, Cmz = {row.Cmz:.5f}")
    print(f"  Q  = {row.Q:.4e} Pa, Re = {row.Re:.4e} /m, Xcp = {row.Xcp:.4f} m")


# ============================================================================
# post extract
# ============================================================================

def cmd_post_extract(args) -> int:
    """气动力 + 系数提取(单/多 case)。"""
    case_dirs = _validate_case_dirs(args.case_dirs)
    if not case_dirs:
        return 1

    try:
        op_ibd = _parse_op_ibd(args.op)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    ref_geom = _build_ref_geom(args)
    report = summarize_forces(case_dirs, op_ibd, ref_geom, xcg=args.xcg)

    if not report.rows:
        print("Warning: no valid cases found (missing mcfd.inp or mcfd.info1).",
              file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Extracted {len(report.rows)} case(s):")
        for row in report.rows:
            _print_coefficient_row(row, quiet=False)

    return 0


# ============================================================================
# post convergence
# ============================================================================

def cmd_post_convergence(args) -> int:
    """收敛性 CV 判定 + 文本报告。"""
    case_dirs = _validate_case_dirs(args.case_dirs)
    if not case_dirs:
        return 1

    try:
        op_ibd = _parse_op_ibd(args.op)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    out_dir = Path(args.out) if args.out else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for case_dir in case_dirs:
        info1_path = case_dir / "mcfd.info1"
        if not info1_path.is_file():
            results.append((case_dir.name, None))
            continue
        steps = read_info1(info1_path, op_ibd)
        window = compute_convergence(
            steps,
            threshold=args.cv_threshold,
            fraction=args.window_fraction,
            min_window=args.min_window,
        )
        results.append((case_dir.name, window))

    report_text = format_convergence_report(
        results,
        threshold=args.cv_threshold,
        fraction=args.window_fraction,
    )

    out_file = out_dir / "convergence_report.txt"
    out_file.write_text(report_text, encoding="utf-8")
    if not args.quiet:
        print(f"Wrote convergence report: {out_file}")

    return 0


# ============================================================================
# post report ([post] extras)
# ============================================================================

def cmd_post_report(args) -> int:
    """生成 Excel 报告(需 [post] extras)。"""
    case_dirs = _validate_case_dirs(args.case_dirs)
    if not case_dirs:
        return 1

    try:
        op_ibd = _parse_op_ibd(args.op)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    ref_geom = _build_ref_geom(args)
    report = summarize_forces(case_dirs, op_ibd, ref_geom, xcg=args.xcg)

    out_path = Path(args.out) if args.out else Path.cwd() / "ForceReport.xlsx"

    try:
        from .postprocess.report import write_excel
        write_excel(report, out_path)
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Wrote Excel report: {out_path}")

    return 0


# ============================================================================
# post plot ([post] extras)
# ============================================================================

def cmd_post_plot(args) -> int:
    """生成收敛曲线 png(需 [post] extras)。"""
    case_dirs = _validate_case_dirs(args.case_dirs)
    if not case_dirs:
        return 1

    try:
        op_ibd = _parse_op_ibd(args.op)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    out_path = Path(args.out) if args.out else Path.cwd() / "convergence_plot.png"

    plot_data = []
    for case_dir in case_dirs:
        info1_path = case_dir / "mcfd.info1"
        if not info1_path.is_file():
            plot_data.append((case_dir.name, None, None))
            continue
        steps = read_info1(info1_path, op_ibd)
        window = compute_convergence(
            steps,
            threshold=args.cv_threshold,
            fraction=args.window_fraction,
            min_window=args.min_window,
        )
        plot_data.append((case_dir.name, window, steps))

    try:
        from .postprocess.plot import save_convergence_plot
        save_convergence_plot(plot_data, out_path)
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Wrote convergence plot: {out_path}")

    return 0


# ============================================================================
# post all
# ============================================================================

def cmd_post_all(args) -> int:
    """一站式:extract + convergence + report + plot。"""
    case_dirs = _validate_case_dirs(args.case_dirs)
    if not case_dirs:
        return 1

    try:
        op_ibd = _parse_op_ibd(args.op)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir) if args.out_dir else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    ref_geom = _build_ref_geom(args)

    # 1. extract
    report = summarize_forces(case_dirs, op_ibd, ref_geom, xcg=args.xcg)
    if not report.rows:
        print("Warning: no valid cases found.", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"\n=== [1/4] Extract: {len(report.rows)} case(s) ===")
        for row in report.rows:
            _print_coefficient_row(row, quiet=args.quiet)

    # 2. convergence
    conv_results = []
    plot_data = []
    for case_dir in case_dirs:
        info1_path = case_dir / "mcfd.info1"
        if not info1_path.is_file():
            conv_results.append((case_dir.name, None))
            plot_data.append((case_dir.name, None, None))
            continue
        steps = read_info1(info1_path, op_ibd)
        window = compute_convergence(
            steps,
            threshold=args.cv_threshold,
            fraction=args.window_fraction,
            min_window=args.min_window,
        )
        conv_results.append((case_dir.name, window))
        plot_data.append((case_dir.name, window, steps))

    conv_text = format_convergence_report(
        conv_results,
        threshold=args.cv_threshold,
        fraction=args.window_fraction,
    )
    conv_file = out_dir / "convergence_report.txt"
    conv_file.write_text(conv_text, encoding="utf-8")
    if not args.quiet:
        print(f"\n=== [2/4] Convergence: {conv_file} ===")

    # 3. report (xlsx)
    xlsx_file = out_dir / "ForceReport.xlsx"
    try:
        from .postprocess.report import write_excel
        write_excel(report, xlsx_file)
        if not args.quiet:
            print(f"\n=== [3/4] Report: {xlsx_file} ===")
    except ImportError as e:
        print(f"\nWarning: skipping Excel report — {e}", file=sys.stderr)

    # 4. plot (png)
    png_file = out_dir / "convergence_plot.png"
    try:
        from .postprocess.plot import save_convergence_plot
        save_convergence_plot(plot_data, png_file)
        if not args.quiet:
            print(f"\n=== [4/4] Plot: {png_file} ===")
    except ImportError as e:
        print(f"\nWarning: skipping plot — {e}", file=sys.stderr)

    return 0


# ============================================================================
# argparse 注册
# ============================================================================

def _register_post_subparser(sub) -> None:
    """注册到顶层 ``cli.main()`` 的 subparser。"""
    spost = sub.add_parser(
        "post",
        help="后处理:气动力提取 / 收敛分析 / Excel / 收敛图",
        description=(
            "CFD++ 算例后处理工具集。"
            "extract/convergence 走零依赖;"
            "report/plot/all 需 'pip install inp-tool[post]'。"
        ),
    )
    spost_sub = spost.add_subparsers(dest="post_cmd", required=True)

    def _add_geom_args(p):
        p.add_argument("--sref", type=float, default=1.0,
                       help="参考面积 (m²,默认 1.0)")
        p.add_argument("--lref", type=float, default=1.0,
                       help="参考长度 (m,默认 1.0)")
        p.add_argument("--xref", type=float, default=0.0,
                       help="参考矩心 X 坐标 (m,默认 0)")
        p.add_argument("--yref", type=float, default=0.0,
                       help="参考矩心 Y 坐标 (m,默认 0)")
        p.add_argument("--zref", type=float, default=0.0,
                       help="参考矩心 Z 坐标 (m,默认 0)")
        p.add_argument("--xcg", type=float, default=0.0,
                       help="重心 X 坐标 (m,默认 0,只填进输出)")

    def _add_conv_args(p):
        p.add_argument(
            "--cv-threshold", dest="cv_threshold", type=float,
            default=DEFAULT_CV_THRESHOLD,
            help=f"CV 收敛阈值(默认 {DEFAULT_CV_THRESHOLD})",
        )
        p.add_argument(
            "--window-fraction", dest="window_fraction", type=float,
            default=DEFAULT_WINDOW_FRACTION,
            help=f"收敛窗口占比(默认 {DEFAULT_WINDOW_FRACTION})",
        )
        p.add_argument(
            "--min-window", dest="min_window", type=int,
            default=DEFAULT_MIN_WINDOW,
            help=f"最小窗口步数(默认 {DEFAULT_MIN_WINDOW})",
        )

    # ---- post extract ----
    se = spost_sub.add_parser("extract", help="提取气动力 + 系数")
    se.add_argument("case_dirs", nargs="+", help="算例目录(可多个)")
    se.add_argument("--op", required=True,
                    help="积分边界 op,逗号分隔(如 '1' 或 '1,2,3')")
    _add_geom_args(se)
    se.add_argument("--quiet", action="store_true", help="静默")
    se.set_defaults(func=cmd_post_extract)

    # ---- post convergence ----
    sc = spost_sub.add_parser("convergence", help="CV 收敛性分析 + 文本报告")
    sc.add_argument("case_dirs", nargs="+", help="算例目录(可多个)")
    sc.add_argument("--op", required=True, help="积分边界 op")
    _add_conv_args(sc)
    sc.add_argument("--out", default=None,
                    help="输出目录(写 convergence_report.txt,默认 ./)")
    sc.add_argument("--quiet", action="store_true", help="静默")
    sc.set_defaults(func=cmd_post_convergence)

    # ---- post report (xlsx) ----
    sr = spost_sub.add_parser(
        "report",
        help="extract + 写 Excel(需 [post] extras)",
    )
    sr.add_argument("case_dirs", nargs="+", help="算例目录(可多个)")
    sr.add_argument("--op", required=True, help="积分边界 op")
    _add_geom_args(sr)
    sr.add_argument("--out", default=None,
                    help="输出 xlsx 路径(默认 ./ForceReport.xlsx)")
    sr.add_argument("--quiet", action="store_true", help="静默")
    sr.set_defaults(func=cmd_post_report)

    # ---- post plot (png) ----
    sp = spost_sub.add_parser(
        "plot",
        help="读 info1 + 画收敛曲线 png(需 [post] extras)",
    )
    sp.add_argument("case_dirs", nargs="+", help="算例目录(可多个)")
    sp.add_argument("--op", required=True, help="积分边界 op")
    _add_conv_args(sp)
    sp.add_argument("--out", default=None,
                    help="输出 png 路径(默认 ./convergence_plot.png)")
    sp.add_argument("--quiet", action="store_true", help="静默")
    sp.set_defaults(func=cmd_post_plot)

    # ---- post all (extract + convergence + report + plot 一站式) ----
    sa = spost_sub.add_parser(
        "all",
        help="一站式:extract + convergence + report + plot",
    )
    sa.add_argument("case_dirs", nargs="+", help="算例目录(可多个)")
    sa.add_argument("--op", required=True, help="积分边界 op")
    _add_geom_args(sa)
    _add_conv_args(sa)
    sa.add_argument("--out-dir", dest="out_dir", default=None,
                    help="输出目录(默认 ./,所有产物写在此)")
    sa.add_argument("--quiet", action="store_true", help="静默")
    sa.set_defaults(func=cmd_post_all)
