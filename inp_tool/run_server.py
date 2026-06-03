"""
启动 inp_tool Web GUI
"""
import sys
from pathlib import Path

# 把项目根加到 sys.path
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("  inp_tool Web GUI v0.3")
    print("  mcfd.inp 浏览器编辑器")
    print("=" * 60)
    print()
    print("  浏览器打开: http://127.0.0.1:8765")
    print("  API 文档:   http://127.0.0.1:8765/docs")
    print()
    print("  Ctrl+C 停止")
    print()
    uvicorn.run("inp_tool.api:app", host="127.0.0.1", port=8765, log_level="info", reload=False)
