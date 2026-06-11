"""
v0.9.0:方程系统感知的 mcfd.inp 配置

提供:
- 能量模型检测(physics.tnoneq_numeqns → NONE/TWO_TEMP/THREE_TEMP)
- 湍流模型检测(顶层 seq.# 1 第 1 行 values 101 1 1 X Y → 6 枚举)
- 气体类型检测(gasnam 存在 / 顶层 infsets + species)
- 4 个湍流初始化 preset(SSTKOmega / RealizableKEpsilon / SA / GoldbergRT)
- 2 温度联动 preset(TwoTemperaturePreset,强校验 T_trans + T_vib)
- 多组分 preset(SpeciesPreset,mass↔mole 互转)

约定来源(2026-06-11 用户确认 + reference/inp_example/compare/ 实测 6 文件):
- tnoneq_numeqns 字段:0/1/2 → 完美气体/2-温度/3-温度(数 = 非平动温度方程数,不是总温度数)
- 湍流模型控制:顶层 seq.# 1 #vals 31 title eqnset_define 块第 1 行 `values 101 1 1 X Y`
  (X=0/1/2/3 = 方程家族,Y=家族内码)
- physics.ntrbst 不可靠(实测 6 算例全 = 11)
"""
from __future__ import annotations
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .model import InpFile, Stmt


# ============================================================
# 枚举
# ============================================================


class EnergyModel(str, Enum):
    """能量模型(对应 physics.tnoneq_numeqns 字段,**非平动温度方程数**)

    约定(用户 2026-06-11 确认):
    - tnoneq_numeqns == 0 → 完美气体(0 个非平动温度方程)
    - tnoneq_numeqns == 1 → 2-温度(1 个非平动温度方程,即振动)
    - tnoneq_numeqns == 2 → 3-温度(2 个非平动温度方程,v0.10+ scope)
    """
    NONE = "none"                # 完美气体
    TWO_TEMP = "2T"              # 2-温度(T_trans + T_vib)
    THREE_TEMP = "3T"            # 3-温度(+ T_elec,v0.10+ scope)
    UNKNOWN = "unknown"


class TurbulenceModel(str, Enum):
    """湍流模型。detection 基于顶层 `seq.# 1 #vals 31 title eqnset_define`
    块第 1 行 `values 101 1 1 X Y` 的 X(方程家族)+ Y(家族内码)。

    家族(由 X 决定):0=无(层流), 1=1-方程, 2=2-方程, 3=3-方程(留 v0.10+)。
    家族内码(由 Y 决定):不同家族含义不同(见下表)。

    实测(从 reference/inp_example/compare/ 6 个 mcfd.inp + cfd-gui 文档):
    - (0, 1) = LAMINAR
    - (1, 2) = GOLDBERG_RT
    - (1, 4) = SPALART_ALLMARAS
    - (2, 2) = REALIZABLE_KEPSILON
    - (2, 3) = SST_KW
    - (3, *) = v0.10+ scope(3-方程家族:k-eps-Rt, k-eps-fmu)
    """
    LAMINAR = "laminar"
    GOLDBERG_RT = "goldberg_rt"
    SPALART_ALLMARAS = "spalart-allmaras"
    SST_KW = "k-omega-sst"
    REALIZABLE_KEPSILON = "realizable-k-eps"
    UNKNOWN = "unknown"


class GasModel(str, Enum):
    """气体模型

    实测(从 reference/inp_example/compare/ 7 文件 + 用户 2026-06-11 确认):
    判定来源是顶层 `seq.# 1 #vals 31 title eqnset_define` 块**第 2 行**
    `values v6 ...` 的 v6:
    - v6 == 0  → PERFECT_GAS(可压缩理想气体)
    - v6 == 1  → REAL_GAS(可压缩真实气体 / 多组分)
    - v6 == 11 → MULTI_TEMP(双温热非平衡)— 与 physics.tnoneq_numeqns=1 互锁

    NOTE: 不要用 `physics.gasnam` 判别 — 实测 7 个文件全部有 `gasnam Air`
    (包括真实气体和双温),会造成误判。
    """
    PERFECT_GAS = "perfect-gas"
    REAL_GAS = "real-gas"
    MULTI_TEMP = "multi-temp"          # v0.9.1 新增(对应 v6=11 + tnoneq_numeqns=1)
    MIXTURE = "mixture"                # **v0.10+ 占位** — 当前 detect_equations 不会返回
                                       # (顶层 species_*.Mwt1_* 解析未实现)
    UNKNOWN = "unknown"


