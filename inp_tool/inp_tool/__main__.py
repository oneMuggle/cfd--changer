"""
inp_tool 的 python -m 入口

用法:
    python -m inp_tool info file.inp
    python -m inp_tool get file.inp key -b block
    python -m inp_tool --version

委派给 inp_tool.cli.main。
"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
