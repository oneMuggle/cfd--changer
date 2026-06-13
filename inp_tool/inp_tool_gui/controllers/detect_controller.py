"""DetectController:GUI 方程/湍流模型检测业务逻辑(Phase 4)。

**简化版(等 v0.9.1 完整 detect_equations):**

当下基于关键字扫描推断:
- 是否含 ``physics.reftem``(参考温度)
- 是否含 ``physics.reynolds``(雷诺数)
- 是否含 ``turb`` / ``turbc`` / ``turbk`` / ``turbw``(湍流模型)
- 是否含 ``chemistry`` block(化学)
- 是否含 ``vibtem``(振动温度,2T 标志)

v0.9.1 完整版 ``detect_equations()`` 上线后,本 controller 直接调它,API 不变。

**不**依赖 PySide2;widget 层只调此 controller。
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from inp_tool.model import InpFile


@dataclass
class DetectionReport:
    """简化版检测报告(取代 v0.9.1 的 EquationSystemReport)。"""

    has_reftem: bool = False
    has_reynolds: bool = False
    has_turbulence: bool = False
    has_chemistry: bool = False
    is_two_temperature: bool = False  # 是否有 vibtem
    turb_keywords: List[str] = field(default_factory=list)
    chemistry_blocks: int = 0
    notes: List[str] = field(default_factory=list)
    recommended_fields: List[Tuple[str, str, object, str]] = field(
        default_factory=list
    )

    def summary_zh(self) -> str:
        """中文摘要(供 DetectPanel 顶部标签显示)。"""
        flags = []
        if self.has_reftem:
            flags.append("✓ 参考温度")
        if self.has_reynolds:
            flags.append("✓ 雷诺数")
        if self.has_turbulence:
            flags.append(f"✓ 湍流({', '.join(self.turb_keywords[:3])})")
        if self.has_chemistry:
            flags.append(f"✓ 化学({self.chemistry_blocks} 块)")
        if self.is_two_temperature:
            flags.append("✓ 双温度(2T)")
        if not flags:
            return "未检测到方程/湍流模型标志字段"
        return "检测到: " + " | ".join(flags)


class DetectController:
    """GUI 检测控制器。"""

    def __init__(self) -> None:
        self._report: Optional[DetectionReport] = None

    @property
    def last_report(self) -> Optional[DetectionReport]:
        """最近一次 :meth:`run` 的报告;未 run 返 None。"""
        return self._report

    def run(self, inp: InpFile) -> DetectionReport:
        """扫 ``inp`` 关键字,生成报告。"""
        rep = DetectionReport()

        all_kw_by_block: dict = {
            b.name: [s.keyword for s in b.statements] for b in inp.block_list
        }
        all_kw_top = [s.keyword for s in inp.top_stmts]

        physics_kw = all_kw_by_block.get("physics", [])
        rep.has_reftem = "reftem" in physics_kw
        rep.has_reynolds = "reynolds" in physics_kw
        rep.is_two_temperature = "vibtem" in physics_kw

        # 湍流关键字(以 turb 开头的)
        turb_kws = [k for k in (physics_kw + all_kw_top) if k.startswith("turb")]
        rep.has_turbulence = bool(turb_kws)
        rep.turb_keywords = sorted(set(turb_kws))

        rep.chemistry_blocks = sum(
            1 for b in inp.block_list if b.name == "chemistry"
        )
        rep.has_chemistry = rep.chemistry_blocks > 0

        # notes
        if rep.has_turbulence and not rep.has_reynolds:
            rep.notes.append(
                "湍流模型存在但缺 reynolds — SST k-ω 反算需要 Reynolds"
            )
        if rep.has_chemistry and rep.chemistry_blocks > 1:
            rep.notes.append(
                f"检测到 {rep.chemistry_blocks} 个 chemistry block — "
                "确认是否多组分 vs 燃烧模型"
            )
        if not rep.has_reftem and rep.has_turbulence:
            rep.notes.append("缺 reftem,湍流参考温度默认 300K")

        # 推荐字段(供 PresetDialog 使用)
        if not rep.has_reynolds and rep.has_turbulence:
            rep.recommended_fields.append(
                ("physics", "reynolds", 1.0e6, "SST k-ω 默认雷诺数")
            )
        if not rep.has_reftem:
            rep.recommended_fields.append(
                ("physics", "reftem", 300.0, "默认参考温度 300 K")
            )

        self._report = rep
        return rep