# ============================================================
# 数据类
# ============================================================


@dataclass
class SpeciesEntry:
    """顶层 species_*.Mwt1_NAME 解析出的 species"""
    name: str                    # "CO"
    mwts: List[float]            # [28.01] 通常 1 个;多 Mwt 时为多元素
    has_sutherland: bool
    has_cp: bool


@dataclass
class EquationSystemReport:
    """detect_equations 的输出,所有 preset 共享"""
    energy: EnergyModel                       # NONE / TWO_TEMP / THREE_TEMP / UNKNOWN
    turbulence: TurbulenceModel              # 6 枚举 + UNKNOWN
    gas: GasModel                             # PERFECT_GAS / REAL_GAS / MULTI_TEMP / MIXTURE / UNKNOWN
    n_species: int = 0                        # 顶层 infsets 解析出的 species 数
    species: List[SpeciesEntry] = field(default_factory=list)
    has_gasnam: bool = False                  # physics.gasnam 是否存在(仅参考,不用于判别)
    gasnam: Optional[str] = None              # "Air" / "CO2" / ...
    # 湍流原始索引(从 seq.# 1 第 1 行 values 取,用于追溯)
    ntrbst_family: Optional[int] = None       # X 值(0/1/2/3,即 eqnset_define v4)
    ntrbst_code: Optional[int] = None         # Y 值(家族内索引,即 eqnset_define v5)
    # 气体原始索引(v0.9.1 新增,从 eqnset_define 第 2 行第 0 位 v6 取)
    gas_code: Optional[int] = None            # 0=理想 / 1=真实 / 11=双温
    notes: List[str] = field(default_factory=list)  # 警告/说明

    def summary_zh(self) -> str:
        """给 wizard / REPL 显示的简短中文摘要"""
        return (
            f"能量={self.energy.value}  湍流={self.turbulence.value}"
            f"  气体={self.gas.value}  物种数={self.n_species}"
        )

    def recommended_fields(self) -> List[str]:
        """根据检测结果,推荐 wizard step_2 展示的字段集"""
        fields: List[str] = []
        if self.energy == EnergyModel.TWO_TEMP:
            fields += ["tnoneq_numeqns", "reftem (T_trans)", "vibtem (T_vib)"]
        elif self.energy == EnergyModel.NONE:
            # 完美气体:不主动推荐
            pass
        # 湍流模型推荐字段(每个湍流模型所需字段不同;v0.9.1 公式详见 §5.2)
        if self.turbulence in (TurbulenceModel.SST_KW,
                                TurbulenceModel.REALIZABLE_KEPSILON):
            fields += ["turbi_lev (k)", "turbi_len (L)",
                       "turbi_tlev (k/U²)", "turbi_tlen"]
        elif self.turbulence in (TurbulenceModel.SPALART_ALLMARAS,
                                  TurbulenceModel.GOLDBERG_RT):
            fields += ["turbi_lev (ν̃)", "turbi_len (L)"]
        if self.gas == GasModel.MIXTURE:
            fields += ["species 质量分率 (mass/mole)"]
        return fields


# ============================================================
# 湍流模型码映射表
# ============================================================
_MAP_TURBULENCE: Dict[Tuple[int, int], TurbulenceModel] = {
    (0, 1): TurbulenceModel.LAMINAR,                  # 层流(实测)
    (1, 2): TurbulenceModel.GOLDBERG_RT,               # 1-方程 Goldberg RT(实测)
    (1, 4): TurbulenceModel.SPALART_ALLMARAS,          # 1-方程 SA(实测)
    (2, 2): TurbulenceModel.REALIZABLE_KEPSILON,       # 2-方程 Realizable k-ε(实测)
    (2, 3): TurbulenceModel.SST_KW,                    # 2-方程 SST k-ω(实测)
    # (3, *) v0.10+ scope(k-eps-Rt, k-eps-fmu)
}


