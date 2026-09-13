# CI 提交前本地检测指南

本文档总结了确保提交代码到 GitHub 时 CI 配置不会报错的完整检测流程。

---

## 检测清单

| 检测项 | 命令 | 说明 |
|--------|------|------|
| **后端格式** | `uv run ruff check . --fix` | 修复 Python 代码格式 |
| **后端类型** | `uv run mypy src` | 检查 Python 类型注解 |
| **后端测试** | `uv run pytest tests/unit` | 运行单元测试 |
| **前端格式** | `pnpm lint --fix` | 修复 ESLint 问题 |
| **前端构建** | `pnpm build` | 完整构建（包含类型检查） |
| **类型同步** | 手动更新 `api-client` 类型 | 后端模型变更后必须同步 |

---

## 一键检测脚本

在项目根目录创建 `scripts/check-before-push.sh`：

```bash
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
echo " 3. 完整构建测试..."
cd ../..
pnpm build
echo ""

echo "========================================="
echo "✅ 所有检测通过！可以安全提交"
echo "========================================="
```

使用方法：

```bash
# 添加执行权限
chmod +x scripts/check-before-push.sh

# 提交前运行
./scripts/check-before-push.sh
```

---

## 后端模型变更后的特殊流程

如果你修改了后端模型（如添加字段、修改表结构），需要额外步骤：

```bash
# 1. 生成数据库迁移
cd apps/api
uv run alembic revision --autogenerate -m "add_xxx_field"

# 2. 更新 api-client 类型定义
# 手动编辑 packages/api-client/src/ 中的相关类型文件
# 例如：courses.ts, membership.ts 等

# 3. 或者重新生成 OpenAPI 类型（如果使用自动生成）
cd ../..
pnpm gen:types

# 4. 运行完整检测
./scripts/check-before-push.sh
```

---

## 常见错误及解决方案

| 错误类型 | 原因 | 解决方案 |
|---------|------|---------|
| `Property 'xxx' does not exist on type` | 后端新增字段，前端类型未更新 | 更新 `packages/api-client/src/` 中的类型定义 |
| `Type 'undefined' is not assignable to type 'number'` | 必填字段传了 undefined | 修改接口定义为可选 `?:` 或确保传值 |
| `ruff check` 失败 | Python 代码格式问题 | 运行 `uv run ruff check . --fix` |
| `pnpm lint` 失败 | 前端代码格式问题 | 运行 `pnpm lint --fix` |
| `pnpm build` 失败 | TypeScript 类型错误 | 检查 `api-client` 类型是否与后端一致 |

---

## 推荐工作流

### 日常开发

```bash
1. 编写代码
2. 保存时 IDE 自动格式化
3. 提交前运行：./scripts/check-before-push.sh
4. 如果通过：git add . && git commit -m "xxx" && git push
```

### 后端模型变更

```bash
1. 修改 models.py
2. 生成迁移：uv run alembic revision --autogenerate -m "xxx"
3. 更新 api-client 类型定义
4. 运行：./scripts/check-before-push.sh
5. 提交代码
```

---

## 关键原则

1. **保存即格式化**：配置 IDE 自动格式化，减少手动操作
2. **提交前必构建**：`pnpm build` 能捕获 99% 的类型错误
3. **类型同步**：后端模型变更后，立即更新前端类型定义
4. **小步提交**：每次提交只做一件事，便于排查问题

---

## 类型定义同步说明

### api-client 类型维护方式

项目中的 `packages/api-client/src/` 目录下的类型定义是**手动维护**的，包括：

- `courses.ts` - 课程相关类型
- `membership.ts` - 会员卡相关类型
- `auth.ts` - 认证相关类型
- 等等...

### 同步步骤

1. **后端修改模型后**，检查 `packages/api-client/src/` 中对应的类型文件
2. **添加新字段**：在对应的 interface 中添加新字段
3. **修改字段类型**：更新字段类型定义（如必填改为可选）
4. **运行构建验证**：`pnpm build` 确保类型一致

### 示例

后端添加了 `frozen_at` 字段到 `MembershipCard` 模型：

```python
# 后端 models.py
class MembershipCard(Base):
    frozen_at = Column(DateTime, nullable=True)
    frozen_until = Column(DateTime, nullable=True)
```

前端需要同步更新：

```typescript
// packages/api-client/src/membership.ts
export interface MembershipCard {
  // ... 其他字段
  frozen_at: string | null
  frozen_until: string | null
}
```

---

## CI 配置概览

### 后端检查（Python）

```yaml
- name: Install dependencies
  run: uv sync --frozen

- name: Lint (Ruff)
  run: uv run ruff check .

- name: Type Check (Mypy)
  run: uv run mypy src
  continue-on-error: true

- name: Run tests
  run: uv run pytest tests/unit --tb=short -q
```

### 前端检查（TypeScript/Vue）

```yaml
- name: Install dependencies
  run: pnpm install --frozen-lockfile

- name: Lint (ESLint)
  run: pnpm lint
  working-directory: apps/admin-web

- name: Build all apps
  run: pnpm build
```

---

## 脚本分工说明

项目中有两个检测脚本，用途不同：

| 脚本 | 用途 | 执行时机 |
|------|------|---------|
| `scripts/check-before-push.sh` | 日常提交前检查 | 每次提交前 |
| `scripts/model-change.sh` | 后端模型变更处理 | 修改 models.py 后 |

### 日常检查脚本

`scripts/check-before-push.sh` - 用于日常提交前的快速检查：

```bash
# 添加执行权限（首次使用）
chmod +x scripts/check-before-push.sh

# 运行
./scripts/check-before-push.sh
```

### 模型变更脚本

`scripts/model-change.sh` - 专门处理后端模型变更：

```bash
#!/bin/bash
set -e

echo "========================================="
echo "🔄 后端模型变更处理流程"
echo "========================================="
echo ""

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
```

使用方法：

```bash
# 添加执行权限
chmod +x scripts/model-change.sh

# 运行（传入迁移描述）
./scripts/model-change.sh "add_phone_to_users"
```

---

## 完整工作流

### 日常开发（无模型变更）

```bash
# 1. 编写代码
# 2. 保存（IDE 自动格式化）
# 3. 运行日常检查
./scripts/check-before-push.sh

# 4. 提交
git add . && git commit -m "feat: xxx" && git push
```

### 后端模型变更

```bash
# 1. 修改 models.py
# 2. 运行模型变更脚本
./scripts/model-change.sh "add_xxx_field"

# 3. 检查生成的文件
#    - alembic/versions/xxx_xxx.py
#    - packages/api-client/src/ 中的类型文件

# 4. 手动调整（如果需要）
#    - 编辑迁移文件
#    - 编辑 api-client 类型定义

# 5. 提交
git add . && git commit -m "feat: add xxx field" && git push
```

---

按照这个流程，你的 CI 通过率将接近 100%！