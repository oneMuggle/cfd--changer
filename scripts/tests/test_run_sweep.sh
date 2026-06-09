#!/usr/bin/env bash
# scripts/tests/test_run_sweep.sh
# 纯 bash 断言:可执行位、无参 exit 2、缺 config 失败
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/run_sweep.sh"

# Test 1: 脚本存在且可执行
[[ -x "$SCRIPT" ]] || { echo "FAIL: not executable"; exit 1; }

# Test 2: 无参数应 exit 2
set +e
"$SCRIPT" 2>/dev/null
RC=$?
set -e
[[ $RC -eq 2 ]] || { echo "FAIL: no-arg should exit 2, got $RC"; exit 1; }

# Test 3: 缺失 config 应非 0
set +e
"$SCRIPT" /no/such/file.json 2>/dev/null
RC=$?
set -e
[[ $RC -ne 0 ]] || { echo "FAIL: missing config should fail"; exit 1; }

echo "OK: run_sweep.sh basic tests"
