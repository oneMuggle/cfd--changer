"""
mcfd.inp 工具包 v0.4

v0.4 变更:
- 新增 sweep 批量算例生成器(inp_tool.sweep)
  - FreestreamPreset: 几何分解 (alpha, beta, Ma) → (U, V, W) + refvel
  - CaseSweep: YAML/JSON 配置
  - generate(): 笛卡尔积展开 → N 个 .inp + manifest.json
  - CLI: `inp-tool sweep <template> <config.json>`
  - API: `POST /api/sweep`

v0.3 变更:
- 完整 Python 包工程化(pyproject.toml / __main__.py / pytest 套件)
- 80% 测试覆盖率(parser / writer / diff / cli / api 五大模块)
- Web GUI 暴露为 `inp-tool-api` console_script
"""
from .model import InpFile, Block, Stmt, Value, infer_type
from .parser import parse, parse_file
from .writer import to_text, write, write_bytes
from .diff import diff, DiffReport, DiffEntry
from .sweep import (
    SweepSpec,
    expand_cartesian,
    FreestreamPreset,
    render_case_name,
    CaseResult,
    SweepReport,
    CaseSweep,
    generate,
    CopyStrategy,        # v0.8.0
    DEFAULT_EXCLUDE,     # v0.8.0
)

__all__ = [
    'InpFile', 'Block', 'Stmt', 'Value', 'infer_type',
    'parse', 'parse_file',
    'to_text', 'write', 'write_bytes',
    'diff', 'DiffReport', 'DiffEntry',
    # v0.4 sweep
    'SweepSpec', 'expand_cartesian', 'FreestreamPreset',
    'render_case_name', 'CaseResult', 'SweepReport',
    'CaseSweep', 'generate',
    # v0.8.0 整算例目录模式
    'CopyStrategy', 'DEFAULT_EXCLUDE',
]
__version__ = '0.7.1'
