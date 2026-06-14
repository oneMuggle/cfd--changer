"""收敛曲线 png 输出(可选依赖,走 ``[post]`` extras)。

依赖:``matplotlib``。顶层不 import — 调用 ``save_convergence_plot`` 时
按需 lazy import,且**显式调用** ``matplotlib.use("Agg")`` 强制无 GUI 后端,
兼容 CI / 远程服务器 / Win7 无 X11 等场景。

参考实现:reference/code/CFDPlus_extract.py:688-709

设计要点:
- ``save_convergence_plot(results, out_path) -> Path``
- 2×3 subplot 布局,6 子图对应 Fx/Fy/Fz/Mx/My/Mz
- ``results``:``list[(case_name: str, window: ConvergenceWindow | None, steps: list[Info1Step] | None)]``
- ``window=None`` 或 ``steps=None`` 跳过该 case(不抛错)
- DPI 150,figsize 14×9(reference 一致)
- 多 case 叠加 + 自动 legend(>1 case 才显示)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

from .convergence import ConvergenceWindow
from .info1 import Info1Step

# 子图标题(对应 Info1Step.total 的 6 个分量)
_COMPONENT_NAMES = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")

# 画图常量
_FIG_SIZE = (14, 9)
_DPI = 150
_LINE_WIDTH = 1.2
_LEGEND_FONT_SIZE = 8
_TITLE_FONT_SIZE = 12
_SUPTITLE_FONT_SIZE = 16

# results 的元素类型:(case_name, window, steps)
PlotResultEntry = Tuple[
    str,
    Optional[ConvergenceWindow],
    Optional[Sequence[Info1Step]],
]


def save_convergence_plot(
    results: Sequence[PlotResultEntry],
    out_path: Union[str, Path],
) -> Path:
    """把收敛历程画成 2×3 png,返回输出路径。

    参数:
    - ``results``:``[(case_name, window, steps), ...]`` 列表
      - ``window=None`` 或 ``steps=None`` → 该 case 跳过画线
    - ``out_path``:输出 png 路径

    强制走 ``Agg`` 后端(无 GUI),适合 CI / 远程。
    多 case 时显示 legend;单 case 不显示。

    无 ``matplotlib`` 时抛 ``ImportError`` 提示安装 ``inp-tool[post]``。
    """
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise ImportError(
            "matplotlib is required for save_convergence_plot; "
            "install with: pip install inp-tool[post]"
        ) from e

    out = Path(out_path)

    fig = plt.figure(figsize=_FIG_SIZE)
    fig.suptitle("CFD++ Aerodynamic Convergence",
                 fontsize=_SUPTITLE_FONT_SIZE, fontweight="bold")

    valid_cases = [(name, steps) for name, _, steps in results if steps]
    show_legend = len(valid_cases) > 1

    for axis in range(6):
        ax = fig.add_subplot(2, 3, axis + 1)
        for case_name, steps in valid_cases:
            x_vals = [s.step for s in steps]
            y_vals = [s.total[axis] for s in steps]
            ax.plot(x_vals, y_vals, label=case_name, linewidth=_LINE_WIDTH)
        ax.set_title(_COMPONENT_NAMES[axis],
                     fontsize=_TITLE_FONT_SIZE, fontweight="bold")
        ax.set_xlabel("nstep")
        ax.grid(True, alpha=0.3)
        if show_legend:
            ax.legend(fontsize=_LEGEND_FONT_SIZE, loc="best")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)

    return out
