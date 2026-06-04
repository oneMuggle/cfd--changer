#!/usr/bin/env bash
#
# Linux / macOS 构建脚本
# 默认产出 dist/inp-tool(单文件),--mode onedir 产出 dist/inp-tool-dist/ 目录
#
# 用法(必须先激活 cfdchanger 环境):
#   conda activate cfdchanger
#   ./scripts/build.sh                          # 默认 onefile
#   ./scripts/build.sh --mode onedir           # 目录式,启动快
#   ./scripts/build.sh --mode onefile          # 显式单文件
#
# 或一行搞定:
#   conda run -n cfdchanger ./scripts/build.sh

set -e

# 默认模式
MODE="onefile"
for arg in "$@"; do
    case "$arg" in
        --mode) shift; MODE="$1"; shift ;;
        --mode=*) MODE="${arg#--mode=}"; shift ;;
    esac
done

if [ "$MODE" != "onefile" ] && [ "$MODE" != "onedir" ]; then
    echo "✗ 未知 --mode: $MODE (期望 onefile 或 onedir)" >&2
    exit 1
fi

# 切到项目根(inp_tool/)
cd "$(dirname "$0")/../inp_tool"

# 确认在正确的 conda 环境
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "✗ PyInstaller 未安装!" >&2
    echo "  请先: conda activate cfdchanger" >&2
    echo "  然后: pip install -e '.[build]'" >&2
    exit 1
fi

echo "==> [1/5] 检查 PyInstaller (mode=$MODE)"
python -c "import PyInstaller; print('  PyInstaller', PyInstaller.__version__)"

echo "==> [2/5] 清理上次构建"
rm -rf build dist
mkdir -p dist

# 选 spec
case "$MODE" in
    onefile)  SPEC="inp_tool.spec"          ;;
    onedir)   SPEC="inp_tool_onedir.spec"   ;;
esac

echo "==> [3/5] PyInstaller 构建 ($SPEC)"
pyinstaller --clean --noconfirm "$SPEC"

echo "==> [4/5] 验证产物"
case "$MODE" in
    onefile)
        if [ ! -f dist/inp-tool ]; then
            echo "✗ dist/inp-tool 不存在!" >&2
            exit 1
        fi
        chmod +x dist/inp-tool
        echo "  ✓ dist/inp-tool ($(du -h dist/inp-tool | cut -f1))"
        TARGET="./dist/inp-tool"
        ;;
    onedir)
        if [ ! -f dist/inp-tool-dist/inp-tool ]; then
            echo "✗ dist/inp-tool-dist/inp-tool 不存在!" >&2
            exit 1
        fi
        chmod +x dist/inp-tool-dist/inp-tool
        echo "  ✓ dist/inp-tool-dist/ ($(du -sh dist/inp-tool-dist/ | cut -f1))"
        echo "  ✓ dist/inp-tool-dist/inp-tool ($(du -h dist/inp-tool-dist/inp-tool | cut -f1))"
        TARGET="./dist/inp-tool-dist/inp-tool"
        ;;
esac

# 烟雾测试
echo "==> [5/5] 烟雾测试: --version"
$TARGET --version

echo "==> 烟雾测试: --help"
$TARGET --help | head -3

echo ""
echo "✓ Build 完成! (mode=$MODE)"
echo "  产物: $(pwd)/$TARGET"
