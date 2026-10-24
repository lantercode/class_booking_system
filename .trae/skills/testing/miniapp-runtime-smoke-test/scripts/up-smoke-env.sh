#!/usr/bin/env bash
# 幂等拉起 miniapp H5 冒烟环境：Docker(PG/Redis) → 后端 API(8000) → H5(5173)
# 已在监听的端口不重复拉起。只做启动与健康探测，不清理/重置任何数据。
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
COMPOSE="$ROOT/infra/docker/docker-compose.yml"
API_URL="http://127.0.0.1:8000/openapi.json"
H5_URL="http://localhost:5173/"

wait_http() { # $1=url $2=name $3=timeout_sec
  local i=0
  while [ "$i" -lt "$3" ]; do
    if curl -s -o /dev/null -m 2 "$1"; then echo "[$2] READY $1"; return 0; fi
    sleep 1; i=$((i+1))
  done
  echo "[$2] TIMEOUT $1" >&2; return 1
}

echo "== 1/3 postgres + redis =="
docker compose -f "$COMPOSE" up -d postgres redis

echo "== 2/3 backend api (8000) =="
if lsof -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[api] already listening"
else
  cd "$ROOT/apps/api"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PYTHONPATH=src nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/f31-api.log 2>&1 &
  echo "[api] started (log /tmp/f31-api.log)"
fi
wait_http "$API_URL" api 30

echo "== 3/3 miniapp h5 (5173) =="
if lsof -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[h5] already listening"
else
  cd "$ROOT/apps/miniapp"
  nohup npm run dev:h5 > /tmp/f31-h5.log 2>&1 &
  echo "[h5] started (log /tmp/f31-h5.log)"
fi
wait_http "$H5_URL" h5 30

echo "ALL READY"
