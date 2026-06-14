"""``inp_tool.postprocess.convergence`` 单元测试。

测试覆盖:
- ``ConvergenceWindow`` dataclass
- ``compute_convergence(steps, threshold, fraction, min_window)``:
  - 100 步常量 → cv=0 全部收敛
  - 100 步线性递增 → cv>0.001 不收敛(漂移)
  - 50 步 → 返回 None(数据不足)
  - 99 步 + min_window=100 → 返回 None
  - 默认阈值 0.001(0.1%)
  - 默认窗口比例 0.1(末 10% 步,至少 100 步)
- ``format_convergence_report(results)``:
  - 中文 UTF-8 输出
  - 单 case / 多 case / 空 / None res

参考实现:reference/code/CFDPlus_extract.py:584-686
"""
from __future__ import annotations

import pytest

from inp_tool.postprocess.convergence import (
    DEFAULT_CV_THRESHOLD,
    DEFAULT_MIN_WINDOW,
    DEFAULT_WINDOW_FRACTION,
    ConvergenceWindow,
    compute_convergence,
    format_convergence_report,
)
from inp_tool.postprocess.info1 import Info1Step


# ============================================================================
# 默认常量
# ============================================================================

class TestDefaults:
    def test_threshold_is_0_001(self):
        """CV < 0.1% 视为收敛。"""
        assert DEFAULT_CV_THRESHOLD == 0.001

    def test_window_fraction_is_0_1(self):
        """末 10% 步作为收敛窗口。"""
        assert DEFAULT_WINDOW_FRACTION == 0.1

    def test_min_window_is_100(self):
        """窗口至少 100 步。"""
        assert DEFAULT_MIN_WINDOW == 100


# ============================================================================
# ConvergenceWindow dataclass
# ============================================================================

class TestConvergenceWindowDataclass:
    def test_field_access(self):
        cv = (0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001)
        conv = (True, True, True, True, True, True)
        w = ConvergenceWindow(n_total=1000, n_window=100, cv=cv,
                              converged=conv, all_converged=True)
        assert w.n_total == 1000
        assert w.n_window == 100
        assert w.all_converged is True
        assert all(c < 0.001 for c in w.cv)


# ============================================================================
# compute_convergence — 收敛 / 不收敛
# ============================================================================

def _make_constant_steps(n: int, value: float = 1.0) -> list:
    """N 步,所有分量都 = value(完美收敛)。"""
    return [
        Info1Step(
            step=i, time=float(i) * 0.001,
            total=(value, value, value, value, value, value),
            inv=(value,) * 6, vis=(0.0,) * 6,
        )
        for i in range(1, n + 1)
    ]


def _make_linear_steps(n: int, start: float = 1.0, slope: float = 0.01) -> list:
    """N 步,Fx 线性递增 → CV 大(不收敛)。其余分量保持常量。"""
    return [
        Info1Step(
            step=i, time=float(i) * 0.001,
            total=(start + slope * i, 1.0, 1.0, 1.0, 1.0, 1.0),
            inv=(start + slope * i, 1.0, 1.0, 1.0, 1.0, 1.0),
            vis=(0.0,) * 6,
        )
        for i in range(1, n + 1)
    ]


class TestComputeConvergenceConverged:
    def test_constant_100_steps_all_converged(self):
        steps = _make_constant_steps(100)
        result = compute_convergence(steps)
        assert result is not None
        assert result.n_total == 100
        assert result.all_converged is True
        for cv_val in result.cv:
            assert cv_val == pytest.approx(0.0, abs=1e-12)

    def test_constant_1000_steps_window_is_10_percent(self):
        """1000 步 → 末 100 步窗口(max(100, 1000//10) = 100)。"""
        steps = _make_constant_steps(1000)
        result = compute_convergence(steps)
        assert result is not None
        assert result.n_window == 100
        assert result.all_converged is True

    def test_constant_5000_steps_window_500(self):
        """5000 步 → 末 500 步窗口(max(100, 5000//10) = 500)。"""
        steps = _make_constant_steps(5000)
        result = compute_convergence(steps)
        assert result.n_window == 500


class TestComputeConvergenceNotConverged:
    def test_linear_drift_fx_not_converged(self):
        """Fx 线性递增,CV 显著 > 0.001。"""
        steps = _make_linear_steps(500, start=1.0, slope=0.01)
        result = compute_convergence(steps)
        assert result is not None
        # Fx (column 0) 不收敛
        assert result.converged[0] is False
        assert result.cv[0] > 0.001

    def test_linear_drift_other_components_still_converged(self):
        """其余分量为 1.0 常量 → 收敛。"""
        steps = _make_linear_steps(500, start=1.0, slope=0.01)
        result = compute_convergence(steps)
        assert result.all_converged is False  # 因为 Fx 不收敛
        # 但 Fy..Mz 应收敛
        for i in range(1, 6):
            assert result.converged[i] is True


