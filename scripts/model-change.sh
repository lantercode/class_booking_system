#!/bin/bash
set -e

echo "========================================="
echo "🔄 后端模型变更处理流程"
echo "========================================="
echo ""

# 检查是否传入了迁移描述
if [ -z "$1" ]; then
    echo "❌ 错误：请提供迁移描述"
    echo "用法：./scripts/model-change.sh \"add_phone_to_users\""
    exit 1
fi

# 1. 生成数据库迁移
echo " 1. 生成数据库迁移..."
cd apps/api
uv run alembic revision --autogenerate -m "$1"
echo "   ✅ 迁移文件已生成"
echo ""

# 2. 更新 OpenAPI 类型
echo " 2. 更新 API 类型定义..."
cd ../..
pnpm gen:types
echo "   ✅ 类型定义已更新"
echo ""

# 3. 运行完整检测
echo " 3. 运行完整检测..."
./scripts/check-before-push.sh
echo ""

echo "========================================="
echo "✅ 模型变更处理完成！"
echo "========================================="
echo ""
echo "📝 下一步："
echo "   1. 检查生成的迁移文件是否正确"
echo "   2. 检查 packages/api-client/src/ 中的类型是否需要手动调整"
echo "   3. git add . && git commit -m 'feat: xxx'"
echo "   4. git push"