"""
mcfd.inp sweep 批量算例生成器 v0.1

基于一个 mcfd.inp 样例,通过 (alpha, beta, mach, ...) 扫描,生成 N 个变体。
- FreestreamPreset: 几何分解 (alpha, beta, Ma) -> (U, V, W) + refvel
- SweepSpec: 笛卡尔积展开
- render_case_name: 命名模板
- CaseResult / SweepReport: 结果聚合
- CopyStrategy (v0.8.0):整算例目录复制策略
"""
from __future__ import annotations
import copy
import enum
import hashlib
import math
import os
import re
import shutil
import sys
import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .model import InpFile
from .parser import parse_file
from .writer import write as write_inp
from .equations import (
    TurbulenceModel, EnergyModel, GasModel,
)


# 一个 sweep 轴的值可以是标量或列表
SweepValue = Union[int, float, str, List[Union[int, float, str]]]


# ============================================================
# v0.8.0:CopyStrategy + 整算例目录生成
# ============================================================
class CopyStrategy(str, enum.Enum):
    """整算例目录复制策略(per_dir 模式)"""
    COPY = "copy"          # shutil.copy2(慢,占空间)
    HARDLINK = "hardlink"  # os.link(快,零空间,跨 inode 但同 FS)— 默认
    SYMLINK = "symlink"    # os.symlink(零空间,跨 FS,Windows 需 dev mode)


# 默认排除规则:基础算例目录里"不该被打包进子算例"的文件
DEFAULT_EXCLUDE: List[str] = [
    "*.bak",         # 备份
    "*.BAK",
    "mlog",          # 上次运行的日志目录
    "nodesout.bin",  # 求解器输出(下次跑会被覆写)
    "*.log",         # 通用日志
]


# ============================================================
# v0.9.0 新增:pbs 完整性错误
# ============================================================
class SweepValidationError(Exception):
    """sweep 完整性检查失败时抛的异常。"""
    def __init__(self, issues):
        self.issues = issues
        super().__init__(
            f"基础算例完整性检查失败,{len([i for i in issues if i.severity == 'error'])} 个 error:\n"
            + "\n".join(f"  [{i.code}] {i.message}" for i in issues if i.severity == "error")
        )


def extract_pbs_basename(template_path: str, max_len: int = 8) -> str:
    """从 pbs 模板里读 #PBS -N 提取 base basename,截到 max_len 字符。
    若模板无 #PBS -N 或文件读不到,返回 "case" 作为 fallback。
    """
    import re
    p = Path(template_path)
    if not p.is_file():
        return "case"
    try:
        text = p.read_text()
    except OSError:
        return "case"
    m = re.search(r"^[ \t]*#PBS[ \t]+-N[ \t]+(\S+)", text, re.MULTILINE)
    if not m:
        return "case"
    name = m.group(1)
    if len(name) > max_len:
        name = name[:max_len]
    return name


def _resolve_layout(sweep: "CaseSweep") -> str:
    """根据 source_dir 是否设置决定输出布局。

    Returns:
        "flat"    — source_dir 未设,每个 case = 1 个 .inp 文件(v0.7.x 行为)
        "per_dir" — source_dir 有值,每个 case = 1 个子目录(完整算例)
    """
    return "per_dir" if sweep.source_dir else "flat"


@dataclass
class SweepSpec:
    """扫描定义:每个 key 是一个轴,值是它的取值列表(或单值)"""
    values: Dict[str, SweepValue] = field(default_factory=dict)

    def values_keys(self) -> List[str]:
        return list(self.values.keys())


@dataclass
class EquationSwitches:
    """v0.10.0 新增:方程改写开关(默认全 True,切)。"""
    turbulence: bool = True
    energy: bool = True
    gas: bool = True

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, bool]]) -> "EquationSwitches":
        if d is None:
            return cls()
        return cls(
            turbulence=bool(d.get("turbulence", True)),
            energy=bool(d.get("energy", True)),
            gas=bool(d.get("gas", True)),
        )


# ============================================================
# PR #1:CaseSpec 抽象(显式 / 分组 / 笛卡尔的统一归一化)
# ============================================================
@dataclass
class CartesianSpec:
    """笛卡尔轴集合(由 sweeps 字段生成,经 expand_cartesian 展开)

    与现有 SweepSpec 的关系:CartesianSpec.axes 是 SweepSpec.values
    的轻量包装。这里 axes 直接持有原 axes(单值轴对笛卡尔无意义,
    由 expand_cartesian 把单值扩展为 1 元素列表)。
    """
    axes: Dict[str, List[float]]


@dataclass
class ExplicitCase:
    """单个完整 case(显式 / 分组 / CSV 路径的最终归一化形式)

    values: 完整 key→数值(已合并 common + per-case 覆盖)
    group:  分组名(用于 {group} 命名占位);未分组时为 None
    """
    values: Dict[str, float]
    group: Optional[str] = None


def _normalize_axis(v: SweepValue) -> List[Any]:
    """把标量/列表统一为列表"""
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


# ============================================================
# v0.10.0 新增:枚举轴识别(spec §4.1)
# ============================================================
_ENUM_AXES: Dict[str, type] = {
    "turbulence": TurbulenceModel,
    "energy": EnergyModel,
    "gas": GasModel,
}