# ============================================================
# 气体类型码映射表(v0.9.1)
# ============================================================
# 数据源:reference/inp_example/compare/ 7 文件实测
# 位置:顶层 seq.# 1 #vals 31 title eqnset_define 块第 2 行第 0 位 (v6)
_MAP_GAS: Dict[int, GasModel] = {
    0:  GasModel.PERFECT_GAS,   # 可压缩理想气体(实测)
    1:  GasModel.REAL_GAS,      # 可压缩真实气体(实测 — 同位 v25 = 6 物种)
    11: GasModel.MULTI_TEMP,    # 双温热非平衡(实测 — 同时 tnoneq_numeqns = 1)
}


# ============================================================
# 工具函数
# ============================================================


def _find_eqnset_define(inp: InpFile) -> Optional[Stmt]:
    """找顶层 `seq.# 1 #vals 31 title eqnset_define` 复合头。

    parser 把该行解析为:
      stmt.keyword = "seq.#"
      stmt.values_raw = ["1"]        ← #vals/title 之后的部分被丢(已知 parser 行为)
      stmt.children   = [values 行, ...]   ← 后续 values 行作为 children

    parser 丢失了 title,无法用 title_substr 定位。本函数靠 children[0] 的
    "values 101 1 1 ..." 前缀匹配 eqnset_define(实测 reference 算例的固定模式)。
    """
    for s in inp.top_stmts:
        if not s.keyword.startswith("seq"):
            continue
        if s.children and s.children[0].values_raw[:3] == ["101", "1", "1"]:
            return s
    return None


def _get_values_lines(eqnset_stmt: Stmt) -> List[Stmt]:
    """从 seq.# 复合头拿后续 values 行(已在 parser 里存为 children)。"""
    return [c for c in eqnset_stmt.children if c.keyword == "values"]


# ============================================================
# 主检测器
# ============================================================


