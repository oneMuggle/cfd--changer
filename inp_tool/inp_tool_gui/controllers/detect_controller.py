"""DetectController:GUI 方程/湍流模型检测业务逻辑(v0.13 升级版)。

**v0.13:** 改用真实 :func:`inp_tool.equations.detect_equations`(v0.9.1 + v0.11.0 上线)。
:data:`DetectionReport` 是 wrap :class:`EquationSystemReport` 的薄 adapter,
保留 v0.12 GUI 字段(has_reftem / has_reynolds / has_turbulence /
has_chemistry / is_two_temperature / chemistry_blocks / notes /
recommended_fields / summary_zh)以便 DetectPanel 兼容。

**字段来源切分:**
- 真实枚举(energy/turbulence/gas/n_species/sweeps_equation_warnings)→ 来自 EquationSystemReport
- 直接字段扫描(has_reftem/has_reynolds/has_chemistry/chemistry_blocks)→ 来自 InpFile 直扫
  (detect_equations 不解析这些,它们与方程系统无关)
- turb_keywords → 直接从 InpFile 提取(``turb*`` 前缀关键字,启发式)

**不**依赖 PySide2;widget 层只调此 controller。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from inp_tool.equations import (
    EquationSystemReport,
    GasModel,
    detect_equations,
)
from inp_tool.model import InpFile


# ``EquationSystemReport.recommended_fields()`` 字符串 → 4 元组映射表
# (block, keyword, default_value, note)。PresetDialog 仍按旧 4 元组 API 消费。
_RECOMMENDED_PARSER: dict = {
    "tnoneq_numeqns":            ("physics", "tnoneq_numeqns", 1, "非平衡方程数(2T = 1)"),
    "reftem (T_trans)":          ("physics", "reftem", 300.0, "平动温度(K)"),
    "vibtem (T_vib)":            ("physics", "vibtem", 300.0, "振动温度(K)"),
    "turbi_lev (k)":             ("guiopts", "turbi_lev", 0.0, "k 初值"),
    "turbi_len (L)":             ("guiopts", "turbi_len", 0.0, "L 长度尺度"),
    "turbi_tlev (k/U²)":         ("guiopts", "turbi_tlev", 0.0, "k/U²"),
    "turbi_tlen":                ("guiopts", "turbi_tlen", 0.0, "tlen"),
    "turbi_lev (ν̃)":             ("guiopts", "turbi_lev", 0.0, "ν̃ 初值"),
    "species 质量分率 (mass/mole)": ("chemistry", "species", {}, "species mass/mole fractions"),
}


@dataclass
class DetectionReport:
    """薄 adapter:wrap :class:`EquationSystemReport` + 派生 GUI 友好字段。"""

    _eq: EquationSystemReport

    # --- 新 API(真实)-------------------------------------------------

    @property
    def turbulence_model(self):
        """:class:`TurbulenceModel` 枚举(SST_KW / SA / Goldberg / Realizable / 等)。"""
        return self._eq.turbulence

    @property
    def energy_model(self):
        """:class:`EnergyModel` 枚举(NONE / TWO_TEMP / THREE_TEMP)。"""
        return self._eq.energy

    @property
    def gas_model(self):
        """:class:`GasModel` 枚举(PERFECT_GAS / REAL_GAS / MULTI_TEMP / MIXTURE)。"""
        return self._eq.gas

    @property
    def n_species(self) -> int:
        return self._eq.n_species

    @property
    def gasnam(self) -> Optional[str]:
        """``physics.gasnam`` 原始字符串(仅参考,不用于判别)。"""
        return self._eq.gasnam

    @property
    def sweeps_equation_warnings(self) -> List[str]:
        """wizard axis 与 template 不兼容的告警。"""
        return list(self._eq.sweeps_equation_warnings)

    # --- 向后兼容 v0.12 字段 ---------------------------------------

    @property
    def has_reftem(self) -> bool:
        """``physics.reftem`` 是否存在(InpFile 直扫)。"""
        return self._inp_contains_keyword("reftem")

    @property
    def has_reynolds(self) -> bool:
        """``physics.reynolds`` 是否存在。"""
        return self._inp_contains_keyword("reynolds")

    @property
    def has_turbulence(self) -> bool:
        """模板含非层流湍流模型(SST/SA/Goldberg/Realizable)。"""
        t = self._eq.turbulence.value
        return t not in ("unknown", "laminar")

    @property
    def has_chemistry(self) -> bool:
        return self.chemistry_blocks > 0

    @property
    def chemistry_blocks(self) -> int:
        """chemistry 块数。"""
        if self._inp is None:
            return 0
        return sum(1 for b in self._inp.block_list if b.name == "chemistry")

    @property
    def is_two_temperature(self) -> bool:
        return self._eq.energy.value == "2T"

    @property
    def turb_keywords(self) -> List[str]:
        """湍流相关关键字启发式(``turb*`` 前缀)。"""
        if self._inp is None:
            return []
        kw_set = set()
        for b in self._inp.block_list:
            for s in b.statements:
                if "turb" in s.keyword.lower():
                    kw_set.add(s.keyword)
        for s in self._inp.top_stmts:
            if "turb" in s.keyword.lower():
                kw_set.add(s.keyword)
        return sorted(kw_set)

    @property
    def notes(self) -> List[str]:
        return list(self._eq.notes)

    @property
    def recommended_fields(self) -> List[Tuple[str, str, object, str]]:
        """``[(block, keyword, default_value, note), ...]`` 兼容 v0.12。

        解析 :meth:`EquationSystemReport.recommended_fields` 字符串列表;
        未知字符串退化为 ``(physics, <keyword>, None, <original_str>)``。
        """
        out: List[Tuple[str, str, object, str]] = []
        for f in self._eq.recommended_fields():
            if f in _RECOMMENDED_PARSER:
                out.append(_RECOMMENDED_PARSER[f])
            else:
                kw = f.split(" ")[0]
                out.append(("physics", kw, None, f))
        return out

    def summary_zh(self) -> str:
        """中文摘要(直接透传 EquationSystemReport.summary_zh)。"""
        return self._eq.summary_zh()

    # --- 内部 ----------------------------------------------------------

    _inp: Optional[InpFile] = None

    def _inp_contains_keyword(self, keyword: str) -> bool:
        if self._inp is None:
            return False
        for b in self._inp.block_list:
            for s in b.statements:
                if s.keyword == keyword:
                    return True
        return False


class DetectController:
    """GUI 检测控制器(v0.13 升级版)。"""

    def __init__(self) -> None:
        self._report: Optional[DetectionReport] = None

    @property
    def last_report(self) -> Optional[DetectionReport]:
        return self._report

    def run(
        self,
        inp: InpFile,
        *,
        intended_axes: Optional[Dict[str, str]] = None,
    ) -> DetectionReport:
        """扫 ``inp`` → 真实 :func:`detect_equations` → adapter。

        ``intended_axes``(v0.11.0+):wizard step_4b/4c 选的 axis 值;
        不传则只做单纯方程检测(无 axis 兼容告警)。
        """
        eq_rep = detect_equations(inp, intended_axes=intended_axes)
        rep = DetectionReport(_eq=eq_rep)
        rep._inp = inp  # type: ignore[attr-defined]
        self._report = rep
        return rep