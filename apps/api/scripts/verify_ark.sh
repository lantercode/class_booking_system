#!/usr/bin/env bash
# 火山方舟（Ark）接入验证：网络连通性 / 模型可用 / Function Calling
#
# 用法：
#   export ARK_API_KEY="你的key"
#   ./scripts/verify_ark.sh
#
# 可选环境变量：
#   AI_LLM_BASE_URL  默认 https://ark.cn-beijing.volces.com/api/v3
#   AI_LLM_MODEL     默认 doubao-seed-2-1-lite-260915
#   PYTHON           默认 python3
#
# 说明：脚本只做只读调用，不写入任何文件；不会打印 API Key。
set -uo pipefail

BASE_URL="${AI_LLM_BASE_URL:-https://ark.cn-beijing.volces.com/api/v3}"
MODEL="${AI_LLM_MODEL:-doubao-seed-2-1-lite-260915}"
CHAT_URL="${BASE_URL%/}/chat/completions"
HOST="$(printf '%s' "$BASE_URL" | sed -E 's#^https?://([^/]+).*#\1#')"
PY="${PYTHON:-python3}"

PASS=0
FAIL=0
BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT

divider() { printf '%s\n' "------------------------------------------------------------"; }
ok() { printf '  [PASS] %s\n' "$1"; PASS=$((PASS + 1)); }
bad() { printf '  [FAIL] %s\n' "$1"; FAIL=$((FAIL + 1)); }

if [[ -z "${ARK_API_KEY:-}" ]]; then
  printf '缺少 ARK_API_KEY。请先执行： export ARK_API_KEY="你的key"\n' >&2
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  printf '未找到 curl，请先安装或改用其他方式验证\n' >&2
  exit 2
fi

printf '\n火山方舟接入验证\n'
printf '  base_url : %s\n' "$BASE_URL"
printf '  model    : %s\n' "$MODEL"
divider

# ---------------------------------------------------------------- ① 连通性
printf '\n① 网络连通性（%s:443）\n' "$HOST"
HTTP_CODE="$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "https://${HOST}/" 2>/dev/null)"
if [[ -z "$HTTP_CODE" || "$HTTP_CODE" == "000" ]]; then
  bad "无法建立 HTTPS 连接（DNS 解析失败 / 出网被拦 / 代理未配置）"
else
  ok "TCP + TLS 可达（根路径返回 HTTP ${HTTP_CODE}）"
fi

# ---------------------------------------------------------------- ② 模型可用
printf '\n② 模型可用性（chat/completions）\n'
PAYLOAD="{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}],\"max_tokens\":32,\"thinking\":{\"type\":\"disabled\"}}"
STATUS="$(curl -sS --max-time 45 -o "$BODY_FILE" -w '%{http_code}' "$CHAT_URL" \
  -H "Authorization: Bearer ${ARK_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" 2>/dev/null)" || STATUS="000"

MODEL_RESULT="$("$PY" -c '
import json, sys
path = sys.argv[1]
try:
    raw = open(path, encoding="utf-8").read()
except OSError:
    print("NO_BODY||")
    raise SystemExit
if not raw.strip():
    print("EMPTY_BODY||")
    raise SystemExit
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("INVALID_JSON||" + raw[:120].replace("\n", " "))
    raise SystemExit
err = data.get("error")
if isinstance(err, dict):
    print("ERROR|{}|{}".format(err.get("code", ""), str(err.get("message", ""))[:200]))
else:
    choices = data.get("choices") or [{}]
    content = (choices[0].get("message") or {}).get("content") or ""
    usage = data.get("usage") or {}
    print("OK|{}|total_tokens={}".format(content[:40].replace("\n", " "), usage.get("total_tokens", "-")))
' "$BODY_FILE")"

KIND="$(printf '%s' "$MODEL_RESULT" | cut -d'|' -f1)"
FIELD2="$(printf '%s' "$MODEL_RESULT" | cut -d'|' -f2)"
FIELD3="$(printf '%s' "$MODEL_RESULT" | cut -d'|' -f3)"

case "$KIND" in
  OK)
    ok "模型返回正常（${FIELD2} ${FIELD3}）"
    ;;
  ERROR)
    case "$FIELD2" in
      ModelNotOpen*)
        bad "模型未开通（${FIELD2}）：请到方舟控制台「开通管理」开通 ${MODEL}"
        ;;
      AuthenticationError*)
        bad "鉴权失败（${FIELD2}）：Key 错误 / 缺少 Bearer / 环境变量未生效"
        ;;
      *)
        bad "方舟返回错误（${FIELD2}）：${FIELD3}"
        ;;
    esac
    ;;
  *)
    bad "响应异常（HTTP ${STATUS}，${KIND}）${FIELD2:+：${FIELD2}}"
    ;;
