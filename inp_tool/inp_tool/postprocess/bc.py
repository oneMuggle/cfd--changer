"""``mcfd.bc`` 边界编号→名称解析。

零运行时依赖,纯 Python stdlib。

文件格式(reference/full_case/Case/mcfd.bc 实测)::

    #BC file created by Pointwise 2024-05-13 21:37:51   ← 跳过(文件头注释)
    seq# type modi info                                  ← 跳过(列头,无 #)
    #Body                                                ← 当前边界名 = "Body"
       1    0    0    0                                  ← 绑定 id 1 → "Body"
    #HCW                                                 ← 当前边界名 = "HCW"
       2    0    0    0                                  ← 绑定 id 2 → "HCW"

规则(沿用 reference ``CFDPlus_V4.py:parse_mcfd_bc`` 行为):
- 以 ``#BC`` 开头的注释跳过(文件头不当边界名)
- 其他 ``#<Name>`` 注释行 → ``current_name = <Name>``
- 数字开头的行 → 绑定 ``current_name`` 给 id,清空 ``current_name``
- 空白行 / 列头行(``seq# type modi info``)忽略
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Union

# 类型别名:边界编号 → 边界名
BcNameMap = Dict[int, str]


def parse_mcfd_bc(path: Union[str, Path]) -> BcNameMap:
    """解析 ``mcfd.bc`` 文件,返回 ``{boundary_id: name}`` 映射。

    抛 ``FileNotFoundError`` 如果文件不存在。
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"mcfd.bc not found: {p}")

    bc_names: BcNameMap = {}
    current_name: str = ""

    with p.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                # `#BC` 开头是文件元数据(reference 风格),跳过
                if stripped.startswith("#BC"):
                    continue
                current_name = stripped[1:].strip()
                continue
            # 非注释行:首字符为数字 → 绑定 id
            parts = stripped.split()
            if parts and current_name and _is_int_token(parts[0]):
                bc_names[int(parts[0])] = current_name
                current_name = ""
                continue
            # 其他(``seq# type modi info`` 列头等)忽略

    return bc_names


def op_label(op_ibd: Iterable[int], bc_names: BcNameMap) -> str:
    """把边界编号列表拼成可读 op 名称,如 ``[1, 2]`` → ``"Body+HCW"``。

    未在 ``bc_names`` 中的 id 回退到其数字字符串(``[99]`` → ``"99"``)。
    顺序保留,**不**去重(``[1, 1]`` → ``"Body+Body"``)。
    """
    return "+".join(bc_names.get(b, str(b)) for b in op_ibd)


# ============================================================================
# 内部工具
# ============================================================================

def _is_int_token(s: str) -> bool:
    """判断字符串是否可解析为整数(支持负号前缀)。"""
    if not s:
        return False
    body = s[1:] if s[0] in "+-" else s
    return body.isdigit()
