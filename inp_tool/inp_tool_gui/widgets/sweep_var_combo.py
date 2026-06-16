"""Sweep 变量发现 + 类型元数据(纯 Python,无 PySide2)。

v0.17 引入,与 SweepController 配合:
- :class:`VarSpec` — 单变量 UI 描述(frozen dataclass)
- :func:`enumerate_vars` — 给定模板路径,返回 :class:`VarSpec` 列表
  (枚举轴 + .inp 变量)

不依赖 PySide2,可被 controller 和测试独立 import。
"""
from dataclasses import dataclass
from typing import Optional, Tuple


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
