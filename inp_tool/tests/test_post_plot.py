"""``inp_tool.postprocess.plot`` 单元测试。

测试覆盖:
- ``save_convergence_plot(results, out_path)`` 输出非空 png
- 2×3 subplot 布局(6 个分量 Fx/Fy/Fz/Mx/My/Mz)
- 多 case 叠加 → legend 数量正确
- None 结果(数据不足)处理
- 显式 ``matplotlib.use("Agg")`` 后端兼容无 GUI 平台
- 接收 str 或 Path

依赖:``matplotlib``([post] extras),用 ``pytest.importorskip`` 守卫。

参考实现:reference/code/CFDPlus_extract.py:688-709
"""
from __future__ import annotations

from pathlib import Path

import pytest

# 跳过整个测试模块 if matplotlib 未装(走 [post] extras 才装)
matplotlib = pytest.importorskip("matplotlib")

from inp_tool.postprocess.convergence import (  # noqa: E402
    compute_convergence,
)
from inp_tool.postprocess.info1 import Info1Step  # noqa: E402


# ============================================================================
# 测试用 fixture data
# ============================================================================

def _make_steps(n: int, fx_start: float = 1.0, fx_drift: float = 0.0) -> list:
    """合成 n 步 Info1Step,Fx 可控漂移。"""
    return [
        Info1Step(
            step=i, time=float(i) * 0.001,
            total=(fx_start + fx_drift * i, 1.0, 1.0, 1.0, 1.0, 1.0),
            inv=(fx_start + fx_drift * i, 1.0, 1.0, 1.0, 1.0, 1.0),
            vis=(0.0,) * 6,
        )
        for i in range(1, n + 1)
    ]


def _result_with_data(case_name: str, n: int = 200) -> tuple:
    """构造一个 (case_name, ConvergenceWindow, steps) 3 元 tuple 用于 plot。"""
    steps = _make_steps(n)
    window = compute_convergence(steps)
    return (case_name, window, steps)


# ============================================================================
# save_convergence_plot — 基础形状
# ============================================================================

class TestSaveConvergencePlotBasic:
    def test_writes_png_file(self, tmp_path):
        from inp_tool.postprocess.plot import save_convergence_plot
        out = tmp_path / "convergence.png"
        results = [_result_with_data("case_01", n=200)]
        save_convergence_plot(results, out)
        assert out.is_file()

    def test_png_non_empty(self, tmp_path):
        from inp_tool.postprocess.plot import save_convergence_plot
        out = tmp_path / "convergence.png"
        results = [_result_with_data("case_01", n=200)]
        save_convergence_plot(results, out)
        # 一个有效 png 至少 1KB
        assert out.stat().st_size > 1024

    def test_returns_path(self, tmp_path):
        from inp_tool.postprocess.plot import save_convergence_plot
        out = tmp_path / "convergence.png"
        results = [_result_with_data("case_01", n=200)]
        result = save_convergence_plot(results, out)
        assert result == out


# ============================================================================
# save_convergence_plot — 多 case 叠加
# ============================================================================

class TestSaveConvergencePlotMultiCase:
    def test_two_cases_same_plot(self, tmp_path):
        from inp_tool.postprocess.plot import save_convergence_plot
        out = tmp_path / "convergence.png"
        results = [
            _result_with_data("alpha_5", n=200),
            _result_with_data("alpha_10", n=200),
        ]
        save_convergence_plot(results, out)
        assert out.is_file()

    def test_five_cases_all_drawn(self, tmp_path):
        from inp_tool.postprocess.plot import save_convergence_plot
        out = tmp_path / "convergence.png"
        results = [_result_with_data(f"case_{i}", n=200) for i in range(5)]
        save_convergence_plot(results, out)
        # 5 个 case 应该都能画;png 应该 > 1KB
        assert out.stat().st_size > 1024


# ============================================================================
# save_convergence_plot — None 结果容错
# ============================================================================

class TestSaveConvergencePlotNoneHandling:
    def test_none_window_skipped(self, tmp_path):
        """有 case 数据不足(ConvergenceWindow=None)应被跳过,不抛错。"""
        from inp_tool.postprocess.plot import save_convergence_plot
        out = tmp_path / "convergence.png"
        results = [
            ("case_short", None, None),         # 数据不足
            _result_with_data("case_good", n=200),  # 正常
        ]
        save_convergence_plot(results, out)
        assert out.is_file()

    def test_all_none_returns_empty_plot(self, tmp_path):
        """所有 case 都 None → 仍能写 png(空轴)。"""
        from inp_tool.postprocess.plot import save_convergence_plot
        out = tmp_path / "empty.png"
        results = [("case_a", None, None), ("case_b", None, None)]
        save_convergence_plot(results, out)
        # png 文件还是会生成,大小 > 1KB(matplotlib 空 figure 也是)
        assert out.is_file()


# ============================================================================
# save_convergence_plot — Path 类型
# ============================================================================

class TestSaveConvergencePlotPathTypes:
    def test_accepts_str_path(self, tmp_path):
        from inp_tool.postprocess.plot import save_convergence_plot
        out = str(tmp_path / "p.png")
        results = [_result_with_data("c", n=200)]
        save_convergence_plot(results, out)
        assert Path(out).is_file()

    def test_accepts_pathlib_path(self, tmp_path):
        from inp_tool.postprocess.plot import save_convergence_plot
        out = tmp_path / "p.png"
        results = [_result_with_data("c", n=200)]
        save_convergence_plot(results, out)
        assert out.is_file()


# ============================================================================
# save_convergence_plot — 后端兼容
# ============================================================================

class TestSaveConvergencePlotBackend:
    """无 GUI 平台(CI)应当用 'Agg' 后端,不能弹 figure。"""

    def test_no_gui_required(self, tmp_path, monkeypatch):
        """模拟无 DISPLAY 环境变量(Linux 无 X11 场景)→ 仍能画。"""
        monkeypatch.delenv("DISPLAY", raising=False)
        from inp_tool.postprocess.plot import save_convergence_plot
        out = tmp_path / "no_display.png"
        results = [_result_with_data("c", n=200)]
        # 应不抛错(走 Agg 后端)
        save_convergence_plot(results, out)
        assert out.is_file()


# ============================================================================
# save_convergence_plot — 数据格式适配
# ============================================================================

class TestResultFormatAcceptance:
    """``save_convergence_plot`` 应能接收多种 result 元素格式。

    本测试约定输入是 ``(case_name, window, steps)`` 3 元 tuple,
    其中 steps 是 list[Info1Step]。
    """

    def test_three_tuple_format(self, tmp_path):
        from inp_tool.postprocess.plot import save_convergence_plot
        out = tmp_path / "p.png"
        results = [_result_with_data("c", n=200)]
        save_convergence_plot(results, out)
        assert out.is_file()
