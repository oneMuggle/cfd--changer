"""
inp_tool 包入口:python -m inp_tool

在 PyInstaller 打包后,相对导入失效,所以用绝对导入。
"""
import sys
from inp_tool.cli import main

if __name__ == "__main__":
    sys.exit(main())
