#!/usr/bin/env bash
# 将模板中缺失的配置项合并进目标 env 文件（幂等，已有值一律保留）
#
# 用法：
#   bash infra/docker/sync-env.sh                                  # 默认 .env.example   -> .env
#   bash infra/docker/sync-env.sh .env.prod.example .env.prod      # 生产：模板 -> 生产配置
#
# 规则：
#   - 目标文件已存在的 key 不动（不覆盖真实值）
#   - 敏感/环境相关 key 缺失时只写空值，强制人工填写，避免写入占位值
#   - 其余 key 缺失时按模板默认值补入
set -euo pipefail

TEMPLATE="${1:-.env.example}"
TARGET="${2:-.env}"

if [ ! -f "$TEMPLATE" ]; then
  echo "❌ 模板不存在: $TEMPLATE" >&2
  exit 1
fi
if [ ! -f "$TARGET" ]; then
  echo "❌ 目标文件不存在: $TARGET（请先创建，例如 cp $TEMPLATE $TARGET）" >&2
  exit 1
fi

# 这些 key 不允许自动填入模板值：缺失时写空值，强制人工确认
SECRET_KEYS="JWT_SECRET POSTGRES_PASSWORD REDIS_PASSWORD DATABASE_URL REDIS_URL \
ARK_API_KEY WECHAT_APP_ID WECHAT_SECRET OSS_ACCESS_KEY_ID OSS_ACCESS_KEY_SECRET \
CORS_ORIGINS API_DOMAIN ADMIN_DOMAIN"

backup="${TARGET}.bak.$(date +%Y%m%d%H%M%S)"
cp "$TARGET" "$backup"
chmod 600 "$TARGET" 2>/dev/null || true

# 规范化：去掉 CRLF，并确保以换行结尾（否则追加内容会粘到上一行）
# 用临时文件改写，兼容 macOS/BSD 与 Linux/GNU 两种 sed
sed 's/\r$//' "$TARGET" > "${TARGET}.tmp" && mv "${TARGET}.tmp" "$TARGET"
if [ -n "$(tail -c 1 "$TARGET" 2>/dev/null)" ]; then
  printf '\n' >> "$TARGET"
fi

added=0
manual=""

while IFS='=' read -r key value; do
  [ -n "$key" ] || continue
  if grep -q "^${key}=" "$TARGET"; then
    continue
  fi

  case " $SECRET_KEYS " in
    *" $key "*)
      printf '%s=\n' "$key" >> "$TARGET"
      manual="${manual}  ${key}"$'\n'
      ;;
    *)
      printf '%s=%s\n' "$key" "$value" >> "$TARGET"
      echo "  + ${key}=${value}"
      ;;
  esac
  added=$((added + 1))
done < <(grep -E '^[A-Z][A-Z0-9_]*=' "$TEMPLATE")

echo "----------------------------------------"
echo "模板   : $TEMPLATE"
echo "目标   : $TARGET"
echo "新增   : ${added} 项"
echo "备份   : $backup"

if [ -n "$manual" ]; then
  echo "需人工填写（已置空）："
  printf '%s' "$manual"
fi
