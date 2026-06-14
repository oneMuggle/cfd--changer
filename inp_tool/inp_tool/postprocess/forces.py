"""气动力汇总:从 mcfd.inp 读来流参数 + 从 mcfd.info1 取末步力 → 系数。

零运行时依赖,纯 Python stdlib(``math`` + ``dataclasses`` + ``pathlib``)。

参考实现:reference/code/CFDPlus_V4.py:838-976 + CFDPlus_extract.py:377-446

数据流::

    mcfd.inp                 mcfd.bc              mcfd.info1
       │                        │                      │
       ▼                        ▼                      ▼
    build_run_params      parse_mcfd_bc         read_info1(op_ibd)
       │ RunParams(9)        │ BcNameMap         │ list[Info1Step]
       │                     │                   │ 取末步 [-1]
       ▼                     ▼                   ▼
              shift_moment_to_ref + compute_coefficients
                              │
                              ▼
                       CoefficientRow / ForceReport

API 设计要点:
- ``RunParams`` 9 字段对应 reference ``runpara`` 9 列(Ma/H/α/β/Q/Re/intyp/P/T)
- ``ForceSample`` 6 元 (Fx, Fy, Fz, Mx, My, Mz)
- ``ForceSection`` (total, inv, vis) — 每个都是 ``ForceSample``
- ``CoefficientRow`` 28 列(完全对应 reference Excel 输出表头)
- ``shift_moment_to_ref`` 仅平移力矩,不动力
- ``compute_coefficients`` 内部自动调 ``shift_moment_to_ref``,然后算系数
- ``summarize_forces`` 高层:遍历 case_dir → 自动找 mcfd.inp + mcfd.info1 → 末步系数
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence, Union

from ..parser import parse_file
from .aero_math import uvw_to_alpha_beta
from .atmosphere import sutherland_mu
from .info1 import read_info1

# 干空气比气体常数(US 1976 标准)
_R_SPECIFIC = 287.0531

# 数值安全阈值
_EPS_Q_SREF = 1e-12  # Q·Sref 防 0 除
_EPS_DRAG = 1e-10    # |D| 防 0 除(L/D)
_EPS_FZ = 1e-10      # |Fz| 防 0 除(Xcp)


# ============================================================================
# Dataclasses
# ============================================================================

@dataclass(frozen=True)
class RunParams:
    """单算例的来流参数 + 衍生量(从 mcfd.inp 提取并补全)。

    字段:
    - ``Ma``: 马赫数
    - ``H``: geopotential 高度(km,intyp=0 时为 0)
    - ``alpha``: 攻角(度)
    - ``beta``: 侧滑角(度)
    - ``Q``: 动压(Pa)= 0.5·ρ·V²
    - ``Re``: 单位 Reynolds 数(/m)= ρ·V/μ
    - ``P``: 来流压强(Pa)
    - ``T``: 来流温度(K)
    - ``intyp``: 来流参数设置方式(0/1/3 — reference 约定)
    """
    Ma: float
    H: float
    alpha: float
    beta: float
    Q: float
    Re: float
    P: float
    T: float
    intyp: int


@dataclass(frozen=True)
class ForceSample:
    """6 自由度力/矩样本 ``(Fx, Fy, Fz, Mx, My, Mz)``,单位 N / N·m。"""
    Fx: float
    Fy: float
    Fz: float
    Mx: float
    My: float
    Mz: float


@dataclass(frozen=True)
class ForceSection:
    """单 step / 单 op 的 3 类力/矩(total / inviscid / viscous)。"""
    total: ForceSample
    inv: ForceSample
    vis: ForceSample


@dataclass(frozen=True)
class ReferenceGeometry:
    """参考几何:Sref/Lref 必须,Xref/Yref/Zref 默认 0(力矩中心在原点)。

    - ``Sref``: 参考面积(m²)
    - ``Lref``: 参考长度(m)
    - ``Xref / Yref / Zref``: 平移到的新力矩中心(m)
    """
    Sref: float
    Lref: float
    Xref: float = 0.0
    Yref: float = 0.0
    Zref: float = 0.0


@dataclass(frozen=True)
class CoefficientRow:
    """单算例的气动汇总行(reference Excel 输出表头一一对应)。"""
    case: str
    Ma: float
    H: float
    alpha_deg: float
    beta_deg: float
    Fx: float
    Fy: float
    Fz: float
    Mx: float      # 已平移到 (Xref, Yref, Zref)
    My: float
    Mz: float
    D: float
    L: float
    CD: float
    CY: float
    CL: float
    Cmx: float
    Cmy: float
    Cmz: float
    L_over_D: float
    Xcp: float
    Xcg: float
    Sref: float
    Lref: float
    Q: float
    Re: float
    P: float
    T: float


@dataclass(frozen=True)
class ForceReport:
    """``summarize_forces`` 的返回值:所有 case 的 ``CoefficientRow`` 集合。"""
    rows: List[CoefficientRow] = field(default_factory=list)


# ============================================================================
# 公共 API:build_run_params
# ============================================================================

# mcfd.inp 中 aero_* 字段所在 block(reference/full_case/Case 实测)
_AERO_BLOCK = "guiopts"

# aero_* 字段默认值(reference 行为)
_AERO_DEFAULTS = {
    "aero_intyp": 0,
    "aero_ma": 0.0,
    "aero_altid": 0.0,
    "aero_alpha": 0.0,
    "aero_beta": 0.0,
    "aero_pres": 0.0,
    "aero_temp": 0.0,
    "aero_u": 0.0,
    "aero_v": 0.0,
    "aero_w": 0.0,
    "aero_re": 0.0,
}


def build_run_params(inp_path: Union[str, Path]) -> RunParams:
    """从 mcfd.inp 读 aero_* 字段,构造 :class:`RunParams`。

    intyp=3 时从 (u, v, w) 反推 alpha / beta(与 reference 行为一致);
    其他 intyp 直接采纳 inp 中的 alpha / beta 值。

    Q 和 Re 走理想气体律 + Sutherland 公式:
    - ρ = P / (R·T),R = 287.0531 J/(kg·K)
    - V = sqrt(u² + v² + w²)
    - Q = 0.5·ρ·V²
    - Re = ρ·V / μ(T)

    若文件不存在抛 ``FileNotFoundError``。
    """
    p = Path(inp_path)
    if not p.is_file():
        raise FileNotFoundError(f"mcfd.inp not found: {p}")

    inp = parse_file(str(p))

    # 取 aero_* 字段(走 guiopts block);缺字段用默认值
    fields = {}
    for key, default in _AERO_DEFAULTS.items():
        v = inp.get(_AERO_BLOCK, key)
        fields[key] = v if v is not None else default

    intyp = int(fields["aero_intyp"])
    Ma = float(fields["aero_ma"])
    H = float(fields["aero_altid"])
    alpha = float(fields["aero_alpha"])
    beta = float(fields["aero_beta"])
    P = float(fields["aero_pres"])
    T = float(fields["aero_temp"])
    u = float(fields["aero_u"])
    v = float(fields["aero_v"])
    w = float(fields["aero_w"])

    # intyp=3: 从 uvw 反推 alpha / beta(度)
    if intyp == 3:
        alpha, beta = uvw_to_alpha_beta(u, v, w)

    # 动压 + Reynolds
    vel = math.sqrt(u * u + v * v + w * w)
    if T > 0.0 and P > 0.0:
        rho = P / (_R_SPECIFIC * T)
        Q = 0.5 * rho * vel * vel
        mu = sutherland_mu(T)
        Re = rho * vel / mu if mu > 0.0 else 0.0
    else:
        Q = 0.0
        Re = 0.0

    return RunParams(
        Ma=Ma, H=H, alpha=alpha, beta=beta,
        Q=Q, Re=Re, P=P, T=T, intyp=intyp,
    )


# ============================================================================
# 公共 API:shift_moment_to_ref
# ============================================================================

def shift_moment_to_ref(force: ForceSample,
                        ref_geom: ReferenceGeometry) -> ForceSample:
    """把力矩中心从 (0, 0, 0) 平移到 (Xref, Yref, Zref)。

    力分量不变;力矩按 ``M_new = M_old + r × F`` 平移,其中
    ``r = (Xref, Yref, Zref) - (0, 0, 0)``::

        Mx_new = Mx + Zref·Fy − Yref·Fz
        My_new = My + Xref·Fz − Zref·Fx
        Mz_new = Mz + Yref·Fx − Xref·Fy
    """
    Xr, Yr, Zr = ref_geom.Xref, ref_geom.Yref, ref_geom.Zref
    return ForceSample(
        Fx=force.Fx,
        Fy=force.Fy,
        Fz=force.Fz,
        Mx=force.Mx + Zr * force.Fy - Yr * force.Fz,
        My=force.My + Xr * force.Fz - Zr * force.Fx,
        Mz=force.Mz + Yr * force.Fx - Xr * force.Fy,
    )


# ============================================================================
# 公共 API:compute_coefficients
# ============================================================================

def compute_coefficients(force: ForceSample,
                         params: RunParams,
                         ref_geom: ReferenceGeometry,
                         case_name: str,
                         xcg: float = 0.0) -> CoefficientRow:
    """从原始力 + 来流参数 + 参考几何,算出系数 + 衍生量。

    内部先调 :func:`shift_moment_to_ref` 把力矩平移到 (Xref,Yref,Zref),
    然后:
    - CD/CY/CL = (Fx/Fy/Fz) / (Q·Sref)(Q·Sref < 1e-12 时返回 0)
    - Cmx/Cmy/Cmz = (Mx_shifted/My_shifted/Mz_shifted) / (Q·Sref·Lref)
    - D = Fx·cos α + Fz·sin α
    - L = -Fx·sin α + Fz·cos α
    - L/D = L/D(|D| < 1e-10 时返回 0)
    - Xcp = Xref - My_shifted / Fz(|Fz| < 1e-10 时返回 0)

    ``xcg``:重心 X 坐标,只填进 ``CoefficientRow.Xcg`` 字段(不参与计算),默认 0.0。
    """
    shifted = shift_moment_to_ref(force, ref_geom)

    Q_S = params.Q * ref_geom.Sref
    Q_S_L = Q_S * ref_geom.Lref

    if Q_S > _EPS_Q_SREF:
        CD = shifted.Fx / Q_S
        CY = shifted.Fy / Q_S
        CL = shifted.Fz / Q_S
    else:
        CD = 0.0
        CY = 0.0
        CL = 0.0

    if Q_S_L > _EPS_Q_SREF:
        Cmx = shifted.Mx / Q_S_L
        Cmy = shifted.My / Q_S_L
        Cmz = shifted.Mz / Q_S_L
    else:
        Cmx = 0.0
        Cmy = 0.0
        Cmz = 0.0

    alpha_rad = math.radians(params.alpha)
    D = shifted.Fx * math.cos(alpha_rad) + shifted.Fz * math.sin(alpha_rad)
    L = -shifted.Fx * math.sin(alpha_rad) + shifted.Fz * math.cos(alpha_rad)
    L_over_D = L / D if abs(D) > _EPS_DRAG else 0.0
    Xcp = (ref_geom.Xref - shifted.My / shifted.Fz) if abs(shifted.Fz) > _EPS_FZ else 0.0

    return CoefficientRow(
        case=case_name,
        Ma=params.Ma, H=params.H,
        alpha_deg=params.alpha, beta_deg=params.beta,
        Fx=shifted.Fx, Fy=shifted.Fy, Fz=shifted.Fz,
        Mx=shifted.Mx, My=shifted.My, Mz=shifted.Mz,
        D=D, L=L,
        CD=CD, CY=CY, CL=CL,
        Cmx=Cmx, Cmy=Cmy, Cmz=Cmz,
        L_over_D=L_over_D,
        Xcp=Xcp, Xcg=xcg,
        Sref=ref_geom.Sref, Lref=ref_geom.Lref,
        Q=params.Q, Re=params.Re,
        P=params.P, T=params.T,
    )


# ============================================================================
# 公共 API:summarize_forces
# ============================================================================

def summarize_forces(case_dirs: Sequence[Union[str, Path]],
                     op_ibd: Sequence[int],
                     ref_geom: ReferenceGeometry,
                     xcg: float = 0.0) -> ForceReport:
    """高层 API:遍历多个算例目录,对每个算例:

    1. 读 ``mcfd.inp`` 算 :class:`RunParams`
    2. 读 ``mcfd.info1`` 拿 op_ibd 上的力历程,取末步力(``steps[-1].total``)
    3. 平移力矩 + 算系数
    4. 收集进 :class:`ForceReport`

    缺 ``mcfd.inp`` 或 ``mcfd.info1`` 的目录跳过(不抛错),最终返回有效结果。

    ``xcg`` 当前透传到 :class:`CoefficientRow.Xcg` 字段。
    """
    rows: List[CoefficientRow] = []
    for case_dir in case_dirs:
        d = Path(case_dir)
        inp_path = d / "mcfd.inp"
        info1_path = d / "mcfd.info1"
        if not inp_path.is_file() or not info1_path.is_file():
            continue

        run_params = build_run_params(inp_path)
        steps = read_info1(info1_path, op_ibd)
        if not steps:
            continue

        last = steps[-1]
        force = ForceSample(
            Fx=last.total[0], Fy=last.total[1], Fz=last.total[2],
            Mx=last.total[3], My=last.total[4], Mz=last.total[5],
        )
        row = compute_coefficients(force, run_params, ref_geom,
                                   case_name=d.name, xcg=xcg)
        rows.append(row)

    return ForceReport(rows=rows)