# 短名别名(常见缩写 → enum.value)
# 容忍 CLI/YAML 用户写短名(如 "sst" 而非 "k-omega-sst")。
_ENUM_ALIASES: Dict[type, Dict[str, str]] = {
    TurbulenceModel: {
        "sst": TurbulenceModel.SST_KW.value,
        "sa": TurbulenceModel.SPALART_ALLMARAS.value,
        "ke": TurbulenceModel.REALIZABLE_KEPSILON.value,
        "keps": TurbulenceModel.REALIZABLE_KEPSILON.value,
        "goldberg": TurbulenceModel.GOLDBERG_RT.value,
        "laminar": TurbulenceModel.LAMINAR.value,
    },
    EnergyModel: {
        "2t": EnergyModel.TWO_TEMP.value,
        "3t": EnergyModel.THREE_TEMP.value,
        "none": EnergyModel.NONE.value,
    },
    GasModel: {
        "perfect": GasModel.PERFECT_GAS.value,
        "real": GasModel.REAL_GAS.value,
        "multi": GasModel.MULTI_TEMP.value,
        "mixture": GasModel.MIXTURE.value,
    },
}


def _normalize_axis_value(key: str, v: Any) -> List[Any]:
    """识别 key 名 → 字符串值映射到枚举。

    - key ∈ _ENUM_AXES 且 v 是 str → 转枚举(支持短名别名)
    - 其他 → 走老 _normalize_axis
    """
    if key in _ENUM_AXES and isinstance(v, str):
        enum_cls = _ENUM_AXES[key]
        # 先查别名(短名 → enum.value),命中则用规范 value
        canonical = _ENUM_ALIASES.get(enum_cls, {}).get(v, v)
        try:
            return [enum_cls(canonical)]
        except ValueError:
            valid = [e.value for e in enum_cls]
            raise ValueError(
                f"unknown axis value {v!r} for key {key!r}; "
                f"expected one of {valid}"
            ) from None
    return _normalize_axis(v)


def expand_cartesian(spec: SweepSpec) -> List[Dict[str, Any]]:
    """展开笛卡尔积:返回 [{alpha:v1,beta:v2,...}, ...]"""
    if not spec.values:
        raise ValueError("SweepSpec.values: at least one sweep axis is required")

    keys: List[str] = []
    axes: List[List[Any]] = []
    for k, v in spec.values.items():
        norm = _normalize_axis_value(k, v)  # v0.10.0: 枚举识别
        if not norm:
            raise ValueError(f"SweepSpec.values[{k!r}]: empty list")
        keys.append(k)
        axes.append(norm)

    cases: List[Dict[str, Any]] = []
    for combo in itertools.product(*axes):
        cases.append(dict(zip(keys, combo)))
    return cases


