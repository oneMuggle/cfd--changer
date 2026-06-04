#!/usr/bin/env bash
#
# Linux / macOS 构建脚本
# 产出 dist/inp-tool (单文件,无需 Python 环境)
#
# 用法(必须先激活 cfdchanger 环境):
#   conda activate cfdchanger
#   ./scripts/build.sh
#
# 或一行搞定:
#   conda run -n cfdchanger ./scripts/build.sh

set -e

# 切到项目根(inp_tool/)
cd "$(dirname "$0")/../inp_tool"

# 确认在正确的 conda 环境
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "✗ PyInstaller 未安装!" >&2
    echo "  请先: conda activate cfdchanger" >&2
    echo "  然后: pip install -e '.[build]'" >&2
    exit 1
fi

echo "==> [1/4] 检查 PyInstaller"
python -c "import PyInstaller; print('  PyInstaller', PyInstaller.__version__)"

echo "==> [2/4] 清理上次构建"
rm -rf build dist
mkdir -p dist

echo "==> [3/4] PyInstaller 构建"
pyinstaller --clean --noconfirm inp_tool.spec

echo "==> [4/4] 验证产物"
if [ ! -f dist/inp-tool ]; then
    echo "✗ dist/inp-tool 不存在!" >&2
    exit 1
fi

chmod +x dist/inp-tool
echo "  ✓ dist/inp-tool ($(du -h dist/inp-tool | cut -f1))"

# 烟雾测试
echo "==> 烟雾测试: --version"
./dist/inp-tool --version

echo "==> 烟雾测试: --help"
./dist/inp-tool --help | head -5

echo ""
echo "✓ Build 完成!"
echo "  产物: $(pwd)/dist/inp-tool"
echo "  用法: ./dist/inp-tool sweep <template> <config>"