def detect_equations(inp: InpFile) -> EquationSystemReport:
    """扫描 InpFile 推断:
    1) 能量模型:physics.tnoneq_numeqns(0/1/2)
    2) 湍流模型:顶层 seq.# eqnset_define 块第 1 行 values 101 1 1 v4 v5
       (v4=方程家族 0/1/2/3, v5=家族内码;实测 physics.ntrbst 不可靠)
    3) 气体类型:顶层 seq.# eqnset_define 块第 2 行 values v6 ...
       (v6: 0=PERFECT_GAS / 1=REAL_GAS / 11=MULTI_TEMP)
       NOTE: 不再用 physics.gasnam 判别 — 实测 7 文件全部 gasnam=Air,会误判
    4) 物种数:顶层 infsets(实测 v0.9.1 简化,具体物种枚举留 v0.10+)
    """
    rep = EquationSystemReport(
        energy=EnergyModel.UNKNOWN,
        turbulence=TurbulenceModel.UNKNOWN,
        gas=GasModel.UNKNOWN,
    )

    # 1) 能量模型
    pb = inp.get_block("physics")
    if pb is not None:
        v = pb.get("tnoneq_numeqns")
        if v == 0:
            rep.energy = EnergyModel.NONE
        elif v == 1:
            rep.energy = EnergyModel.TWO_TEMP
        elif v == 2:
            rep.energy = EnergyModel.THREE_TEMP  # v0.10+ scope
        else:
            if v is not None:
                rep.notes.append(
                    f"physics.tnoneq_numeqns={v!r} 非预期值(v0.9.1 仅支持 0/1/2)"
                )
        # gasnam 仅作参考(实测 7 文件全 = Air,不可用于判别气体类型)
        gasnam_v = pb.get_value("gasnam")
        if gasnam_v is not None:
            rep.has_gasnam = True
            rep.gasnam = str(gasnam_v)

    # 2 + 3) 湍流模型 + 气体类型:扫顶层 seq.# eqnset_define 块
    eqnset_define_stmt = _find_eqnset_define(inp)
    if eqnset_define_stmt is not None:
        values_lines = _get_values_lines(eqnset_define_stmt)
        # 2) 湍流(第 1 行 values 101 1 1 v4 v5)
        if values_lines:
            x_y = values_lines[0].values_raw
            if len(x_y) >= 5 and x_y[0] == "101":
                try:
                    eq_count = int(x_y[3])
                    turb_code = int(x_y[4])
                    rep.ntrbst_family = eq_count
                    rep.ntrbst_code = turb_code
                    rep.turbulence = _MAP_TURBULENCE.get(
                        (eq_count, turb_code), TurbulenceModel.UNKNOWN
                    )
                    if rep.turbulence == TurbulenceModel.UNKNOWN:
                        if eq_count == 3:
                            rep.notes.append(
                                f"3-方程湍流家族(家族={eq_count},码={turb_code})"
                                f"留 v0.10+ scope"
                            )
                        else:
                            rep.notes.append(
                                f"未识别湍流模型:家族={eq_count},码={turb_code}"
                            )
                except ValueError as e:
                    rep.notes.append(f"eqnset_define 第 1 行 values 解析失败: {e}")
        # 3) 气体(第 2 行 values v6 ...)
        if len(values_lines) >= 2:
            row2 = values_lines[1].values_raw
            if row2:
                try:
                    gas_code = int(row2[0])
                    rep.gas_code = gas_code
                    rep.gas = _MAP_GAS.get(gas_code, GasModel.UNKNOWN)
                    if rep.gas == GasModel.UNKNOWN:
                        rep.notes.append(
                            f"未识别气体类型码 v6={gas_code}"
                            f"(v0.9.1 仅支持 0/1/11)"
                        )
                    # 一致性检查:v6=11 ↔ tnoneq_numeqns=1
                    if gas_code == 11 and rep.energy != EnergyModel.TWO_TEMP:
                        rep.notes.append(
                            f"eqnset_define v6=11 表示双温,但 tnoneq_numeqns"
                            f"={pb.get('tnoneq_numeqns') if pb else None!r} 不匹配"
                        )
                    if rep.energy == EnergyModel.TWO_TEMP and gas_code != 11:
                        rep.notes.append(
                            f"tnoneq_numeqns=1 表示双温,但 eqnset_define v6"
                            f"={gas_code} ≠ 11(可能不一致)"
                        )
                except ValueError as e:
                    rep.notes.append(f"eqnset_define 第 2 行 values 解析失败: {e}")

    # 4) 顶层 infsets(物种数;v0.9.1 简化:仅记数,不枚举)
    infsets_stmt = next(
        (s for s in inp.top_stmts if s.keyword == "infsets"), None
    )
    if infsets_stmt is not None and infsets_stmt.values:
        n_v = infsets_stmt.values[0].typed
        if isinstance(n_v, int) and n_v > 0:
            rep.n_species = n_v
            # 若 v0.10+ 引入 species 显式声明(顶层 species_*.Mwt1_*),
            # 则把 gas 从 REAL_GAS 升级为 MIXTURE — v0.9.1 不做(infsets 不等于 species)

    return rep


# ============================================================
# 异常类
# ============================================================


class TwoTemperatureError(ValueError):
    """2-温度模型需要 T_trans + T_vib 同时给,缺一抛此异常。"""
    pass


class SpeciesNotFoundError(KeyError):
    """SpeciesPreset 给的 species 名不在 inp 已声明的 species 列表中。"""
    pass


class GasModelError(ValueError):
    """SpeciesPreset 应用于非 MIXTURE inp 时抛。"""
    pass


# ============================================================
# v0.10.0 新增:方程改写异常 + issue(spec §4.2)
# ============================================================


class EquationRewriteError(ValueError):
    """set_*_model 写不进去或一致性破坏时抛。"""
    pass


@dataclass
class EquationRewriteIssue:
    """写完后追加到 inp.notes 列表;generate 末尾聚合。

    复用 v0.9.0 PbsIssue 字段结构(severity/code/message)。
    """
    severity: str
    code: str
    message: str

    def __post_init__(self) -> None:
        if self.severity not in ("error", "warning"):
            raise ValueError(
                f"severity must be 'error' or 'warning', got {self.severity!r}"
            )

    def __repr__(self) -> str:
        return f"[{self.severity}] {self.code}: {self.message}"


# ============================================================
# 湍流初始化 preset 基类 + 4 子类
# ============================================================