# ============================================================
# FreestreamPreset: alpha/beta/Ma -> aero_u/v/w + refvel
# ============================================================
@dataclass
class FreestreamPreset:
    """
    高层来流 preset。
    给定 (alpha_deg, beta_deg, mach, T_inf),更新:
      - guiopts.aero_alpha / aero_beta / aero_ma / aero_u / aero_v / aero_w / aero_temp / aero_pres
      - physics.refvel (总速) / reftem / refpre
    """
    gamma: float = 1.4
    R: float = 287.05  # J/(kg*K), 干空气
    speed_of_sound: Optional[float] = None  # 若给出则覆盖 a = sqrt(gamma*R*T)
    update_physics: bool = True  # 是否同时更新 physics 块的 refvel/reftem/refpre

    def speed_of_sound_at(self, T: float) -> float:
        if self.speed_of_sound is not None:
            return self.speed_of_sound
        return math.sqrt(self.gamma * self.R * T)

    def compute_uvw(self, params: Dict[str, Any]) -> Dict[str, float]:
        """返回 {U, V, W} (m/s)"""
        alpha = math.radians(float(params.get("alpha", 0.0)))
        beta = math.radians(float(params.get("beta", 0.0)))
        mach = float(params.get("mach", 0.0))
        T = float(params.get("T_inf", 288.15))
        a = self.speed_of_sound_at(T)
        U = mach * a * math.cos(alpha) * math.cos(beta)
        V = mach * a * math.sin(beta)
        W = mach * a * math.sin(alpha) * math.cos(beta)
        return {"U": U, "V": V, "W": W}

    def apply(self, inp: InpFile, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        把 preset 应用到 InpFile。返回 {applied_key: value} 记录本次改了什么。

        若 params 里没给 mach / T / p_inf,沿用 InpFile 模板里的现有值;
        若 InpFile 模板也没有(罕见),则用项目级默认(mach→0, T→288.15, p→101325)。
        """
        applied: Dict[str, Any] = {}
        alpha = float(params.get("alpha", 0.0))
        beta = float(params.get("beta", 0.0))

        # 读模板默认值(guiopts 块)
        gb = inp.get_block("guiopts")
        pb = inp.get_block("physics") if self.update_physics else None

        def _existing_typed(block, key, cast, default):
            if block is None:
                return default
            v = block.get_value(key)
            if v is None:
                return default
            try:
                return cast(v.typed)
            except (TypeError, ValueError):
                return default

        template_ma = _existing_typed(gb, "aero_ma", float, 0.0)
        template_T = _existing_typed(gb, "aero_temp", float, 288.15)
        template_p = _existing_typed(gb, "aero_pres", float, 101325.0)

        mach = float(params["mach"]) if "mach" in params else template_ma
        T = float(params["T_inf"]) if "T_inf" in params else template_T
        p_inf = float(params["p_inf"]) if "p_inf" in params else template_p

        # 重算 U/V/W 用最终的 mach + T(几何分解必然依赖这两个)
        a = self.speed_of_sound_at(T)
        U = mach * a * math.cos(math.radians(alpha)) * math.cos(math.radians(beta))
        V = mach * a * math.sin(math.radians(beta))
        W = mach * a * math.sin(math.radians(alpha)) * math.cos(math.radians(beta))
        uvw = {"U": U, "V": V, "W": W}
        refvel = math.sqrt(U * U + V * V + W * W)

        # --- guiopts 块 ---
        if gb is not None:
            # 这 6 个字段是强耦合的(mach/alpha/beta → U/V/W 几何分解),
            # 必须一起写,不能只写 alpha
            pairs = {
                "aero_alpha": alpha,
                "aero_beta": beta,
                "aero_ma": mach,
                "aero_u": uvw["U"],
                "aero_v": uvw["V"],
                "aero_w": uvw["W"],
                "aero_temp": T,
                "aero_pres": p_inf,
            }
            for k, v in pairs.items():
                if gb.set(k, v):
                    applied[f"guiopts.{k}"] = v
                else:
                    gb.append(k, v)
                    applied[f"guiopts.{k}"] = v
        else:
            print(
                "[sweep] WARN: template has no `guiopts` block; "
                "aero_* fields will not be updated.",
                file=sys.stderr,
            )

        # --- physics 块 ---
        if self.update_physics and pb is not None:
            # refvel 需要 U/V/W 被重算(任何角度/马赫变化)
            if "mach" in params or "alpha" in params or "beta" in params:
                if pb.set("refvel", refvel):
                    applied["physics.refvel"] = refvel
            # reftem 跟 T 绑定
            if "T_inf" in params:
                if pb.set("reftem", T):
                    applied["physics.reftem"] = T
            # refpre 跟 p 绑定
            if "p_inf" in params:
                if pb.set("refpre", p_inf):
                    applied["physics.refpre"] = p_inf
        elif self.update_physics and pb is None:
            print(
                "[sweep] WARN: template has no `physics` block; "
                "refvel/reftem/refpre will not be updated.",
                file=sys.stderr,
            )

        return applied


# ============================================================
# 命名模板
# ============================================================
def render_case_name(
    template: str, params: Dict[str, Any], ext: str = ""
) -> str:
    """
    用 Python str.format(**params) 风格渲染。
    - 占位符 = sweep 字段名
    - 多余字段被忽略
    - 缺失字段抛 KeyError
    - ext 非空时自动追加(若模板本身已含 ext 则不重复)
    """
    name = template.format(**params)
    if ext and not name.endswith(ext):
        name = name + ext
    return name


# ============================================================
# 结果聚合
# ============================================================
@dataclass
class CaseResult:
    case_id: str
    path: str
    params: Dict[str, Any] = field(default_factory=dict)
    applied: Dict[str, Any] = field(default_factory=dict)
    # v0.8.0:per_dir 模式时记录实际复制/链接的文件列表(供 manifest 用)
    # flat 模式时为 None
    files_copied: Optional[List[str]] = None
    # v0.9.0:pbs 任务名(per_dir + pbs enabled 时填充,否则 None)
    pbs_name: Optional[str] = None
    pbs_template: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "case_id": self.case_id,
            "path": self.path,
            "params": dict(self.params),
            "applied": dict(self.applied),
        }
        if self.files_copied is not None:
            d["files"] = list(self.files_copied)
        if self.pbs_name is not None:
            d["pbs_name"] = self.pbs_name
        if self.pbs_template is not None:
            d["pbs_template"] = self.pbs_template
        return d


@dataclass
class SweepReport:
    template: str
    cases: List[CaseResult] = field(default_factory=list)
    # v0.8.0:per_dir 模式时记录元信息(flat 模式为 None,保持向后兼容)
    layout: Optional[str] = None
    source_dir: Optional[str] = None
    copy_strategy: Optional[str] = None
    exclude: Optional[List[str]] = None

    @property
    def total(self) -> int:
        return len(self.cases)

    def __iter__(self):
        return iter(self.cases)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "template": self.template,
            "total": self.total,
            "cases": [c.to_dict() for c in self.cases],
        }
        # 仅 per_dir 模式写入新字段(flat 模式不污染 manifest)
        if self.layout == "per_dir":
            d["layout"] = "per_dir"
            d["source_dir"] = self.source_dir
            d["copy_strategy"] = (
                self.copy_strategy.value
                if hasattr(self.copy_strategy, "value")
                else self.copy_strategy
            )
            d["exclude"] = list(self.exclude or [])
            # v0.9.0:pbs 启用时顶层加 pbs_enabled 字段
            if any(c.pbs_name for c in self.cases):
                d["pbs_enabled"] = True
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ============================================================
# CaseSweep: 配置聚合
# ============================================================
_DEFAULT_NAMING = "case_{alpha}"  # 占位,实际会被注入所有 sweep 字段


def _default_naming(sweep_spec: "SweepSpec") -> str:
    """生成包含所有**多值** sweep 字段的默认 naming。
    单值轴(如 T_inf 常量)不进文件名,否则可读性差。
    """
    parts = []
    for k, v in sweep_spec.values.items():
        norm = _normalize_axis(v)
        if len(norm) > 1:  # 只放多值轴
            parts.append("{" + k + "}")
    return "case_" + "_".join(parts) if parts else "case"


def _check_naming_against_sweep(
    naming: str, sweep: SweepSpec
) -> None:
    """确保 naming 模板覆盖了所有**多值** sweep 字段占位符。
    单值轴(如 T_inf 常量)视为辅助参数,可不出现于命名。
    """
    missing = []
    for k, v in sweep.values.items():
        norm = _normalize_axis(v)
        if len(norm) > 1 and ("{" + k) not in naming:
            missing.append(k)
    if missing:
        raise ValueError(
            f"naming template {naming!r} is missing sweep key placeholders "
            f"for multi-value axes: {missing}"
        )


@dataclass
class CaseSweep:
    """完整的批量算例配置"""
    template: str
    output_dir: str
    sweeps: SweepSpec
    naming: str = ""
    overrides: Dict[str, Any] = field(default_factory=dict)
    freestream: Optional[FreestreamPreset] = None
    manifest_path: Optional[str] = None
    naming_ext: str = ".inp"
    # PR #1 新增:统一 spec 列表(老 sweeps 字段保留,向后兼容)
    specs: List[Union[CartesianSpec, ExplicitCase]] = field(default_factory=list)
    # v0.8.0 新增:整算例目录模式
    source_dir: Optional[str] = None
    copy_strategy: CopyStrategy = CopyStrategy.HARDLINK
    exclude: List[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE))
    # v0.9.0 新增:pbs 脚本可选生成
    pbs: Optional[Any] = None  # 实际类型:Optional["PbsConfig"]
    # v0.9.0 新增:方程感知的湍流/2T/组分 preset
    turbulence: Optional[Any] = None  # 实际类型:Optional[TurbulencePresetBase]
    two_temperature: Optional[Any] = None  # 实际类型:Optional[TwoTemperaturePreset]
    species: Optional[Any] = None  # 实际类型:Optional[SpeciesPreset]
    # v0.10.0 新增:方程改写开关
    equation_switches: EquationSwitches = field(
        default_factory=EquationSwitches
    )

    # --------------------- 构造 ---------------------
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CaseSweep":
        if "template" not in d:
            raise KeyError("CaseSweep config: 'template' is required")
        if "output_dir" not in d:
            raise KeyError("CaseSweep config: 'output_dir' is required")

        # PR #1:从 sweeps / cases / groups 任一字段构造 specs
        specs = _build_specs_from_dict(d)

        # 老契约:必须有 sweeps 字段(向后兼容)
        # 1) sweeps 在 → 从 sweeps 构造 SweepSpec(供 cs.sweeps.values 老 API 访问)
        # 2) sweeps 不在(cases/groups 模式)→ 构造空 SweepSpec(老 API 拿到空 dict)
        if "sweeps" in d:
            sweep = SweepSpec(values=d["sweeps"])
            # 命名校验仍用老 sweeps 字段
            naming = d.get("naming") or _default_naming(sweep)
            if d.get("naming"):
                _check_naming_against_sweep(naming, sweep)
        else:
            # cases/groups 模式:用空 SweepSpec 兜底(老 API 行为:空值)
            sweep = SweepSpec(values={})
            naming = d.get("naming") or "case"
            # 不做 _check_naming_against_sweep(strict 模式对 explicit 不适用)

        # freestream: 默认开启,{"enabled": False} 显式关闭
        fs_cfg = d.get("freestream", {"enabled": True})
        if isinstance(fs_cfg, dict):
            if fs_cfg.get("enabled", True):
                freestream = FreestreamPreset(
                    gamma=fs_cfg.get("gamma", 1.4),
                    R=fs_cfg.get("R", 287.05),
                    speed_of_sound=fs_cfg.get("speed_of_sound"),
                    update_physics=fs_cfg.get("update_physics", True),
                )
            else:
                freestream = None
        else:
            freestream = fs_cfg  # 已经是 FreestreamPreset 实例

        manifest_cfg = d.get("manifest") or {}
        manifest_path = manifest_cfg.get("path") if isinstance(manifest_cfg, dict) else None

        # naming_ext: 2026-06-09 起可配置,默认 ".inp" 保持向后兼容
        naming_ext = d.get("naming_ext", ".inp")

        # v0.8.0:整算例目录模式字段
        source_dir = d.get("source_dir")  # 缺省/None → flat 模式
        # copy_strategy:接受字符串("copy"/"hardlink"/"symlink")或枚举实例
        cs_raw = d.get("copy_strategy", CopyStrategy.HARDLINK)
        try:
            copy_strategy = cs_raw if isinstance(cs_raw, CopyStrategy) else CopyStrategy(cs_raw)
        except ValueError as e:
            raise ValueError(
                f"CaseSweep config: invalid copy_strategy {cs_raw!r}; "
                f"expected one of {[s.value for s in CopyStrategy]}"
            ) from e
        # exclude:None 或缺省 → 用 DEFAULT_EXCLUDE 的副本(避免共享 mutable)
        exclude_raw = d.get("exclude")
        exclude = list(exclude_raw) if exclude_raw else list(DEFAULT_EXCLUDE)

        # v0.9.0:pbs 字段解析
        pbs_cfg = None
        pbs_d = d.get("pbs")
        if isinstance(pbs_d, dict):
            from .pbs import PbsConfig  # 局部 import 避免循环
            pbs_cfg = PbsConfig.from_dict(pbs_d)

        # v0.9.1:turbulence preset 解析
        # YAML 例:turbulence: {enabled: true, I: 0.01, L: 0.01, U_ref: 100}
        # 检测 template 的湍流模型,选对应 preset(SST/k-ε/SA/Goldberg)
        turbulence_preset = None
        turb_d = d.get("turbulence")
        if isinstance(turb_d, dict) and turb_d.get("enabled", True):
            from .equations import (
                detect_equations, make_turbulence_preset, TurbulenceModel,
            )
            from .parser import parse_file as _parse_file
            _inp = _parse_file(d["template"])
            _rep = detect_equations(_inp)
            if _rep.turbulence in (TurbulenceModel.LAMINAR, TurbulenceModel.UNKNOWN):
                raise ValueError(
                    f"sweep config turbulence.enabled=true, but template "
                    f"is {_rep.turbulence.value}; cannot apply turbulence preset"
                )
            I = turb_d.get("I")
            L = turb_d.get("L")
            U_ref = turb_d.get("U_ref", turb_d.get("U", 1.0))
            if I is None or L is None:
                raise KeyError(
                    "sweep config turbulence: 'I' and 'L' are required"
                )
            turbulence_preset = make_turbulence_preset(
                _rep.turbulence, I=float(I), L=float(L), U_ref=float(U_ref)
            )

        # v0.9.1:two_temperature preset 解析
        # YAML 例:two_temperature: {enabled: true, T_trans: 300, T_vib: 200}
        two_temperature_preset = None
        twot_d = d.get("two_temperature")
        if isinstance(twot_d, dict) and twot_d.get("enabled", True):
            from .equations import TwoTemperaturePreset
            T_trans = twot_d.get("T_trans")
            T_vib = twot_d.get("T_vib")
            if T_trans is None or T_vib is None:
                raise KeyError(
                    "sweep config two_temperature: 'T_trans' and 'T_vib' are required"
                )
            two_temperature_preset = TwoTemperaturePreset(
                T_trans=float(T_trans),
                T_vib=float(T_vib),
                set_numeqns=bool(twot_d.get("set_numeqns", True)),
            )

        # v0.10.0:equation_switches 解析
        equation_switches = EquationSwitches.from_dict(
            d.get("equation_switches")
        )

        return cls(
            template=d["template"],
            output_dir=d["output_dir"],
            sweeps=sweep,
            naming=naming,
            overrides=d.get("overrides", {}) or {},
            freestream=freestream,
            manifest_path=manifest_path,
            naming_ext=naming_ext,
            specs=specs,
            source_dir=source_dir,
            copy_strategy=copy_strategy,
            exclude=exclude,
            pbs=pbs_cfg,
            turbulence=turbulence_preset,
            two_temperature=two_temperature_preset,
            equation_switches=equation_switches,
        )

    def materialize(self) -> List[ExplicitCase]:
        """把 specs 摊平为 ExplicitCase 列表(笛卡尔展开在此完成)"""
        out: List[ExplicitCase] = []
        for spec in self.specs:
            if isinstance(spec, CartesianSpec):
                # 用临时 SweepSpec 喂给 expand_cartesian
                # (单值轴会被 expand_cartesian 复制为 1 元素列表,行为不变)
                tmp = SweepSpec(values=spec.axes)
                for combo in expand_cartesian(tmp):
                    out.append(ExplicitCase(values=combo))
            else:
                out.append(spec)
        return out

    @classmethod
    def from_json(cls, path: str) -> "CaseSweep":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_yaml(cls, path: str) -> "CaseSweep":
        """
        加载 YAML 配置文件。需要 `pyyaml`(`pip install inp-tool[yaml]`)。
        缺包时抛 ImportError 并给出安装提示。
        """
        try:
            import yaml
        except ImportError as e:
            raise ImportError(
                "YAML support requires `pyyaml`. "
                "Install via:  pip install inp-tool[yaml]"
            ) from e
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            data = {}  # 空 YAML 当作空 dict,后续 from_dict 报缺字段
        return cls.from_dict(data)

    @classmethod
    def from_csv(
        cls,
        path: str,
        template: str,
        output_dir: str,
        naming: Optional[str] = None,
        manifest_path: Optional[str] = None,
    ) -> "CaseSweep":
        """
        从 CSV 加载 case 列表(必须有表头)。

        CSV 第一行 = 列名(将作为 case values 的 key)。
        后续每行 = 一个 case,所有列值尝试转 float,失败则保留字符串。
        编码:UTF-8 优先;读取失败时尝试 GBK(Windows 默认)。

        参数:
            path: CSV 文件路径
            template: 模板 .inp 路径(必填,因为 CSV 不含模板信息)
            output_dir: 输出目录
            naming: naming 模板(可选;默认 "case" 或 "case_{<第一个键>}")
            manifest_path: manifest.json 路径(可选)
        """
        import csv as _csv

        # 编码处理:UTF-8 → GBK fallback
        try:
            f = open(path, "r", encoding="utf-8", newline="")
            sample = f.read(4096)
            f.seek(0)
        except UnicodeDecodeError:
            f = open(path, "r", encoding="gbk", newline="")
            sample = f.read(4096)
            f.seek(0)

        try:
            reader = _csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError(
                    f"CaseSweep.from_csv: CSV is empty or has no header: {path}"
                )

            # 第一遍:收集所有行(原始字符串)
            raw_rows: List[Dict[str, str]] = []
            for row in reader:
                raw_rows.append({k: (v or "") for k, v in row.items()})

            if not raw_rows:
                raise ValueError(
                    f"CaseSweep.from_csv: no data rows in {path}"
                )

            # 推断每列类型:全为数字 → float;否则 string
            # 某列若既有数字又有非数字 → ValueError(列类型不一致)
            col_types: Dict[str, str] = {}  # col -> "float" | "string"
            for row in raw_rows:
                for col, val in row.items():
                    if val == "":
                        continue
                    try:
                        float(val)
                        cur = "float"
                    except ValueError:
                        cur = "string"
                    if col not in col_types:
                        col_types[col] = cur
                    elif col_types[col] != cur:
                        raise ValueError(
                            f"row {raw_rows.index(row) + 2}: "
                            f"column {col!r} has mixed types "
                            f"(was {col_types[col]}, got {cur}={val!r})"
                        )

            # 第二遍:转 typed values
            specs: List[ExplicitCase] = []
            for row_idx, row in enumerate(raw_rows, start=2):  # start=2 因 header 占第 1 行
                values: Dict[str, Any] = {}
                for col, val in row.items():
                    if val == "":
                        continue
                    if col_types[col] == "float":
                        values[col] = float(val)
                    else:
                        values[col] = val
                if not values:
                    continue
                specs.append(ExplicitCase(values=values))

            if not specs:
                raise ValueError(
                    f"CaseSweep.from_csv: no usable data rows in {path}"
                )

            # 默认 naming:case(若用户未给)
            if naming is None:
                first_key = list(specs[0].values.keys())[0] if specs[0].values else "case"
                naming = f"case_{{{first_key}}}"

            # 用空 SweepSpec 兜底(老 API 兼容);specs 走 ExplicitCase 列表
            # freestream 默认开启(与其他模式一致);用户可后续修改 cs.freestream
            return cls(
                template=template,
                output_dir=output_dir,
                sweeps=SweepSpec(values={}),  # CSV 模式无 sweeps
                naming=naming,
                overrides={},
                freestream=FreestreamPreset(),  # 默认开启(与 sweeps 模式一致)
                manifest_path=manifest_path,
                naming_ext=".inp",
                specs=specs,
            )
        finally:
            f.close()


# ============================================================
# PR #1:specs 构造器(从 dict 识别 sweeps / cases / groups)
# ============================================================
def _build_specs_from_dict(d: Dict[str, Any]) -> List[Union[CartesianSpec, ExplicitCase]]:
    """根据 dict 字段决定走哪种 spec 模式。

    规则:
      - 必须有 sweeps / cases / groups 至少一个
      - sweeps:   CartesianSpec
      - cases:    ExplicitCase(每个 dict 转)
      - groups:   每个 group 的 common 注入到每个 case,得 ExplicitCase + group 名
      - 三者可以共存(顺序展开)
    """
    has_sweeps = "sweeps" in d
    has_cases = "cases" in d
    has_groups = "groups" in d

    if not (has_sweeps or has_cases or has_groups):
        raise KeyError(
            "CaseSweep config: 'sweeps' / 'cases' / 'groups' 至少需要其中一个"
        )

    specs: List[Union[CartesianSpec, ExplicitCase]] = []

    if has_sweeps:
        sweeps_dict = d["sweeps"]
        if not sweeps_dict:
            raise ValueError("CaseSweep config: 'sweeps' is empty")
        specs.append(CartesianSpec(axes=dict(sweeps_dict)))

    if has_cases:
        cases_list = d["cases"]
        if not cases_list:
            raise ValueError("CaseSweep config: 'cases' is empty")
        for c in cases_list:
            specs.append(ExplicitCase(values={k: float(v) for k, v in c.items()}))

    if has_groups:
        groups_list = d["groups"]
        if not groups_list:
            raise ValueError("CaseSweep config: 'groups' is empty")
        for g in groups_list:
            common = g.get("common", {}) or {}
            group_name = g.get("name")
            cases_in_group = g.get("cases", []) or []
            if not cases_in_group:
                raise ValueError(
                    f"CaseSweep config: group {group_name!r} has no cases"
                )
            for c in cases_in_group:
                merged = {**common, **c}
                specs.append(ExplicitCase(
                    values={k: float(v) for k, v in merged.items()},
                    group=group_name,
                ))

    if not specs:
        # 三个 key 都在但都是空(已被前面的 ValueError 抓住;此分支兜底)
        raise KeyError(
            "CaseSweep config: no cases produced from 'sweeps' / 'cases' / 'groups'"
        )

    return specs


# ============================================================
# overrides 应用
# ============================================================
def _apply_overrides(inp: InpFile, overrides: Dict[str, Any]) -> None:
    """
    两种风格:
      1) 嵌套: {block: {keyword: value, ...}, ...}
      2) 点号: {"block.keyword": value, ...}
    """
    for key, val in overrides.items():
        if "." in key and not isinstance(val, dict):
            # 风格 2
            block, kw = key.split(".", 1)
            b = inp.get_block(block)
            if b is None:
                print(
                    f"[sweep] WARN: override block {block!r} not found; skipping {key}",
                    file=sys.stderr,
                )
                continue
            if not b.set(kw, val):
                b.append(kw, val)
        elif isinstance(val, dict):
            # 风格 1
            b = inp.get_block(key)
            if b is None:
                print(
                    f"[sweep] WARN: override block {key!r} not found; skipping",
                    file=sys.stderr,
                )
                continue
            for kw, v in val.items():
                if not b.set(kw, v):
                    b.append(kw, v)
        else:
            # 标量值且无点号:无法定位,报 warn
            print(
                f"[sweep] WARN: override key {key!r} has no block; "
                f"expect 'block.keyword' or nested dict",
                file=sys.stderr,
            )


# ============================================================
# v0.8.0:整算例目录复制核心
# ============================================================
def _match_any(name: str, patterns: List[str]) -> bool:
    """fnmatch 风格通配符匹配,任一 pattern 命中即返回 True。

    容忍 user 在 CLI 写 `mlog/` (带 trailing / 习惯),自动 strip。
    """
    from fnmatch import fnmatch
    return any(fnmatch(name, p.rstrip("/")) for p in patterns)


def _copy_one(src: "os.PathLike", dst: "os.PathLike", strategy: CopyStrategy) -> None:
    """按 strategy 把 src 复制/链接到 dst。失败自动退化(详见各分支)。"""
    src = str(src)
    dst = str(dst)
    if strategy == CopyStrategy.COPY:
        shutil.copy2(src, dst)
    elif strategy == CopyStrategy.HARDLINK:
        try:
            os.link(src, dst)
        except OSError:
            # 跨 FS / 权限不足 → 退化到 copy
            shutil.copy2(src, dst)
    elif strategy == CopyStrategy.SYMLINK:
        try:
            os.symlink(src, dst)
        except OSError:
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
    else:
        raise ValueError(f"unknown copy strategy: {strategy!r}")


def _copy_case_files(
    src: "os.PathLike",
    dst: "os.PathLike",
    exclude: List[str],
    strategy: CopyStrategy,
    force: bool = False,
) -> List[str]:
    """递归复制 src 目录内容到 dst(不含 mcfd.inp,会在外层由 write_preserve 覆盖)。

    Args:
        src: 源目录(基础算例)
        dst: 目标子目录(将被创建)
        exclude: fnmatch 风格的排除模式(默认含 *.bak / mlog / nodesout.bin)
        strategy: 复制策略
        force: 目标已存在时是否覆盖(默认 False 抛错)

    Returns:
        实际处理的文件相对路径列表(供 manifest 用)

    Raises:
        FileExistsError: dst 已存在且 force=False
        FileNotFoundError: src 不存在
    """
    import shutil as _shutil
    src = str(src)
    dst = str(dst)
    if not os.path.isdir(src):
        raise FileNotFoundError(f"source_dir not found: {src}")
    if os.path.exists(dst):
        if not force:
            raise FileExistsError(
                f"target case directory already exists: {dst}; "
                f"use --force to overwrite or change the naming template"
            )
        # force=True → 删了重建
        _shutil.rmtree(dst)

    os.makedirs(dst, exist_ok=False)
    copied: List[str] = []

    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        # 排除目录(原地修改 dirs 以让 os.walk 跳过)
        dirs[:] = [
            d for d in dirs
            if not _match_any(
                os.path.join(rel, d) if rel != "." else d,
                exclude,
            )
        ]
        for f in files:
            rel_path = os.path.join(rel, f) if rel != "." else f
            if _match_any(rel_path, exclude):
                continue
            # 关键:mcfd.inp 必须由 generate() 用 write_preserve() 写入(覆盖模板修改版),
            # 若此处也复制/硬链接,HARDLINK/SYMLINK 策略下会共享 inode,
            # 后续 write_preserve() 写 dst 时会同步覆盖源 mcfd.inp → 静默数据损坏
            if f == "mcfd.inp":
                # 仍记入 copied 列表(让 manifest 反映完整文件清单)
                copied.append(rel_path)
                continue
            src_f = os.path.join(root, f)
            dst_f = os.path.join(dst, rel_path)
            os.makedirs(os.path.dirname(dst_f), exist_ok=True)
            _copy_one(src_f, dst_f, strategy)
            copied.append(rel_path)

    return copied


# ============================================================
# generate() 主流程
# ============================================================
def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def generate(sweep: CaseSweep, dry_run: bool = False, force: bool = False) -> SweepReport:
    """
    解析模板 -> 摊平 specs(笛卡尔展开在此) -> 每个 case 应用 preset + overrides ->
    写盘 -> 累积报告。

    PR #1:不再直接 expand_cartesian(sweep.sweeps),统一走 cs.materialize(),
    支持 sweeps / cases / groups / 混合模式。

    v0.8.0:支持 source_dir → per_dir 模式(整算例目录生成)。

    v0.9.0:per_dir 模式开头跑完整性检查(error 抛 SweepValidationError);
    per_case 末尾可选生成 pbs(替换 #PBS -N)。
    """
    if not dry_run:
        os.makedirs(sweep.output_dir, exist_ok=True)

    # v0.9.0:完整性检查(仅 per_dir 模式)
    if sweep.source_dir is not None and not dry_run:
        from .pbs import validate_base_case_dir
        pbs_enabled = sweep.pbs is not None and sweep.pbs.enabled
        issues = validate_base_case_dir(sweep.source_dir, pbs_enabled=pbs_enabled)
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            raise SweepValidationError(issues)
        # 警告打到 stderr
        import sys as _sys
        for w in [i for i in issues if i.severity == "warning"]:
            print(f"[validate] {w.severity}: {w.code} - {w.message}", file=_sys.stderr)

    # 1) 加载模板(只读一次)
    template_inp = parse_file(sweep.template)

    # 2) 摊平 specs(笛卡尔 / 显式 / 分组 / 混合,统一入口)
    flat = sweep.materialize()

    # 3) 命名模板预先校验(老 sweeps 模式下,检查多值轴是否都在 naming 中)
    # 显式 / 分组模式不做 strict 校验(每个 case 自带完整 values,
    # 缺占位符时让 render_case_name 在 format 时报 KeyError)
    if sweep.sweeps.values:
        _check_naming_against_sweep(sweep.naming, sweep.sweeps)

    # v0.8.0:布局判定
    layout = _resolve_layout(sweep)
    # per_dir 模式:目录名无 .inp 扩展
    # flat 模式:文件名带 naming_ext(默认 .inp)
    naming_ext = "" if layout == "per_dir" else sweep.naming_ext

    report = SweepReport(
        template=sweep.template,
        layout=layout,
        source_dir=sweep.source_dir,
        copy_strategy=(
            sweep.copy_strategy.value
            if hasattr(sweep.copy_strategy, "value")
            else sweep.copy_strategy
        ) if layout == "per_dir" else None,
        exclude=list(sweep.exclude) if layout == "per_dir" else None,
    )
    used_names: Dict[str, int] = {}

    # v0.9.0:per_dir + pbs 模式时,循环外预读 pbs 模板内容(in-memory,避免 hardlink 副作用)
    pbs_template_text: Optional[str] = None
    pbs_template_path: Optional[str] = None
    if (
        layout == "per_dir"
        and not dry_run
        and sweep.pbs is not None
        and sweep.pbs.enabled
    ):
        from .pbs import detect_pbs_template
        pbs_template_path = sweep.pbs.template
        if not pbs_template_path:
            pbs_template_path = detect_pbs_template(sweep.source_dir)
        if pbs_template_path and os.path.isfile(pbs_template_path):
            pbs_template_text = Path(pbs_template_path).read_text()

    for case_spec in flat:
        params = case_spec.values
        # deepcopy 模板(每个 case 独立改)
        inp = copy.deepcopy(template_inp)

        # 应用 freestream preset
        applied: Dict[str, Any] = {}
        if sweep.freestream is not None:
            applied.update(sweep.freestream.apply(inp, params))

        # v0.9.1:应用 turbulence preset(每个 case 同样 I/L/U,
        # 但因 deepcopy template,字段需重写)
        if sweep.turbulence is not None:
            applied.update(sweep.turbulence.apply(inp))

        # v0.9.1:应用 two_temperature preset(联动写 tnoneq_numeqns + 温度)
        if sweep.two_temperature is not None:
            applied.update(sweep.two_temperature.apply(inp))

        # 应用 overrides
        _apply_overrides(inp, sweep.overrides)

        # 命名(可能冲突: 同名 case 追加 _1, _2)
        # 注入 {group} 占位符(若 case 有 group)
        render_params = dict(params)
        if case_spec.group is not None:
            render_params["group"] = case_spec.group
        base_name = render_case_name(
            sweep.naming, render_params, ext=naming_ext
        )
        name = base_name
        if name in used_names:
            used_names[name] += 1
            stem, ext = os.path.splitext(base_name)
            name = f"{stem}_{used_names[name]}{ext}"
        else:
            used_names[name] = 0

        # 路径
        path = os.path.join(sweep.output_dir, name)

        # 写盘
        files_copied: Optional[List[str]] = None
        if not dry_run:
            from .writer import write_preserve
            if layout == "per_dir":
                # 1) 复制基础算例目录(不含 mcfd.inp,会被覆盖)
                files_copied = _copy_case_files(
                    src=sweep.source_dir,
                    dst=path,
                    exclude=sweep.exclude,
                    strategy=sweep.copy_strategy,
                    force=force,
                )
                # 2) 写修改后的 mcfd.inp
                write_preserve(inp, os.path.join(path, "mcfd.inp"))
            else:
                write_preserve(inp, path)

        # v0.9.0:per_dir 模式末尾写 pbs(可选项)
        pbs_name_for_case: Optional[str] = None
        pbs_template_for_case: Optional[str] = None
        if (
            layout == "per_dir"
            and not dry_run
            and pbs_template_path is not None
            and pbs_template_text is not None
        ):
            from .pbs import write_pbs as pbs_write, render_pbs_name
            base_basename = extract_pbs_basename(
                pbs_template_path, max_len=sweep.pbs.basename_max_len
            )
            # 多值轴
            multi_value: List[str] = []
            if hasattr(sweep.sweeps, "values") and isinstance(sweep.sweeps.values, dict):
                for ax, vs in sweep.sweeps.values.items():
                    if isinstance(vs, list) and len(vs) > 1:
                        multi_value.append(ax)
            job_name = render_pbs_name(
                params=params,
                multi_value_axes=multi_value,
                base_basename=base_basename,
                user_template=sweep.pbs.naming,
            )
            # 写出到 case 子目录。in-memory template 避免每次 read 源文件;
            # 先 unlink 解除源 hardlink,write 时新建独立 inode,避免 case_0 写影响 case_4。
            case_pbs_path = os.path.join(path, os.path.basename(pbs_template_path))
            if os.path.isfile(case_pbs_path):
                os.unlink(case_pbs_path)
            pbs_write(
                pbs_template_path, case_pbs_path, job_name,
                template_text=pbs_template_text,
            )
            pbs_name_for_case = job_name
            pbs_template_for_case = case_pbs_path

        # 记录
        case = CaseResult(
            case_id=name,
            path=path,
            params=dict(params),
            applied=applied,
            files_copied=files_copied,
            pbs_name=pbs_name_for_case,
            pbs_template=pbs_template_for_case,
        )
        report.cases.append(case)

    # 4) manifest
    if sweep.manifest_path and not dry_run:
        os.makedirs(os.path.dirname(sweep.manifest_path) or ".", exist_ok=True)
        manifest_data = report.to_dict()
        # 加入 template hash 供校验
        try:
            manifest_data["template_sha256"] = _file_sha256(sweep.template)
        except OSError:
            pass
        manifest_data["generated_at"] = _iso_now()
        with open(sweep.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    return report


def _iso_now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")
