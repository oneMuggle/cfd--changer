"""``inp_tool.postprocess`` 子包(v0.15.0)。

CFD++ 算例后处理:大气模型 / 坐标系变换 / ``mcfd.info1`` 解析 /
气动力汇总 / 收敛性分析 / Excel + 收敛图输出。

依赖边界(硬约束):
- 核心模块(``atmosphere`` / ``aero_math`` / ``bc`` / ``info1`` /
  ``forces`` / ``convergence``)零运行时依赖,只用 Python stdlib。
  ``aero_math`` 在 ``numpy`` 可用时走加速路径,否则纯 ``math`` 回退。
- 可选输出模块(``report`` / ``plot``)走 ``[post]`` extras
  (``openpyxl`` / ``matplotlib`` / ``numpy``),顶层不 import,
  调用方按需 ``from inp_tool.postprocess.report import write_excel``。

子包公共 API 按 Phase 推进逐步暴露。
"""
from __future__ import annotations

from .aero_math import (
    alpha_beta_to_uvw,
    body_to_wind,
    uvw_to_alpha_beta,
    wind_to_body,
)
from .atmosphere import (
    AtmosphereResult,
    atmosphere_us_1976,
    geometric_to_geopotential_km,
    reynolds_number,
    reynolds_number_at_altitude,
    sutherland_mu,
)
from .bc import (
    BcNameMap,
    op_label,
    parse_mcfd_bc,
)
from .convergence import (
    DEFAULT_CV_THRESHOLD,
    DEFAULT_MIN_WINDOW,
    DEFAULT_WINDOW_FRACTION,
    ConvergenceWindow,
    compute_convergence,
    format_convergence_report,
)
from .forces import (
    CoefficientRow,
    ForceReport,
    ForceSample,
    ForceSection,
    ReferenceGeometry,
    RunParams,
    build_run_params,
    compute_coefficients,
    shift_moment_to_ref,
    summarize_forces,
)
from .info1 import (
    Info1Step,
    find_total_force_file,
    is_viscous,
    read_info1,
)

__all__ = [
    # atmosphere
    "AtmosphereResult",
    "atmosphere_us_1976",
    "geometric_to_geopotential_km",
    "reynolds_number",
    "reynolds_number_at_altitude",
    "sutherland_mu",
    # aero_math
    "alpha_beta_to_uvw",
    "body_to_wind",
    "uvw_to_alpha_beta",
    "wind_to_body",
    # bc
    "BcNameMap",
    "op_label",
    "parse_mcfd_bc",
    # info1
    "Info1Step",
    "find_total_force_file",
    "is_viscous",
    "read_info1",
    # forces
    "CoefficientRow",
    "ForceReport",
    "ForceSample",
    "ForceSection",
    "ReferenceGeometry",
    "RunParams",
    "build_run_params",
    "compute_coefficients",
    "shift_moment_to_ref",
    "summarize_forces",
    # convergence
    "DEFAULT_CV_THRESHOLD",
    "DEFAULT_MIN_WINDOW",
    "DEFAULT_WINDOW_FRACTION",
    "ConvergenceWindow",
    "compute_convergence",
    "format_convergence_report",
]
