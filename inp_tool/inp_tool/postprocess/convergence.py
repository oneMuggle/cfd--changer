"""收敛性判定:对 mcfd.info1 时间步序列计算变异系数(CV)判定收敛。

零运行时依赖,纯 Python stdlib(``math`` + ``dataclasses``)。

参考实现:reference/code/CFDPlus_extract.py:584-686

判定规则(reference 行为):
- 取末 ``n_window = max(min_window, n_total · fraction)`` 步作为收敛窗口
- 默认 ``min_window=100``,``fraction=0.1``(末 10% 步,但至少 100 步)
- 数据 < ``min_window`` → 返回 ``None`` (数据不足)
- 对每个分量(Fx/Fy/Fz/Mx/My/Mz)在窗口内算 ``CV = std(ddof=1) / |mean|``
- ``CV < 0.001`` (0.1%) 视为该分量收敛
- 所有 6 个分量都收敛 → ``all_converged = True``

边界:
- ``mean == 0`` 时 CV 约定为 0(不视为不收敛 — 物理上 0 力是有意义的均值)
- ``n_total == 1`` 时无法算 ddof=1 std → 视作数据不足
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .info1 import Info1Step

# ============================================================================
# 默认常量
# ============================================================================

DEFAULT_CV_THRESHOLD = 0.001     # CV < 0.1% 收敛
DEFAULT_WINDOW_FRACTION = 0.1    # 末 10% 步
DEFAULT_MIN_WINDOW = 100         # 窗口至少 100 步

_COMPONENT_NAMES = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")


# ============================================================================
# Dataclass
# ============================================================================

@dataclass(frozen=True)
class ConvergenceWindow:
    """单算例的收敛性分析结果。

    - ``n_total``: 总迭代步数
    - ``n_window``: 用于判定的窗口步数(取末 n_window 步)
    - ``cv``: 6 元 tuple,每分量的变异系数 std/|mean|(0 ≤ cv < ∞)
    - ``converged``: 6 元 tuple of bool,该分量 CV < threshold 即 True
    - ``all_converged``: 是否所有 6 分量都收敛
    """
    n_total: int
    n_window: int
    cv: Tuple[float, float, float, float, float, float]
    converged: Tuple[bool, bool, bool, bool, bool, bool]
    all_converged: bool


# ============================================================================
# 公共 API:compute_convergence
# ============================================================================

def compute_convergence(
    steps: Sequence[Info1Step],
    threshold: float = DEFAULT_CV_THRESHOLD,
    fraction: float = DEFAULT_WINDOW_FRACTION,
    min_window: int = DEFAULT_MIN_WINDOW,
) -> Optional[ConvergenceWindow]:
    """对单算例的 Info1Step 序列计算收敛窗口。

    数据不足(``len(steps) < min_window``)→ 返回 ``None``。
    """
    n_total = len(steps)
    if n_total < min_window:
        return None

    n_window = max(min_window, int(n_total * fraction))
    n_window = min(n_window, n_total)  # 窗口不超过总长

    window = steps[-n_window:]

    cv_list = []
    converged_list = []
    for axis in range(6):
        vals = [s.total[axis] for s in window]
        mean = _mean(vals)
        std = _sample_std(vals, mean)
        if abs(mean) > 1e-30:
            cv = abs(std / mean)
        else:
            # mean ≈ 0:CV 约定为 0(物理上"0 力是稳定的均值")
            cv = 0.0
        cv_list.append(cv)
        converged_list.append(cv < threshold)

    return ConvergenceWindow(
        n_total=n_total,
        n_window=n_window,
        cv=tuple(cv_list),       # type: ignore[arg-type]
        converged=tuple(converged_list),  # type: ignore[arg-type]
        all_converged=all(converged_list),
    )


# ============================================================================
# 公共 API:format_convergence_report
# ============================================================================

def format_convergence_report(
    results: Sequence[Tuple[str, Optional[ConvergenceWindow]]],
    threshold: float = DEFAULT_CV_THRESHOLD,
    fraction: float = DEFAULT_WINDOW_FRACTION,
) -> str:
    """生成中文 UTF-8 收敛报告。

    ``results``:``[(case_name, window or None), ...]`` 列表。
    """
    sep_main = "=" * 70
    sep_comp = "-" * 55

    lines: List[str] = []
    lines.append(sep_main)
    lines.append("  CFD++ 气动力收敛性分析报告")
    lines.append(sep_main)
    lines.append("")
    lines.append(f"收敛判定标准: 各分量变异系数 CV < {threshold * 100:.2f}%")
    lines.append(f"收敛窗口: 末 {fraction * 100:.0f}% 迭代步(至少 {DEFAULT_MIN_WINDOW} 步)")
    lines.append("")

    for case_name, res in results:
        lines.append(sep_main)
        lines.append(f"  算例: {case_name}")
        lines.append(sep_main)
        lines.append("")

        if res is None:
            lines.append("  数据量不足,无法判断收敛性")
            lines.append("")
            continue

        lines.append(f"  总迭代步: {res.n_total}")
        lines.append(f"  收敛窗口: 末 {res.n_window} 步")
        lines.append("")
        lines.append(f"  {sep_comp}")
        lines.append(f"  {'分量':<6}  {'CV(%)':<15}  {'收敛状态':<12}")
        lines.append(f"  {sep_comp}")

        for axis in range(6):
            cv_pct = res.cv[axis] * 100
            status = "收敛" if res.converged[axis] else "未收敛"
            lines.append(
                f"  {_COMPONENT_NAMES[axis]:<6}  "
                f"{cv_pct:<15.4f}  {status:<12}"
            )

        lines.append(f"  {sep_comp}")
        overall = "全部收敛" if res.all_converged else "未全部收敛"
        lines.append(f"  综合判定: {overall}")
        lines.append("")

    lines.append(sep_main)
    lines.append(f"  报告生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(sep_main)

    return "\n".join(lines) + "\n"


# ============================================================================
# 内部:统计辅助(零依赖手撸,以保 numpy 可选)
# ============================================================================

def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _sample_std(values: Sequence[float], mean: float) -> float:
    """ddof=1 样本标准差(n < 2 时返回 0)。"""
    n = len(values)
    if n < 2:
        return 0.0
    sq_sum = sum((v - mean) ** 2 for v in values)
    return math.sqrt(sq_sum / (n - 1))