esac

# ---------------------------------------------------------------- ③ Function Calling
printf '\n③ Function Calling（tools → tool_calls）\n'
TOOL_PAYLOAD="{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"帮我查一下明天有哪些舞蹈课\"}],\"max_tokens\":128,\"thinking\":{\"type\":\"disabled\"},\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"query_schedules\",\"description\":\"查询课程排期\",\"parameters\":{\"type\":\"object\",\"properties\":{\"date\":{\"type\":\"string\",\"description\":\"日期，格式 YYYY-MM-DD\"}},\"additionalProperties\":false}}}]}"
TOOL_STATUS="$(curl -sS --max-time 45 -o "$BODY_FILE" -w '%{http_code}' "$CHAT_URL" \
  -H "Authorization: Bearer ${ARK_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$TOOL_PAYLOAD" 2>/dev/null)" || TOOL_STATUS="000"

TOOL_RESULT="$("$PY" -c '
import json, sys
path = sys.argv[1]
try:
    data = json.load(open(path, encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    print("INVALID||")
    raise SystemExit
err = data.get("error")
if isinstance(err, dict):
    print("ERROR|{}|{}".format(err.get("code", ""), str(err.get("message", ""))[:200]))
    raise SystemExit
choices = data.get("choices") or [{}]
message = choices[0].get("message") or {}
calls = message.get("tool_calls") or []
if not calls:
    print("NO_TOOL_CALL||" + str(message.get("content") or "")[:80].replace("\n", " "))
    raise SystemExit
first = calls[0]
func = first.get("function") or {}
print("OK|{}|{}|count={}".format(func.get("name", ""), str(func.get("arguments", ""))[:120], len(calls)))
' "$BODY_FILE")"

TOOL_KIND="$(printf '%s' "$TOOL_RESULT" | cut -d'|' -f1)"
TOOL_NAME="$(printf '%s' "$TOOL_RESULT" | cut -d'|' -f2)"
TOOL_ARGS="$(printf '%s' "$TOOL_RESULT" | cut -d'|' -f3)"
TOOL_COUNT="$(printf '%s' "$TOOL_RESULT" | cut -d'|' -f4)"

case "$TOOL_KIND" in
  OK)
    if [[ "$TOOL_NAME" == "query_schedules" ]]; then
      ok "模型正确发起工具调用：${TOOL_NAME} ${TOOL_ARGS} ${TOOL_COUNT}"
    else
      bad "模型调用了非预期工具：${TOOL_NAME}"
    fi
    ;;
  NO_TOOL_CALL)
    bad "模型未发起工具调用（可能只是文字回复）：${TOOL_NAME}${TOOL_ARGS}"
    ;;
  ERROR)
    bad "方舟返回错误（${TOOL_NAME}）：${TOOL_ARGS}"
    ;;
  *)
    bad "响应异常（HTTP ${TOOL_STATUS}）"
    ;;
esac

# ---------------------------------------------------------------- 汇总
divider
printf '\n结果：PASS=%d  FAIL=%d\n' "$PASS" "$FAIL"
printf '\n常见错误对照：\n'
printf '  401 AuthenticationError  → Key 错误 / 未 export / 缺少 Bearer 前缀\n'
printf '  404 ModelNotOpen        → 模型未开通，或 Key 与模型不在同一项目\n'
printf '  404 NotFound            → Model ID 拼写错误\n'
printf '  429                     → 触发限流，稍后重试\n'
printf '  curl 超时 / 000         → 出网未放行 %s:443\n' "$HOST"
divider

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
printf '\n全部通过，可以进入下一步 TTFT 基准测试。\n'
