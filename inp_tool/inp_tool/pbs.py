"""PBS 脚本解析 / 校验 / 生成工具模块。

零运行时依赖(纯 stdlib: re / pathlib / fnmatch / dataclasses)。
"""
from __future__ import annotations

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
