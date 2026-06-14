"""``mcfd.info1`` 历程文件解析。

零运行时依赖,纯 Python stdlib。

文件格式(摘自 ``reference/full_case/Case/mcfd.info1``,行号 = 截取 fixture 行号)::

    At the beginning of this run:        ← line 1-11  header,跳过
    reflen: reference length = 1.0e+00
    ...
    nt 1 tau 0.0e+00 time 0.0e+00       ← line 12  新 step 起点
    For selector 1, # of boundary faces = 16079
    nbc =    1, total inviscid viscous, nondimensional   ← line 14  跳过(nondim)
    energy flux ...                       ← line 15-22  10 行物理量(跳过 areas/areamoments)
    ...
    nbc =   1, total inviscid viscous, dimensional       ← line 25  累加!
    energy flux  -4.27e-06  -4.27e-06   0.0e+00
    mass   flux  -1.90e-12  -1.90e-12   0.0e+00
    x force      5.67e+06    5.67e+06   0.0e+00         ← 行 0(force/moment 6 列开始)
    y force      9.83e+06    9.83e+06   0.0e+00
    z force     -2.01e+07   -2.01e+07   0.0e+00
    x moment     3.28e+08    3.28e+08   0.0e+00
    y moment     1.26e+09    1.26e+09   0.0e+00
    z moment     7.07e+08    7.07e+08   0.0e+00
    areas        ...                                      ← 跳过 1 行
    areamoments  ...                                      ← 跳过 1 行
    [新 selector 2 section 同上格式]
    nt 2 tau 0.0e+00 time 0.0e+00       ← 新 step 触发 flush

规则:
- 仅累加 ``dimensional`` 段;``nondimensional`` 段跳过(否则会双倍计数)
- ``op_ibd`` 控制累加范围:每个 ``nbc = <id>`` 段若 ``id ∈ op_ibd`` 则加,否则跳过
- 每段 8 个物理量行:energy flux / mass flux / x force / y force / z force / x moment / y moment / z moment
  取后 6 个(force + moment),每行 3 数(total / inviscid / viscous)
- EOF 时必须把最后累积的 ``current`` flush 进结果(reference bug 修复)

跟 reference (``CFDPlus_V4.py:read_info1_file``)的差异:
- 修了 EOF flush bug(reference 把最后一个 step 的累积值丢了)
- 返回 ``list[Info1Step]`` dataclass 而非 ``(step, time, formom dict)`` 元组
- ``op_ibd`` 不匹配时,该 step 仍保留(force 全零),不静默吞 step
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

# 6 元 tuple: (Fx, Fy, Fz, Mx, My, Mz)
Vec6 = Tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class Info1Step:
    """``mcfd.info1`` 中单个时间步的力/矩积分结果。

    每个字段是 6 元 tuple ``(Fx, Fy, Fz, Mx, My, Mz)``:
    - ``total``:总力/矩(物面积分 dimensional)
    - ``inv``:无黏力/矩(inviscid 列)
    - ``vis``:粘性力/矩(viscous 列)
    """
    step: int
    time: float
    total: Vec6
    inv: Vec6
    vis: Vec6


def read_info1(
    path: Union[str, Path],
    op_ibd: Sequence[int],
) -> List[Info1Step]:
    """读 ``mcfd.info1`` 文件,返回每个时间步在 ``op_ibd`` 联合边界上的积分。

    参数:
    - ``path``:``mcfd.info1`` 路径
    - ``op_ibd``:积分操作的边界编号列表(单边界用 ``[1]``,多边界合并用 ``[1, 2]``)

    返回:列表,每元素是一个 ``Info1Step``。

    若文件不存在抛 ``FileNotFoundError``;空文件 / 无 ``nt`` 标记 → 返回空列表。
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"mcfd.info1 not found: {p}")

    op_set = set(op_ibd)
    steps: List[Info1Step] = []
    current: Optional[_StepAccumulator] = None

    with p.open("r", encoding="utf-8") as f:
        line = f.readline()
        while line:
            parts = line.split()
            if _is_nt_line(parts):
                # 新 step 起点 — 先把上一个 flush 出来
                if current is not None:
                    steps.append(current.to_info1_step())
                current = _StepAccumulator(
                    step=int(parts[1]),
                    time=float(parts[5]),
                )
            elif current is not None and _is_dimensional_nbc(parts):
                bc_id = _parse_nbc_id(parts[2])
                if bc_id is not None and bc_id in op_set:
                    _accumulate_section(f, current)
                # 不匹配也要把这 10 行跳过(否则数据流错位),但因后续循环
                # 会读到下一个有意义的 token(nt / nbc),不必显式跳行
            line = f.readline()

    # EOF flush — reference 把这步漏了,导致最后一个 step 力值丢失
    if current is not None:
        steps.append(current.to_info1_step())

    return steps


