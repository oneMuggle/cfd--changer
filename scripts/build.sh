#!/usr/bin/env bash
#
# Linux / macOS 构建脚本
# 默认产出 dist/inp-tool(单文件),--mode onedir 产出 dist/inp-tool-dist/ 目录
# --mode gui 产出 dist/inp-tool-gui(PySide2 桌面 GUI,W7 兼容)
#
# 用法(必须先激活 cfdchanger 环境):
#   conda activate cfdchanger
#   ./scripts/build.sh                          # 默认 onefile(CLI)
#   ./scripts/build.sh --mode onedir           # 目录式(CLI)
#   ./scripts/build.sh --mode onefile          # 显式单文件(CLI)
#   ./scripts/build.sh --mode gui              # PySide2 GUI(Win7 兼容)
#
# 或一行搞定:
#   conda run -n cfdchanger ./scripts/build.sh
#
# GUI 模式注意:
#   - 需先装 [gui-build] extras: pip install -e ".[gui-build]"
#   - GUI EXE 启动需要桌面 session(Win7 SP1 / Linux X11 / macOS Aqua)
#   - offscreen 烟雾:QT_QPA_PLATFORM=offscreen ./dist/inp-tool-gui --help
#     (注:PySide2 GUI app 没有 --help,但 import 主窗口模块不崩即视为通过)

set -e

# 默认模式
MODE="onefile"
for arg in "$@"; do
    case "$arg" in
        --mode) shift; MODE="$1"; shift ;;
        --mode=*) MODE="${arg#--mode=}"; shift ;;
    esac
done

if [ "$MODE" != "onefile" ] && [ "$MODE" != "onedir" ] && [ "$MODE" != "gui" ]; then
    echo "✗ 未知 --mode: $MODE (期望 onefile / onedir / gui)" >&2
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

# GUI 模式额外检查 PySide2
if [ "$MODE" == "gui" ]; then
    if ! python -c "import PySide2" 2>/dev/null; then
        echo "✗ PySide2 未安装!" >&2
        echo "  GUI 模式需: pip install -e '.[gui-build]'" >&2
        echo "  (gui-build 含 PySide2==5.15.2.1 + pyinstaller==6.16.0)" >&2
        exit 1
    fi
fi

echo "==> [1/5] 检查依赖 (mode=$MODE)"
python -c "import PyInstaller; print('  PyInstaller', PyInstaller.__version__)"
if [ "$MODE" == "gui" ]; then
    python -c "import PySide2; print('  PySide2', PySide2.__version__)"
fi

echo "==> [2/5] 清理上次构建"
rm -rf build dist
mkdir -p dist

# 选 spec
case "$MODE" in
    onefile)  SPEC="inp_tool.spec"          ;;
    onedir)   SPEC="inp_tool_onedir.spec"   ;;
    gui)      SPEC="inp_tool_gui.spec"      ;;
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
        # v0.4.2: onedir spec 自包含 deps,产物在 dist/inp-tool,move 到 dist/inp-tool-dist/
        if [ ! -f dist/inp-tool ]; then
            echo "✗ dist/inp-tool 不存在!" >&2
            exit 1
        fi
        rm -rf dist/inp-tool-dist
        mkdir -p dist/inp-tool-dist
        mv dist/inp-tool dist/inp-tool-dist/inp-tool
        chmod +x dist/inp-tool-dist/inp-tool
        echo "  ✓ dist/inp-tool-dist/ ($(du -sh dist/inp-tool-dist/ | cut -f1))"
        echo "  ✓ dist/inp-tool-dist/inp-tool ($(du -h dist/inp-tool-dist/inp-tool | cut -f1))"
        TARGET="./dist/inp-tool-dist/inp-tool"
        ;;
    gui)
        # v0.14.1: GUI 单文件(~73 MB),含 PySide2 + Qt5 运行时
        if [ ! -f dist/inp-tool-gui ]; then
            echo "✗ dist/inp-tool-gui 不存在!" >&2
            exit 1
        fi
        chmod +x dist/inp-tool-gui
        echo "  ✓ dist/inp-tool-gui ($(du -h dist/inp-tool-gui | cut -f1))"
        TARGET="./dist/inp-tool-gui"
        ;;
esac

# 烟雾测试
echo "==> [5/5] 烟雾测试"
case "$MODE" in
    onefile|onedir)
        $TARGET --version
        $TARGET --help | head -3
        ;;
    gui)
        # GUI 模式不启动主窗口(避免 CI runner 无桌面 session 卡死)
        # 用 offscreen 平台 import 主窗口模块,验证依赖图完整
        QT_QPA_PLATFORM=offscreen python -c "
import sys
from PySide2 import __version__ as pyside2_ver
from PySide2.QtWidgets import QApplication
app = QApplication([])
from inp_tool_gui.main_window import MainWindow
w = MainWindow()
print('  ✓ MainWindow import OK (PySide2', pyside2_ver + ')')
print('  ✓ Title:', w.windowTitle())
" 2>&1 | grep -E '(OK|✓|Error|Traceback)'
        ;;
esac

echo ""
echo "✓ Build 完成! (mode=$MODE)"
echo "  产物: $(pwd)/$TARGET"
