#!/usr/bin/env bash
# scripts/run_sweep.sh - 批跑 sweep 的环境封装
#
# 用法:
#   ./run_sweep.sh <config.json|yaml> [extra sweep flags...]
#
# 示例:
#   ./run_sweep.sh scripts/tests/fixtures/sweep_min.json
#   ./run_sweep.sh my.yaml --alpha 0,5,10 --mach 0.85
#
# 要求:
#   - conda 环境名 cfdchanger 存在
#   - 仓库根目录下有 inp_tool/ 子目录
#
# 默认输出目录: /tmp/inp_verify/run_sweep_<YYYYMMDD_HHMMSS>/
# 默认 manifest: <out>/manifest.json
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <config.json|yaml> [--alpha ...] [--out ...]" >&2
    exit 2
fi

CFG="$1"; shift
# 切到 INP_TOOL_DIR 之前先转绝对路径,否则 cd 后相对路径解析不到
CFG="$(cd "$(dirname "$CFG")" && pwd)/$(basename "$CFG")"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INP_TOOL_DIR="$REPO_ROOT/inp_tool"

[[ -d "$INP_TOOL_DIR" ]] || { echo "error: $INP_TOOL_DIR not found" >&2; exit 2; }

# 验证 conda env
if ! conda run -n cfdchanger python -c "import sys; sys.exit(0)" 2>/dev/null; then
    echo "error: conda env 'cfdchanger' not available" >&2
    exit 2
fi

# 验证 config 文件存在
[[ -f "$CFG" ]] || { echo "error: config not found: $CFG" >&2; exit 2; }

# 默认输出目录(可被 config 内部 output_dir 字段覆盖)
TS="$(date +%Y%m%d_%H%M%S)"
OUT_DEFAULT="/tmp/inp_verify/run_sweep_$TS"

echo "[$(date +%H:%M:%S)] run_sweep start"
echo "  config:  $CFG"
echo "  extra:   $*"

cd "$INP_TOOL_DIR"
conda run -n cfdchanger python -m inp_tool.cli sweep \
    --out "$OUT_DEFAULT" \
    --manifest "$OUT_DEFAULT/manifest.json" \
    -v \
    "$@" \
    "$CFG"

echo "[$(date +%H:%M:%S)] run_sweep done -> $OUT_DEFAULT"
