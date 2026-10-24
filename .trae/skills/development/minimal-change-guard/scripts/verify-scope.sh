#!/usr/bin/env bash
# 最小改动守卫：把工作区实际变更文件与 expected-files 白名单核对。
# Usage: verify-scope.sh <expected-file> [<expected-file> ...]
# 退出码：0 = PASS（actual ⊆ expected）；1 = FAIL；2 = 用法错误
# 只读取 git 状态，不修改任何文件，不执行任何写操作。
set -uo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: verify-scope.sh <expected-file> [<expected-file> ...]" >&2
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit 2

# 预期白名单（归一化排序）
EXPECTED="$(printf '%s\n' "$@" | sed 's#^\./##' | sort -u)"

# 实际已跟踪文件改动（unstaged + staged），仅取内容修改类状态
ACTUAL="$( { git diff --name-only --diff-filter=ACMR; git diff --cached --name-only --diff-filter=ACMR; } | sort -u )"
# 未跟踪文件（单独提示）
UNTRACKED="$(git ls-files --others --exclude-standard | sort -u)"

echo "== git diff --check =="
if git diff --check; then echo "OK (no whitespace errors)"; fi
echo
echo "== git diff --stat =="
git diff --stat
echo
echo "== git diff --numstat =="
git diff --numstat
echo

VIOLATIONS="$(comm -23 <(echo "$ACTUAL") <(echo "$EXPECTED"))"
UNUSED="$(comm -13 <(echo "$ACTUAL") <(echo "$EXPECTED"))"

echo "== expected files =="
echo "$EXPECTED" | sed 's/^/  /'
echo
echo "== actual changed files =="
if [ -n "$ACTUAL" ]; then echo "$ACTUAL" | sed 's/^/  /'; else echo "  (none)"; fi
echo

FAIL=0
echo "== verdict =="
if [ -n "$VIOLATIONS" ]; then
  echo "FAIL — changed files outside expected scope:"
  echo "$VIOLATIONS" | sed 's/^/  X /'
  FAIL=1
else
  echo "OK — all changed files are within expected scope"
fi

if [ -n "$UNUSED" ]; then
  echo "WARN — expected but not changed (informational, not a failure):"
  echo "$UNUSED" | sed 's/^/  ? /'
fi

if [ -n "$UNTRACKED" ]; then
  echo "WARN — untracked files present (review before commit):"
  echo "$UNTRACKED" | sed 's/^/  U /'
fi

exit "$FAIL"
