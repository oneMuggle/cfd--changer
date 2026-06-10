"""PBS 脚本解析 / 校验 / 生成工具模块。

零运行时依赖(纯 stdlib: re / pathlib / fnmatch / dataclasses)。
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PbsConfig:
    """PBS 脚本生成配置。"""
    enabled: bool = True
    template: Optional[str] = None
    naming: str = ""
    naming_ext: str = ""
    detect_basename: bool = True
    basename_max_len: int = 8

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PbsConfig":
        """从 dict 构造,缺失字段走默认。空 dict 返回全默认实例。"""
        if d is None:
            d = {}
        return cls(
            enabled=d.get("enabled", True),
            template=d.get("template"),
            naming=d.get("naming", ""),
            naming_ext=d.get("naming_ext", ""),
            detect_basename=d.get("detect_basename", True),
            basename_max_len=d.get("basename_max_len", 8),
        )


@dataclass
class PbsIssue:
    """完整性检查产物。"""
    code: str
    severity: str
    path: str
    message: str


def detect_pbs_template(
    source_dir: str,
    explicit_template: Optional[str] = None,
) -> Optional[str]:
    """从 source_dir 找 PBS 模板文件。返回 None 表示没找到。

    规则:
    - explicit_template 非空 → 直接返回(已存在性由调用方校验)
    - 否则在 source_dir 下 glob run_*.pbs,取第一个(字母序)
    - 多个时打印 warning 到 stderr
    """
    if explicit_template:
        return explicit_template
    p = Path(source_dir)
    if not p.is_dir():
        return None
    matches = sorted(p.glob("run_*.pbs"))
    if not matches:
        return None
    if len(matches) > 1:
        print(
            f"[warning] 发现 {len(matches)} 个 pbs 模板: "
            f"{[m.name for m in matches]},使用 {matches[0].name}",
            file=sys.stderr,
        )
    return str(matches[0])


def _axis_short(axis: str, value: float) -> str:
    """把 axis 名字 + value 渲染成短 token。

    Examples:
        ("alpha", 4)    -> "a04"
        ("alpha", 4.5)  -> "a04.5"
        ("beta", 0)     -> "b00"
        ("mach", 0.6)   -> "m0.60"
        ("mach", 0.85)  -> "m0.85"
        ("T_inf", 288.15) -> "T288"
        ("alpha", -2.0) -> "a-2.0"
    """
    prefix = axis[0]  # 保留大小写: alpha -> a, T_inf -> T
    # Python int 输入(用户显式传 int):补零到 2 位
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{prefix}{value:02d}"
    v = float(value)
    # 负数:原样保留字符串表示(保留 -2.0 的 .0)
    if v < 0:
        return f"{prefix}{v}"
    # abs >= 100:截断为整数,补零到 2 位(288.15 -> 288, 0 不补)
    if abs(v) >= 100:
        return f"{prefix}{int(v):02d}"
    # 0 < v < 100,正小数:拆分整数部分和小数部分
    int_part = int(v)
    frac = v - int_part
    if int_part == 0:
        # 小于 1:保留 2 位小数,前面带 0(0.6 -> 0.60, 0.85 -> 0.85)
        return f"{prefix}{v:.2f}"
    # >=1 且 <100:整数部分补零到 2 位,小数部分去前导 0 和尾随 0
    frac_str = f"{frac:.2f}".lstrip("0").rstrip("0")
    if not frac_str:
        frac_str = "0"
    return f"{prefix}{int_part:02d}{frac_str}"


def render_pbs_name(
    params: Dict[str, Any],
    multi_value_axes: List[str],
    base_basename: str,
    user_template: str = "",
    max_len: int = 200,
) -> str:
    """渲染 pbs 任务名。

    优先级:
    1. user_template 非空 → str.format(**params)
    2. 否则默认: {base}_{axis1_short}_{axis2_short}...
       - 仅 multi_value_axes 中的轴进入
       - 按 multi_value_axes 顺序
    3. 超 max_len 字符截断(末尾加 .)
    4. 特殊字符替换为 _
    """
    if user_template:
        name = user_template.format(**params)
    else:
        tokens = [_axis_short(ax, params[ax]) for ax in multi_value_axes if ax in params]
        if tokens:
            name = f"{base_basename}_{'_'.join(tokens)}"
        else:
            name = base_basename
    # 长度截断
    if len(name) > max_len:
        name = name[: max_len - 1] + "."
    # 字符兜底(非 [A-Za-z0-9_-])
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    return name
