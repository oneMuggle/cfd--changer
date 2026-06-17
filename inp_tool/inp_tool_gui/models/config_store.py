"""ConfigStore: 不可变 sweep 配置 + AxisSpec / ConditionalRule 模型。"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class AxisSpec:
    """单轴值规范。kind 决定 values / range_* 字段语义。"""
    kind: str  # "enum_subset" | "explicit_list" | "range" | "csv_str"
    values: Tuple[Any, ...] = ()
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    range_step: Optional[float] = None