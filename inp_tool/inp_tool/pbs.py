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


def validate_base_case_dir(
    source_dir: str,
    pbs_enabled: bool = True,
) -> List["PbsIssue"]:
    """检查基础算例目录的完整性。返回 issues 列表(error + warning)。

    文件级检查(本任务):
    - mcfd.inp 存在(若缺失,先返回)
    - cellsin.bin / nodesin.bin / cgrpsin.bin* 网格文件(警告)
    - *.dat 物性文件 ≥ 1(警告)
    - mcfd.bc / mcfd.grp 配置(警告)
    - run_*.pbs 模板(pbs_enabled=True 时检查,警告)

    注:Task 7 会追加 block 级检查
    """
    issues: List[PbsIssue] = []
    p = Path(source_dir)

    # mcfd.inp 必须存在
    mcfd_path = p / "mcfd.inp"
    if not mcfd_path.is_file():
        issues.append(PbsIssue(
            code="MISSING_MCFD_INP",
            severity="error",
            path=str(mcfd_path),
            message=f"找不到 mcfd.inp: {mcfd_path}",
        ))
        return issues  # 后续检查无意义

    # 网格文件(软提示)
    for gf in ["cellsin.bin", "nodesin.bin"]:
        if not (p / gf).exists():
            issues.append(PbsIssue(
                code=f"MISSING_GRID:{gf}",
                severity="warning",
                path=str(p / gf),
                message=f"缺失网格文件 {gf}",
            ))
    # cgrpsin.bin* glob
    if not list(p.glob("cgrpsin.bin*")):
        issues.append(PbsIssue(
            code="MISSING_GRID:cgrpsin.bin*",
            severity="warning",
            path=str(p / "cgrpsin.bin*"),
            message="缺失网格族文件 cgrpsin.bin*",
        ))

    # 物性 *.dat(至少 1 个)
    if not list(p.glob("*.dat")):
        issues.append(PbsIssue(
            code="MISSING_PROPERTY:*.dat",
            severity="warning",
            path=str(p / "*.dat"),
            message="缺失物性文件(*.dat)",
        ))

    # mcfd.bc / mcfd.grp
    for cfg in ["mcfd.bc", "mcfd.grp"]:
        if not (p / cfg).exists():
            issues.append(PbsIssue(
                code=f"MISSING_CONFIG:{cfg}",
                severity="warning",
                path=str(p / cfg),
                message=f"缺失配置文件 {cfg}",
            ))

    # pbs 模板(仅当 pbs_enabled=True)
    if pbs_enabled and not list(p.glob("run_*.pbs")):
        issues.append(PbsIssue(
            code="MISSING_PBS_TEMPLATE",
            severity="warning",
            path=str(p / "run_*.pbs"),
            message="基础算例目录里没有 run_*.pbs 模板,生成 pbs 将自动关闭",
        ))

    # === block 级检查(Task 7) ===
    from .parser import parse_file
    try:
        inp = parse_file(str(mcfd_path))
    except Exception as e:
        issues.append(PbsIssue(
            code="MCFD_PARSE_ERROR",
            severity="error",
            path=str(mcfd_path),
            message=f"mcfd.inp 解析失败: {e}",
        ))
        return issues

    for blk in ["tsteps", "physics"]:
        if inp.get_block(blk) is None:
            # v0.9.0 注:tsteps/physics 降为 warning(向后兼容老 fixture 用
            # tsteps/end 格式的 .inp);严格 error 模式留给 v0.9.x 后期或 v0.10
            issues.append(PbsIssue(
                code=f"MISSING_BLOCK:{blk}",
                severity="warning",
                path=f"{mcfd_path}#{blk}",
                message=f"mcfd.inp 缺 '{blk}' block(标准 mcfd 用 '{blk} begin/end' 格式)",
            ))
    for blk in ["chemkin", "restart"]:
        if inp.get_block(blk) is None:
            issues.append(PbsIssue(
                code=f"MISSING_BLOCK:{blk}",
                severity="warning",
                path=f"{mcfd_path}#{blk}",
                message=f"mcfd.inp 缺可选 block '{blk}'(部分算例类型需要)",
            ))

    return issues


_PBS_N_PATTERN = re.compile(r"^[ \t]*#PBS[ \t]+-N[ \t]+\S+", re.MULTILINE)


def write_pbs(
    template_path: str,
    output_path: str,
    job_name: str,
    template_text: Optional[str] = None,
) -> None:
    """从 template_path 读取 pbs 脚本,把 #PBS -N 替换为 job_name,写出到 output_path。

    规则:
    - 若模板含 #PBS -N → 原地替换(保留缩进/格式)
    - 若模板不含 → 在 shebang 之后追加一行 #PBS -N job_name
    - job_name 会先过 sanitization
    - 若传 template_text(已读好的 in-memory 内容)→ 优先用,避免 hardlink 副作用下重复读源
    """
    if template_text is not None:
        text = template_text
    else:
        tp = Path(template_path)
        if not tp.is_file():
            raise FileNotFoundError(f"pbs 模板不存在: {template_path}")
        text = tp.read_text()
    # 字符兜底
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", job_name)

    if _PBS_N_PATTERN.search(text):
        new_text = _PBS_N_PATTERN.sub(f"#PBS -N {safe_name}", text, count=1)
    else:
        # 在 shebang 之后插入(若没有 shebang 则在文件开头)
        lines = text.splitlines(keepends=True)
        insert_idx = 0
        for i, ln in enumerate(lines):
            if ln.startswith("#!"):
                insert_idx = i + 1
                break
        lines.insert(insert_idx, f"#PBS -N {safe_name}\n")
        new_text = "".join(lines)

    Path(output_path).write_text(new_text)