class TestComputeConvergenceInsufficientData:
    """数据不足 → 返回 None,不抛错。"""

    def test_50_steps_returns_none(self):
        steps = _make_constant_steps(50)
        result = compute_convergence(steps)
        assert result is None

    def test_99_steps_returns_none(self):
        """min_window=100 → 99 步还差一步。"""
        steps = _make_constant_steps(99)
        result = compute_convergence(steps)
        assert result is None

    def test_empty_returns_none(self):
        assert compute_convergence([]) is None

    def test_exactly_100_steps_ok(self):
        steps = _make_constant_steps(100)
        result = compute_convergence(steps)
        assert result is not None


class TestComputeConvergenceCustomThreshold:
    def test_custom_threshold_makes_drift_pass(self):
        """加大漂移到默认阈值不收敛,放宽到 50% 应收敛。"""
        steps = _make_linear_steps(500, start=100.0, slope=0.1)
        # 默认阈值 0.001 应不收敛
        default = compute_convergence(steps)
        # 自定义阈值 0.5(50%)应收敛
        loose = compute_convergence(steps, threshold=0.5)
        assert default.converged[0] is False
        assert loose.converged[0] is True

    def test_custom_min_window(self):
        """min_window=20 → 30 步也能算。"""
        steps = _make_constant_steps(30)
        result = compute_convergence(steps, min_window=20)
        assert result is not None
        assert result.n_window == 20

    def test_custom_fraction(self):
        """fraction=0.5 + 1000 步 → 窗口 500。"""
        steps = _make_constant_steps(1000)
        result = compute_convergence(steps, fraction=0.5)
        assert result.n_window == 500


class TestComputeConvergenceMeanZero:
    """当一个分量的 mean 在窗口内 = 0,CV 公式必须不爆炸(0/0)。"""

    def test_mean_zero_returns_finite_cv(self):
        """Fx 全为 0 → mean=0,CV = 0(约定)。"""
        steps = [
            Info1Step(
                step=i, time=0.0,
                total=(0.0, 1.0, 1.0, 1.0, 1.0, 1.0),
                inv=(0.0, 1.0, 1.0, 1.0, 1.0, 1.0),
                vis=(0.0,) * 6,
            )
            for i in range(1, 101)
        ]
        result = compute_convergence(steps)
        # Fx mean = 0 → CV 应当是 0 或某 fallback,不能是 NaN/Inf
        assert result is not None
        assert result.cv[0] >= 0.0  # 不是 NaN


# ============================================================================
# format_convergence_report — 中文 UTF-8 报告
# ============================================================================

class TestFormatConvergenceReport:
    def test_empty_results_returns_string(self):
        result = format_convergence_report([])
        assert isinstance(result, str)
        # 头部应有标题(中文 UTF-8)
        assert "收敛" in result

    def test_single_converged_case(self):
        steps = _make_constant_steps(200)
        window = compute_convergence(steps)
        report = format_convergence_report([("case_01", window)])
        assert "case_01" in report
        assert "收敛" in report
        # 应该列出 6 个分量
        assert "Fx" in report
        assert "Mz" in report

    def test_single_not_converged_case(self):
        steps = _make_linear_steps(500, slope=0.1)
        window = compute_convergence(steps)
        report = format_convergence_report([("drift_case", window)])
        assert "drift_case" in report
        assert "未收敛" in report

    def test_none_window_handled(self):
        """``compute_convergence`` 返回 None → 报告应说明数据不足。"""
        report = format_convergence_report([("short_case", None)])
        assert "short_case" in report
        assert "数据" in report or "不足" in report

    def test_multi_case_report(self):
        s1 = _make_constant_steps(200)
        s2 = _make_linear_steps(300, slope=0.1)
        w1 = compute_convergence(s1)
        w2 = compute_convergence(s2)
        report = format_convergence_report([("case_a", w1), ("case_b", w2)])
        assert "case_a" in report
        assert "case_b" in report

    def test_utf8_encodable(self):
        """报告应能 UTF-8 编码无误(中文字符)。"""
        steps = _make_constant_steps(200)
        window = compute_convergence(steps)
        report = format_convergence_report([("case", window)])
        # 不抛 UnicodeEncodeError
        encoded = report.encode("utf-8")
        assert len(encoded) > 0
