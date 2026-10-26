#!/usr/bin/env bash
# mypy 基线 ratchet（F7.3 / T7.3.2）
#
# 用途：不做 mypy 存量错误全量修复，改为「错误数只允许下降、不允许上升」的基线比对。
# 基线文件：apps/api/scripts/mypy-baseline.txt（当前基线 234 errors / 32 files）。
#
# 使用方式：
#   - CI：在 apps/api 目录下由 workflow 调用，uv 可用时走 `uv run mypy`。
#   - 本地：直接执行 `bash scripts/mypy_baseline_check.sh`，自动回退到 .venv/bin/mypy。
#
# 更新基线（仅当确认存量错误被修复、数字下降，或经评审认可时）：
#   echo <new_count> > scripts/mypy-baseline.txt

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASELINE_FILE="${SCRIPT_DIR}/mypy-baseline.txt"

cd "${API_DIR}"

if [ ! -f "${BASELINE_FILE}" ]; then
  echo "ERROR: 基线文件不存在: ${BASELINE_FILE}" >&2
  exit 2
fi

# 选择 mypy 运行方式：CI 用 uv，本地回退 .venv / PATH
if command -v uv >/dev/null 2>&1; then
  MYPY_CMD=(uv run mypy)
elif [ -x ".venv/bin/mypy" ]; then
  MYPY_CMD=(.venv/bin/mypy)
elif command -v mypy >/dev/null 2>&1; then
  MYPY_CMD=(mypy)
else
  echo "ERROR: 未找到可用的 mypy（uv / .venv/bin/mypy / PATH 均不可用）" >&2
  exit 2
fi

echo "==> Running: ${MYPY_CMD[*]} src"
MYPY_OUTPUT="$("${MYPY_CMD[@]}" src 2>&1)"
MYPY_EXIT=$?
echo "${MYPY_OUTPUT}"

# 解析错误总数：匹配汇总行 "Found N errors in M files"（含单数 "Found 1 error"）
CURRENT="$(printf '%s\n' "${MYPY_OUTPUT}" | grep -oE 'Found [0-9]+ errors?' | grep -oE '[0-9]+' | head -n 1)"
CURRENT="${CURRENT:-0}"

if [ "${MYPY_EXIT}" -ne 0 ] && [ "${CURRENT}" -eq 0 ]; then
  echo "ERROR: mypy 以非零码退出但未解析到错误计数，可能是运行环境异常。" >&2
  exit 2
fi

BASELINE="$(tr -d '[:space:]' < "${BASELINE_FILE}")"

echo "==> mypy errors: current=${CURRENT}, baseline=${BASELINE}"

if [ "${CURRENT}" -gt "${BASELINE}" ]; then
  echo "FAIL: mypy 错误数 ${CURRENT} 超过基线 ${BASELINE}（新增 $((CURRENT - BASELINE)) 个）。" >&2
  echo "请修复新增的 mypy 错误；如确属预期变更，经评审后更新基线：" >&2
  echo "  echo ${CURRENT} > apps/api/scripts/mypy-baseline.txt" >&2
  exit 1
fi

echo "PASS: mypy 错误数 ${CURRENT} 未超过基线 ${BASELINE}。"
exit 0
