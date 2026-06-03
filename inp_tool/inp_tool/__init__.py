"""
mcfd.inp 工具包 v0.3

v0.3 变更:
- 完整 Python 包工程化(pyproject.toml / __main__.py / pytest 套件)
- 80% 测试覆盖率(parser / writer / diff / cli / api 五大模块)
- Web GUI 暴露为 `inp-tool-api` console_script
"""
from .model import InpFile, Block, Stmt, Value, infer_type
from .parser import parse, parse_file
from .writer import to_text, write, write_bytes
from .diff import diff, DiffReport, DiffEntry

__all__ = [
    'InpFile', 'Block', 'Stmt', 'Value', 'infer_type',
    'parse', 'parse_file',
    'to_text', 'write', 'write_bytes',
    'diff', 'DiffReport', 'DiffEntry',
]
__version__ = '0.3.0'