@dataclass
class TurbulencePresetBase(ABC):
    """湍流初始化 preset 基类。

    子类必须实现:
    - family: TurbulenceModel(1-方程 / 2-方程)
    - compute() -> Dict[str, float]: 算湍流参数

    共同约束:
    - I ∈ [0, 1]
    - L > 0
    - U_ref > 0
    """
    I: float = 0.01                          # 湍流强度(0.01 = 1%)
    L: float = 0.01                          # 特征长度 [m]
    U_ref: float = 1.0                        # 参考速度 [m/s](通常 = refvel / aero_u)
    Cmu: float = 0.09                         # SST/k-ε 共用默认系数
    # guiopts 字段键(子类可覆盖)
    turbi_lev_key: str = "turbi_lev"          # 写"特征量"(k / ν̃)
    turbi_len_key: str = "turbi_len"          # 写"长度尺度"
    turbi_tlev_key: str = "turbi_tlev"        # 写"特征量"无量纲比例(2-方程用)
    turbi_tlen_key: str = "turbi_tlen"        # 写"长度"或 ε(Realizable k-ε)

    def _validate(self) -> None:
        if not (0 <= self.I <= 1):
            raise ValueError(f"turbulence intensity I must be in [0,1], got {self.I!r}")
        if self.L <= 0:
            raise ValueError(f"length scale L must be > 0, got {self.L!r}")
        if self.U_ref <= 0:
            raise ValueError(f"reference velocity U_ref must be > 0, got {self.U_ref!r}")

    @property
    @abstractmethod
    def family(self) -> TurbulenceModel:
        """返回本 preset 对应的湍流模型。"""
        raise NotImplementedError

    @abstractmethod
    def compute(self) -> Dict[str, float]:
        """算湍流参数。返回 dict {guiopts_field_name: float}。"""
        raise NotImplementedError

    def apply(self, inp: InpFile) -> Dict[str, Any]:
        """写入 guiopts 块;返回 applied 字典供 undo / manifest。"""
        self._validate()
        gb = inp.get_block("guiopts")
        if gb is None:
            raise ValueError(
                "template has no `guiopts` block; cannot apply turbulence preset"
            )
        values = self.compute()
        applied: Dict[str, Any] = {}
        for field_key, value in values.items():
            if gb.set(field_key, value):
                applied[f"guiopts.{field_key}"] = value
            else:
                gb.append(field_key, value)
                applied[f"guiopts.{field_key}"] = value
        return applied


@dataclass
class SSTKOmegaPreset(TurbulencePresetBase):
    """SST k-ω(Menter 1994)初始化。给 I, L, U_ref 算 k, ω。"""

    @property
    def family(self) -> TurbulenceModel:
        return TurbulenceModel.SST_KW

    def compute(self) -> Dict[str, float]:
        self._validate()
        k = 1.5 * (self.U_ref * self.I) ** 2          # 湍动能 [m²/s²]
        omega = math.sqrt(k) / (self.Cmu ** 0.25 * self.L)  # Wilcox 2006 Eq.2.49
        return {
            "turbi_lev": k,                              # 写 k
            "turbi_tlev": k / (0.5 * self.U_ref ** 2),   # k/U²(无量纲)
            "turbi_len": self.L,
            "turbi_tlen": omega,                         # tlen 存 ω
        }


@dataclass
class RealizableKEpsilonPreset(TurbulencePresetBase):
    """Realizable k-ε(Shih et al. 1995)初始化。给 I, L, U_ref 算 k, ε。

    ε = Cμ^0.75 · k^1.5 / L
    """
    C2: float = 1.9                              # 模型常数(Shih 1995)
    sigma_eps: float = 1.2                        # σ_ε(可调)

    @property
    def family(self) -> TurbulenceModel:
        return TurbulenceModel.REALIZABLE_KEPSILON

    def compute(self) -> Dict[str, float]:
        self._validate()
        k = 1.5 * (self.U_ref * self.I) ** 2
        l = self.L
        eps = (self.Cmu ** 0.75) * (k ** 1.5) / l
        return {
            "turbi_lev": k,
            "turbi_tlev": k / (0.5 * self.U_ref ** 2),
            "turbi_len": self.L,
            "turbi_tlen": eps,                          # tlen 存 ε
        }


