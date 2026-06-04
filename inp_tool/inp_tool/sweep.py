"""
mcfd.inp sweep 批量算例生成器 v0.1

基于一个 mcfd.inp 样例,通过 (alpha, beta, mach, ...) 扫描,生成 N 个变体。
- FreestreamPreset: 几何分解 (alpha, beta, Ma) -> (U, V, W) + refvel
- SweepSpec: 笛卡尔积展开
- render_case_name: 命名模板
- CaseResult / SweepReport: 结果聚合
"""
from __future__ import annotations
import copy
import hashlib
import math
import os
import re
import sys
import itertools
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from .model import InpFile
from .parser import parse_file
from .writer import write as write_inp


# 一个 sweep 轴的值可以是标量或列表
SweepValue = Union[int, float, str, List[Union[int, float, str]]]


@dataclass
class SweepSpec:
    """扫描定义:每个 key 是一个轴,值是它的取值列表(或单值)"""
    values: Dict[str, SweepValue] = field(default_factory=dict)

    def values_keys(self) -> List[str]:
        return list(self.values.keys())


def _normalize_axis(v: SweepValue) -> List[Any]:
    """把标量/列表统一为列表"""
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


def expand_cartesian(spec: SweepSpec) -> List[Dict[str, Any]]:
    """展开笛卡尔积:返回 [{alpha:v1,beta:v2,...}, ...]"""
    if not spec.values:
        raise ValueError("SweepSpec.values: at least one sweep axis is required")

    keys: List[str] = []
    axes: List[List[Any]] = []
    for k, v in spec.values.items():
        norm = _normalize_axis(v)
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
        """
        applied: Dict[str, Any] = {}
        uvw = self.compute_uvw(params)
        alpha = float(params.get("alpha", 0.0))
        beta = float(params.get("beta", 0.0))
        mach = float(params.get("mach", 0.0))
        T = float(params.get("T_inf", 288.15))
        refvel = math.sqrt(uvw["U"] ** 2 + uvw["V"] ** 2 + uvw["W"] ** 2)

        # --- guiopts 块 ---
        gb = inp.get_block("guiopts")
        if gb is None:
            print(
                "[sweep] WARN: template has no `guiopts` block; "
                "aero_* fields will not be updated.",
                file=sys.stderr,
            )
        else:
            pairs = {
                "aero_alpha": alpha,
                "aero_beta": beta,
                "aero_ma": mach,
                "aero_u": uvw["U"],
                "aero_v": uvw["V"],
                "aero_w": uvw["W"],
                "aero_temp": T,
            }
            if "p_inf" in params:
                pairs["aero_pres"] = float(params["p_inf"])
            for k, v in pairs.items():
                if gb.set(k, v):
                    applied[f"guiopts.{k}"] = v
                else:
                    # 字段不存在,append
                    gb.append(k, v)
                    applied[f"guiopts.{k}"] = v

        # --- physics 块 ---
        if self.update_physics:
            pb = inp.get_block("physics")
            if pb is None:
                print(
                    "[sweep] WARN: template has no `physics` block; "
                    "refvel/reftem/refpre will not be updated.",
                    file=sys.stderr,
                )
            else:
                if pb.set("refvel", refvel):
                    applied["physics.refvel"] = refvel
                if pb.set("reftem", T):
                    applied["physics.reftem"] = T
                if "p_inf" in params:
                    p = float(params["p_inf"])
                    if pb.set("refpre", p):
                        applied["physics.refpre"] = p

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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "path": self.path,
            "params": dict(self.params),
            "applied": dict(self.applied),
        }


@dataclass
class SweepReport:
    template: str
    cases: List[CaseResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cases)

    def __iter__(self):
        return iter(self.cases)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template": self.template,
            "total": self.total,
            "cases": [c.to_dict() for c in self.cases],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ============================================================
# CaseSweep: 配置聚合
# ============================================================
_DEFAULT_NAMING = "case_{alpha}"  # 占位,实际会被注入所有 sweep 字段


def _default_naming(sweep_keys: List[str]) -> str:
    """生成包含所有 sweep 字段的默认 naming"""
    parts = []
    for k in sweep_keys:
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

    # --------------------- 构造 ---------------------
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CaseSweep":
        if "template" not in d:
            raise KeyError("CaseSweep config: 'template' is required")
        if "output_dir" not in d:
            raise KeyError("CaseSweep config: 'output_dir' is required")
        if "sweeps" not in d:
            raise KeyError("CaseSweep config: 'sweeps' is required")

        sweep_keys = list(d["sweeps"].keys())
        sweep = SweepSpec(values=d["sweeps"])
        naming = d.get("naming") or _default_naming(sweep_keys)
        if d.get("naming"):
            _check_naming_against_sweep(naming, sweep)

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

        return cls(
            template=d["template"],
            output_dir=d["output_dir"],
            sweeps=sweep,
            naming=naming,
            overrides=d.get("overrides", {}) or {},
            freestream=freestream,
            manifest_path=manifest_path,
        )

    @classmethod
    def from_json(cls, path: str) -> "CaseSweep":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


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
# generate() 主流程
# ============================================================
def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def generate(sweep: CaseSweep, dry_run: bool = False) -> SweepReport:
    """
    解析模板 -> 笛卡尔积展开 -> 每个 case 应用 preset + overrides -> 写盘 -> 累积报告
    """
    if not dry_run:
        os.makedirs(sweep.output_dir, exist_ok=True)

    # 1) 加载模板(只读一次)
    template_inp = parse_file(sweep.template)

    # 2) 展开笛卡尔积
    cases = expand_cartesian(sweep.sweeps)

    # 3) 命名模板预先校验
    _check_naming_against_sweep(sweep.naming, sweep.sweeps)

    report = SweepReport(template=sweep.template)
    used_names: Dict[str, int] = {}

    for params in cases:
        # deepcopy 模板(每个 case 独立改)
        inp = copy.deepcopy(template_inp)

        # 应用 freestream preset
        applied: Dict[str, Any] = {}
        if sweep.freestream is not None:
            applied.update(sweep.freestream.apply(inp, params))

        # 应用 overrides
        _apply_overrides(inp, sweep.overrides)

        # 命名(可能冲突: 同名 case 追加 _1, _2)
        base_name = render_case_name(
            sweep.naming, params, ext=sweep.naming_ext
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
        if not dry_run:
            write_inp(inp, path)

        # 记录
        case = CaseResult(
            case_id=name,
            path=path,
            params=dict(params),
            applied=applied,
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
