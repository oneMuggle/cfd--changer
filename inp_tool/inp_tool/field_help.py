"""mcfd.inp 字段含义字典(中文)。

约定:
    帮助文本面向 CFD 工程师,简明扼要(≤ 200 字)。
    不在字典中的字段返回空串 → UI 上不显示 tooltip。
"""
from typing import Dict, Tuple

FIELD_HELP: Dict[str, Dict[str, str]] = {
    "physics": {
        "reftem": "参考温度(K)。无量纲化用,典型值 288.15 或 300.0。",
        "reynolds": "参考雷诺数。基于 Lref 与参考粘性系数。",
        "gammat": "湍流模型 gamma 系数(SST k-omega 默认 5/9)。",
    },
    "guiopts": {
        "aero_ma": "来流马赫数 Ma。0.3 以下不可压,0.3-0.8 跨声速,>1 超声速。",
        "aero_alpha": "迎角(度)。正值为抬头。",
        "aero_beta": "侧滑角(度)。对称工况通常为 0。",
        "aero_temp": "来流静温(K)。",
        "aero_pres": "来流静压(Pa)。",
        "aero_Re": "来流雷诺数(基于 Lref)。",
    },
    "chemistry": {
        "model": "气体模型。常见:air5, air7, n2, o2, 11species_air。",
    },
    "turbulence": {
        "model": "湍流模型关键字,如 komega, sst, sa。",
    },
    "equation": {
        "energy": "能量方程开关。.true. 开启, .false. 关闭。",
        "turbulence": "湍流方程开关。",
        "chemistry": "组分输运开关。",
        "two_temperature": "双温度模型开关(电子温度独立求解)。",
    },
    "output": {
        "frequency": "输出频率(步数)。每 N 步写一次结果。",
    },
    "iteration": {
        "max_iter": "最大迭代步数。",
        "cfl": "CFL 数。显式格式典型 1-5。",
    },
    "grid": {
        "filename": "网格文件名(相对路径)。",
    },
}


def get_help(block: str, keyword: str) -> str:
    """取某 block.keyword 的中文说明;无记录返回空串。"""
    block_dict = FIELD_HELP.get(block)
    if not block_dict:
        return ""
    return block_dict.get(keyword, "")


def known_blocks() -> Tuple[str, ...]:
    return tuple(FIELD_HELP.keys())


def known_keywords(block: str) -> Tuple[str, ...]:
    block_dict = FIELD_HELP.get(block, {})
    return tuple(block_dict.keys())