def is_viscous(steps: Sequence[Info1Step]) -> bool:
    """任一 step 的任一 viscous 分量非零 → True。"""
    return any(any(v != 0.0 for v in s.vis) for s in steps)


def find_total_force_file(case_dir: Union[str, Path]) -> Optional[Path]:
    """在算例目录下找总力历程文件(``minfo1_e1`` 或 ``minfo1_e1_<op>``)。

    排除 ``_inviscid`` / ``_viscous`` 后缀的辅助文件。
    多个匹配时取字典序最小(stable),无匹配返回 ``None``。
    """
    d = Path(case_dir)
    candidates = sorted(d.glob("minfo1_e1*"))
    for c in candidates:
        name = c.name
        if name.endswith("_inviscid") or name.endswith("_viscous"):
            continue
        return c
    return None


# ============================================================================
# 内部:状态机辅助
# ============================================================================

@dataclass
class _StepAccumulator:
    """单步累加器:对 op_ibd 范围内的 dimensional 段做向量加法。"""
    step: int
    time: float
    total: List[float] = field(default_factory=lambda: [0.0] * 6)
    inv: List[float] = field(default_factory=lambda: [0.0] * 6)
    vis: List[float] = field(default_factory=lambda: [0.0] * 6)

    def add_section(self, total: Sequence[float],
                    inv: Sequence[float],
                    vis: Sequence[float]) -> None:
        for i in range(6):
            self.total[i] += total[i]
            self.inv[i] += inv[i]
            self.vis[i] += vis[i]

    def to_info1_step(self) -> Info1Step:
        return Info1Step(
            step=self.step,
            time=self.time,
            total=tuple(self.total),  # type: ignore[arg-type]
            inv=tuple(self.inv),      # type: ignore[arg-type]
            vis=tuple(self.vis),      # type: ignore[arg-type]
        )


def _is_nt_line(parts: Sequence[str]) -> bool:
    """``nt 1 tau X time Y`` 至少 6 列,且第 2 / 6 列可解析。"""
    if len(parts) < 6 or parts[0] != "nt":
        return False
    return _is_int_token(parts[1]) and _is_float_token(parts[5])


def _is_dimensional_nbc(parts: Sequence[str]) -> bool:
    """``nbc =    1,    total    inviscid    viscous, dimensional``

    parts after split:
        ['nbc', '=', '1,', 'total', 'inviscid', 'viscous,', 'dimensional']
    """
    return (
        len(parts) > 6
        and parts[0] == "nbc"
        and parts[6] == "dimensional"
    )


def _parse_nbc_id(token: str) -> Optional[int]:
    """从 ``"1,"`` 提出 ``1``;失败返回 None。"""
    cleaned = token.rstrip(",")
    if _is_int_token(cleaned):
        return int(cleaned)
    return None


def _accumulate_section(f, current: _StepAccumulator) -> None:
    """读 nbc 段后续 10 行,提 force/moment 6 行(跳过 energy/mass flux + areas/areamoments)。

    nbc 段后的 10 行结构(每行 3 数 = total / inviscid / viscous,除 areas/areamoments):
        line 1: energy flux  (skip — not 6-vector)
        line 2: mass flux    (skip — not 6-vector)
        line 3: x force      → total[0], inv[0], vis[0]
        line 4: y force      → total[1], inv[1], vis[1]
        line 5: z force      → total[2], inv[2], vis[2]
        line 6: x moment     → total[3], inv[3], vis[3]
        line 7: y moment     → total[4], inv[4], vis[4]
        line 8: z moment     → total[5], inv[5], vis[5]
        line 9: areas        (skip)
        line 10: areamoments (skip)

    每个值行格式::
        x force      5.6728762e+06  5.6728762e+06  0.0000000e+00
        ↑label词           ↑total       ↑inviscid       ↑viscous
    """
    # skip energy flux + mass flux
    f.readline()
    f.readline()

    total = [0.0] * 6
    inv = [0.0] * 6
    vis = [0.0] * 6
    for axis in range(6):  # x force, y force, z force, x moment, y moment, z moment
        line = f.readline()
        nums = _tail_floats(line, count=3)
        if nums is None:
            # 文件格式被破坏,放弃本段(不更新 current)
            return
        total[axis] = nums[0]
        inv[axis] = nums[1]
        vis[axis] = nums[2]

    # skip areas + areamoments
    f.readline()
    f.readline()

    current.add_section(total, inv, vis)


def _tail_floats(line: str, count: int) -> Optional[Tuple[float, ...]]:
    """提取行末尾 ``count`` 个浮点数,失败返回 None。"""
    parts = line.split()
    if len(parts) < count:
        return None
    try:
        return tuple(float(x) for x in parts[-count:])
    except ValueError:
        return None


def _is_int_token(s: str) -> bool:
    if not s:
        return False
    body = s[1:] if s[0] in "+-" else s
    return body.isdigit()


def _is_float_token(s: str) -> bool:
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False
