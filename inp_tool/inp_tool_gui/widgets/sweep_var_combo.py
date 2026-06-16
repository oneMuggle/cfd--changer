"""Sweep 变量发现 + 类型元数据(纯 Python,无 PySide2)。

v0.17 引入,与 SweepController 配合:
- :class:`VarSpec` — 单变量 UI 描述(frozen dataclass)
- :func:`enumerate_vars` — 给定模板路径,返回 :class:`VarSpec` 列表
  (枚举轴 + .inp 变量)

不依赖 PySide2,可被 controller 和测试独立 import。
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from inp_tool import parser
from inp_tool.sweep import (
    EnergyModel, GasModel, TurbulenceModel,
)


# 枚举轴定义: key -> Enum class
_ENUM_AXIS_CLASSES: Dict[str, type] = {
    "turbulence": TurbulenceModel,
    "energy": EnergyModel,
    "gas": GasModel,
}


@dataclass(frozen=True)
class VarSpec:
    """单变量的 UI 描述。

    - 枚举轴: block/keyword/value_idx 全为 None,enum_values 填合法 enum
    - 普通 .inp 变量: 填 block + keyword + value_idx,enum_values 为 None
    """
    key: str
    label: str
    kind: str
    enum_values: Optional[Tuple[str, ...]] = None
    block: Optional[str] = None
    keyword: Optional[str] = None
    value_idx: Optional[int] = None


def _infer_kind_for_sweep(typed: Any) -> str:
    """推断 sweep 轴的 kind。

    注意:与 ``infer_type`` 的 bool>int>float>str 不同,
    sweep 轴语义上更接近「物理参数」,布尔直接走 str(避免误把
    "t"/"f" 误判成 axis 值)。
    """
    if isinstance(typed, bool):
        return "str"
    if isinstance(typed, int):
        return "int"
    if isinstance(typed, float):
        return "float"
    return "str"


def _enum_axis_specs() -> List[VarSpec]:
    """构造 3 个枚举轴 VarSpec。"""
    out: List[VarSpec] = []
    for key, enum_cls in _ENUM_AXIS_CLASSES.items():
        values = tuple(e.value for e in enum_cls)
        label = "{} (枚举:{})".format(key, ",".join(values))
        out.append(VarSpec(
            key=key,
            label=label,
            kind="enum",
            enum_values=values,
        ))
    return out


def _parse_inp(path: str) -> List[VarSpec]:
    """解析 .inp,生成所有 (block, keyword, value_idx) 的 VarSpec。

    包含两类语句:
    - 顶层语句 ``inp.top_stmts``(block 字段填 ``"<top>"``,key 无 ``.`` 前缀)
    - 块内语句 ``inp.block_list[].statements``(block 填块名,key 形如
      ``block.keyword[idx]``)
    """
    inp = parser.parse_file(path)
    out: List[VarSpec] = []
    # 顶层语句:celltypes / infsets / runtype / ... — Sweep 重要来源
    for stmt in inp.top_stmts:
        for vi, v in enumerate(stmt.values):
            kind = _infer_kind_for_sweep(v.typed)
            raw = str(v.typed) if v.typed is not None else ""
            key = "{}[{}]".format(stmt.keyword, vi)
            label = "{} [{}] = {}".format(key, kind, raw)
            out.append(VarSpec(
                key=key, label=label, kind=kind,
                block="<top>", keyword=stmt.keyword, value_idx=vi,
            ))
    # 块内语句
    for blk in inp.block_list:
        for stmt in blk.statements:
            for vi, v in enumerate(stmt.values):
                kind = _infer_kind_for_sweep(v.typed)
                raw = str(v.typed) if v.typed is not None else ""
                key = "{}.{}[{}]".format(blk.name, stmt.keyword, vi)
                label = "{} [{}] = {}".format(key, kind, raw)
                out.append(VarSpec(
                    key=key, label=label, kind=kind,
                    block=blk.name, keyword=stmt.keyword, value_idx=vi,
                ))
    return out


def enumerate_vars(template_path: Optional[str]) -> List[VarSpec]:
    """根据模板路径返回 :class:`VarSpec` 列表。

    - template_path 为空(None 或空串)→ 仅 3 个枚举轴
    - template_path 存在但解析失败 → 仅 3 个枚举轴(不抛)
    - 否则 → 解析 .inp,枚举所有 (block, keyword, value_idx)

    返回列表:枚举轴在前,.inp 变量在后;同 group 内顺序由实现定义。
    """
    enum_specs = _enum_axis_specs()
    if not template_path:
        return enum_specs
    try:
        inp_specs = _parse_inp(template_path)
    except Exception:
        return enum_specs  # 解析失败:静默退化为仅枚举轴
    return enum_specs + inp_specs
