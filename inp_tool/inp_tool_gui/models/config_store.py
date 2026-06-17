"""ConfigStore: 不可变 sweep 配置 + AxisSpec / ConditionalRule 模型。"""
import dataclasses
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


@dataclass(frozen=True)
class ConditionalRule:
    """(when, then) 一条规则。"""
    when: Any  # inp_tool.sweep.ConditionWhen
    then: Any  # inp_tool.sweep.ConditionThen


@dataclass(frozen=True)
class ConfigStore:
    """不可变 sweep 配置;所有修改走 replace 系列方法返回新实例。"""
    template: str
    output_dir: str
    naming: str
    preset_ref: Optional[str]
    sweeps: Dict[str, AxisSpec] = field(default_factory=dict)
    conditions: Tuple[ConditionalRule, ...] = ()

    @property
    def case_count(self) -> int:
        """笛卡尔积预估(无 condition 时)。"""
        if not self.sweeps:
            return 0
        n = 1
        for spec in self.sweeps.values():
            if spec.kind == "range" and spec.range_step:
                n *= int((spec.range_max - spec.range_min) / spec.range_step) + 1
            else:
                n *= max(len(spec.values), 1)
        return n

    def replace(self, **kwargs) -> "ConfigStore":
        return dataclasses.replace(self, **kwargs)

    def replace_sweep(self, key: str, spec: AxisSpec) -> "ConfigStore":
        new_sweeps = dict(self.sweeps)
        new_sweeps[key] = spec
        return self.replace(sweeps=new_sweeps)

    def remove_sweep(self, key: str) -> "ConfigStore":
        new_sweeps = {k: v for k, v in self.sweeps.items() if k != key}
        return self.replace(sweeps=new_sweeps)

    def add_condition(self, rule: ConditionalRule) -> "ConfigStore":
        return self.replace(conditions=self.conditions + (rule,))