@dataclass
class SpalartAllmarasPreset(TurbulencePresetBase):
    """SA(Spalart-Allmaras 1994)初始化。给 I, L, U_ref 算 ν̃。

    v0.9.1 简化估计:ν̃ ≈ √k · L / 100(v0.10 用更精确公式)
    """
    Cb1: float = 0.1355                          # SA 模型常数
    Cv1: float = 7.1

    @property
    def family(self) -> TurbulenceModel:
        return TurbulenceModel.SPALART_ALLMARAS

    def compute(self) -> Dict[str, float]:
        self._validate()
        k = 1.5 * (self.U_ref * self.I) ** 2
        nu_tilde = math.sqrt(k) * self.L / 100.0     # 简化估计
        return {
            "turbi_lev": nu_tilde,                     # SA: lev 存 ν̃
            "turbi_len": self.L,
        }


@dataclass
class GoldbergRTPreset(TurbulencePresetBase):
    """Goldberg Reynolds Transport 1-方程 模型初始化。

    v0.9.1 简化:同 SA(ν̃ ≈ √k · L / 100),v0.10 用更精确 Goldberg 公式
    """
    @property
    def family(self) -> TurbulenceModel:
        return TurbulenceModel.GOLDBERG_RT

    def compute(self) -> Dict[str, float]:
        self._validate()
        k = 1.5 * (self.U_ref * self.I) ** 2
        nu_tilde = math.sqrt(k) * self.L / 100.0
        return {
            "turbi_lev": nu_tilde,
            "turbi_len": self.L,
        }


def make_turbulence_preset(model: TurbulenceModel, I: float, L: float, U_ref: float = 1.0):
    """从 TurbulenceModel + 用户给定 I/L/U_ref 选对应 preset。"""
    factory = {
        TurbulenceModel.SST_KW: SSTKOmegaPreset,
        TurbulenceModel.REALIZABLE_KEPSILON: RealizableKEpsilonPreset,
        TurbulenceModel.SPALART_ALLMARAS: SpalartAllmarasPreset,
        TurbulenceModel.GOLDBERG_RT: GoldbergRTPreset,
    }
    if model not in factory:
        if model == TurbulenceModel.LAMINAR:
            raise ValueError(
                "laminar has no turbulence preset (no 湍流 init needed)"
            )
        raise ValueError(
            f"no preset for {model.value}; v0.9.1 supports SST / k-ε / SA / Goldberg"
        )
    return factory[model](I=I, L=L, U_ref=U_ref)


# ============================================================
# 2 温度联动 preset
# ============================================================


@dataclass
class TwoTemperaturePreset:
    """2 温度(2T)非平衡能量模型联动 preset。

    强约束:T_trans(平动温度)和 T_vib(振动温度)必须**同时**给(物理上 2T 模型
    两者都是独立变量);缺一抛 TwoTemperatureError。
    """
    T_trans: Optional[float] = None            # 平动温度 [K]
    T_vib: Optional[float] = None              # 振动温度 [K]
    set_numeqns: bool = True                   # 是否自动设 tnoneq_numeqns=1(启用 2T)

    def apply(self, inp: InpFile) -> Dict[str, Any]:
        if self.T_trans is None or self.T_vib is None:
            raise TwoTemperatureError(
                "2T model requires BOTH T_trans and T_vib. "
                f"got T_trans={self.T_trans!r}, T_vib={self.T_vib!r}"
            )
        if self.T_trans <= 0 or self.T_vib <= 0:
            raise ValueError(
                f"temperatures must be > 0 K "
                f"(got T_trans={self.T_trans}, T_vib={self.T_vib})"
            )
        pb = inp.get_block("physics")
        if pb is None:
            raise ValueError("template has no `physics` block; cannot apply 2T preset")
        applied: Dict[str, Any] = {}
        if self.set_numeqns:
            if pb.set("tnoneq_numeqns", 1):
                applied["physics.tnoneq_numeqns"] = 1
            else:
                pb.append("tnoneq_numeqns", 1)
                applied["physics.tnoneq_numeqns"] = 1
        # 平动温度
        if pb.set("reftem", self.T_trans):
            applied["physics.reftem"] = self.T_trans
        else:
            pb.append("reftem", self.T_trans)
            applied["physics.reftem"] = self.T_trans
        # 振动温度(约定字段名 vibtem;若用户用其他字段名留 v0.10 适配)
        if pb.set("vibtem", self.T_vib):
            applied["physics.vibtem"] = self.T_vib
        else:
            pb.append("vibtem", self.T_vib)
            applied["physics.vibtem"] = self.T_vib
        return applied


