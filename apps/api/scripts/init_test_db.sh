#!/usr/bin/env bash
# 初始化独立测试库（dance_saas_test）：建库 → 迁移 → 种子数据
#
# 用法：
#   bash scripts/init_test_db.sh            # 在 apps/api 目录下执行
#   TEST_DB_NAME=dance_saas_ci bash scripts/init_test_db.sh
#
# 完成后运行集成测试：
#   TEST_DATABASE_URL="<测试库 URL>" .venv/bin/python -m pytest tests/integration -q
set -euo pipefail

cd "$(dirname "$0")/.."

PY_BIN=".venv/bin/python"
TEST_DB_NAME="${TEST_DB_NAME:-dance_saas_test}"

# 基础连接串：优先环境变量，其次 .env（本目录 / 上级 / 仓库根）
BASE_URL="${DATABASE_URL:-}"
if [ -z "$BASE_URL" ]; then
  for f in .env ../.env ../../.env; do
    if [ -f "$f" ]; then
      BASE_URL="$(grep -m1 '^DATABASE_URL=' "$f" | cut -d= -f2- || true)"
      [ -n "$BASE_URL" ] && break
    fi
  done
fi
if [ -z "$BASE_URL" ]; then
  echo "❌ 未找到 DATABASE_URL（环境变量或 .env）" >&2
  exit 1
fi

# 保留鉴权信息，替换库名为测试库
BASE_URL="${BASE_URL#*://}"
CRED_HOST="${BASE_URL%@*}"
CRED="${CRED_HOST}"
HOST_PORT="${BASE_URL##*@}"
HOST="${HOST_PORT%%:*}"
PORT="${HOST_PORT#*:}"
PORT="${PORT%%/*}"
TEST_URL="postgresql+asyncpg://${CRED}@${HOST}:${PORT}/${TEST_DB_NAME}"

echo "== 目标测试库: ${TEST_DB_NAME} =="

# 1. 建库（已存在则跳过）
"$PY_BIN" - "$TEST_URL" "$TEST_DB_NAME" <<'PY'
import asyncio
import sys

import asyncpg

test_url, db_name = sys.argv[1], sys.argv[2]
# asyncpg 不接受 +asyncpg 方言前缀
dsn = test_url.replace("postgresql+asyncpg://", "postgresql://")
admin_dsn = dsn.rsplit("/", 1)[0] + "/postgres"


async def main() -> None:
    conn = await asyncpg.connect(admin_dsn)
    exists = await conn.fetchval("select 1 from pg_database where datname = $1", db_name)
    if exists:
        print(f"  数据库已存在，跳过创建: {db_name}")
    else:
        await conn.execute(f'create database "{db_name}"')
        print(f"  已创建数据库: {db_name}")
    await conn.close()


asyncio.run(main())
PY

# 2. 迁移
echo "== 执行迁移 =="
DATABASE_URL="$TEST_URL" "$PY_BIN" -m alembic upgrade head

# 3. 不执行 scripts/seed.py：集成测试的租户/角色/权限/用户由
#    tests/conftest.py 的 session 级 fixture 自建（与 CI 一致），
#    预置业务数据反而会让断言基数（如列表总数）不稳定。

echo
echo "✅ 测试库就绪（结构已迁移，数据由 pytest fixture 初始化）"
echo "运行集成测试："
echo "  TEST_DATABASE_URL=\"$TEST_URL\" $PY_BIN -m pytest tests/integration -q"
