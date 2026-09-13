#!/bin/bash
set -e

echo "========================================="
echo "🚀 提交前完整检测"
echo "========================================="
echo ""

# 1. 后端检查
echo " 1. 后端代码检查..."
cd apps/api
uv run ruff check . --fix
uv run ruff format .
echo "   ✅ 后端格式检查完成"
echo ""

# 2. 前端检查
echo "🎨 2. 前端代码检查..."
cd ../..
cd apps/admin-web
pnpm lint --fix
pnpm format
echo "   ✅ 前端格式检查完成"
echo ""

# 3. 完整构建（包含类型检查）
echo "🔨 3. 完整构建测试..."
cd ../..
pnpm build
echo ""

echo "========================================="
echo "✅ 所有检测通过！可以安全提交"
echo "========================================="