# ============================================================
# 多组分 preset
# ============================================================


@dataclass
class SpeciesPreset:
    """多组分物性 preset。

    ⚠️ **v0.10+ scope — 当前 v0.9.1 不可达**:
    `detect_equations` 不会把 `gas` 升级为 `GasModel.MIXTURE`(顶层
    `species_*.Mwt1_*` 解析未实现,详见 `EquationSystemReport.species` 字段
    docstring)。因此 `SpeciesPreset.apply` 在任何真实 .inp 上都会抛
    `GasModelError`。

    本类的 mass↔mole 换算逻辑(`convert`)已实现并经过单元测试覆盖,
    可在 v0.10 加入物种枚举后直接复用。

    给定 {species_name: fraction},mode ∈ {"mass","mole"},自动:
    1) mass ↔ mole 互转(用每个 species 的 Mwt)
    2) 归一化(总和 → 1.0)
    """
    fractions: Dict[str, float] = field(default_factory=dict)
    mode: str = "mass"                        # "mass" or "mole"
    tol: float = 1e-9

    def _resolve_mwts(self, rep: EquationSystemReport) -> Dict[str, float]:
        """从 rep.species 拿每个 species 的 Mwt(取第一个 mwts 元素)。"""
        return {s.name: s.mwts[0] for s in rep.species if s.mwts}

    def _validate_fractions(self, mwts: Dict[str, float]) -> None:
        unknown = set(self.fractions) - set(mwts)
        if unknown:
            raise SpeciesNotFoundError(
                f"species {sorted(unknown)!r} not declared in InpFile; "
                f"known: {sorted(mwts)!r}"
            )
        total = sum(self.fractions.values())
        if total <= 0:
            raise ValueError(f"fractions sum to {total}, must be > 0")

    def convert(self, rep: EquationSystemReport) -> Dict[str, float]:
        """归一化 + mass↔mole 换算。返回 {name: mass_fraction}。"""
        if not rep.species:
            raise SpeciesNotFoundError("no species found in InpFile; cannot apply")
        mwts = self._resolve_mwts(rep)
        self._validate_fractions(mwts)
        # 归一化输入
        total = sum(self.fractions.values())
        norm = {k: v / total for k, v in self.fractions.items()}
        if self.mode == "mass":
            # mass 模式直接归一化结果(不反转)
            return norm
        elif self.mode == "mole":
            # mole → mass: Y_i = X_i * M_i / Σ(X_j * M_j)
            denom = sum(norm[n] * mwts[n] for n in norm)
            return {n: norm[n] * mwts[n] / denom for n in norm}
        else:
            raise ValueError(f"mode must be 'mass' or 'mole', got {self.mode!r}")

    def apply(self, inp: InpFile) -> Dict[str, Any]:
        """convert + 写顶层 mass fracs 行(v0.9.1 简化为仅 convert,写字段留 v0.10)"""
        rep = detect_equations(inp)
        if rep.gas != GasModel.MIXTURE:
            raise GasModelError(
                f"inp is not a multi-species mixture (gas={rep.gas.value}); "
                f"SpeciesPreset requires infsets + species_*.Mwt1_* structure"
            )
        mass = self.convert(rep)
        # v0.9.1 简化:apply 只返回换算结果,不写文件(写顶层 infsets 留 v0.10)
        return {"top_stmts": mass}


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    # 枚举
    "EnergyModel",
    "TurbulenceModel",
    "GasModel",
    # 数据类
    "SpeciesEntry",
    "EquationSystemReport",
    # 异常
    "TwoTemperatureError",
    "SpeciesNotFoundError",
    "GasModelError",
    "EquationRewriteError",
    "EquationRewriteIssue",
    # 检测器
    "detect_equations",
    # 湍流 preset
    "TurbulencePresetBase",
    "SSTKOmegaPreset",
    "RealizableKEpsilonPreset",
    "SpalartAllmarasPreset",
    "GoldbergRTPreset",
    "make_turbulence_preset",
    # 2 温度
    "TwoTemperaturePreset",
    # 多组分
    "SpeciesPreset",
]
