"""Sweep 变量发现 + 类型元数据(纯 Python,无 PySide2)。

v0.17 引入,与 SweepController 配合:
- :class:`VarSpec` — 单变量 UI 描述(frozen dataclass)
- :func:`enumerate_vars` — 给定模板路径,返回 :class:`VarSpec` 列表
  (枚举轴 + .inp 变量)

不依赖 PySide2,可被 controller 和测试独立 import。
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

from inp_tool.sweep import (
    EnergyModel, GasModel, TurbulenceModel,
)


# 枚举轴定义: key -> Enum class
_ENUM_AXIS_CLASSES = {
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


def enumerate_vars(template_path: Optional[str]) -> List[VarSpec]:
    """根据模板路径返回 :class:`VarSpec` 列表。

    - template_path 为空(None 或空串)→ 仅 3 个枚举轴
    - template_path 存在但解析失败 → 仅 3 个枚举轴(不抛,本任务范围)
    - 否则 → 解析 .inp,枚举所有 (block, keyword, value_idx)
      (Task 3 实现)

    返回列表:枚举轴在前,.inp 变量在后;同 group 内顺序由实现定义。
    """
    if not template_path:
        return _enum_axis_specs()
    # 解析 .inp(后续 Task 3 实现)
    return _enum_axis_specs()  # 暂未实现
