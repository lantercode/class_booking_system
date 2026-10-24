# F2.1 — admin 用户管理真实化 · 实施报告

> 日期：2026-09-27 ｜ 执行：backend-engineer
> 关联：[implementation-plan.md](./implementation-plan.md)

## 1. 实施摘要

按方案完成 admin 模块用户管理真实化，全部写/读操作经由 `UserService` 落库，无 Mock 残留。

## 2. 变更明细

### 2.1 `apps/api/src/app/modules/admin/service.py`（重写，255 → 370 行）

| 方法 | 实现 |
|------|------|
| `create_user` | admin 契约映射（`username→nickname`）→ `UserService.create_user` → `_to_admin_dict`（追加 `username`/`is_active` 兼容别名） |
| `update_user` | 映射（`username→nickname`、`is_active→status`）→ `UserService.update_user`，透传 `redis_client` 以支持角色变更缓存失效 |
| `delete_user` | 预检"不能删除自己"（`ValidationException` 400）→ `UserService.delete_user`（软删 + 清缓存） |
| `list_users` | → `UserService.list_users`（租户隔离 + 软删过滤 + 关键词搜索），items 追加兼容别名 |
| `get_user`（新增） | → `UserService.get_user_by_id` |
| `assign_roles`（新增） | → `UserService.assign_roles`（内部已 commit + 清缓存，不重复清） |
| `batch_delete_users`（新增） | 预检不含操作者；循环 `UserService.delete_user(auto_commit=False)` 共享同一 `AsyncSession`；统一 `db.commit()`；提交后统一清权限缓存。原子语义：任一失败整体回滚 |
| `get_public_stats`（新增） | 按当前租户真实聚合：`total_students`/`total_teachers`（count distinct User join UserRole/Role，Role.tenant_id 兼容全局角色 NULL）、`total_classes`（Course 未删除）、`total_bookings`（Booking 无 deleted_at 不过滤）；无租户上下文时降级全平台并告警 |
| `get_my_permissions` | 原样保留（原本已是真实实现） |

### 2.2 `apps/api/src/app/modules/admin/router.py`（4 处端点 + 1 处修复）

- `get_user`：删除内联 Mock dict，改调 `admin_user_service.get_user`。
- `update_user`：**顺带修复历史 bug** —— 旧代码调用 `admin_user_service.update_user(user_id, ...)` 缺少 `db` 实参（Mock 时期未暴露）；补传 `db`，并注入 `redis_client` 以支持 AC-17 缓存失效。
- `assign_user_roles`：删除内联日志 + 只清缓存的假实现，改调 Service。
- `public_stats`：签名补 `db: AsyncSession = Depends(get_session)`，改调 Service（去除硬编码 5000/200/1000/10000）。
- `batch_delete_users`：删除内联循环清缓存的假实现，改调 Service。

装饰器（`@require_permissions` / `@require_roles`）、路径、方法、请求体 schema 均未动。

### 2.3 `apps/api/src/app/modules/user/service.py`（1 处）

- `delete_user` 增加 keyword-only 参数 `auto_commit: bool = True`，透传至 `user_repo.delete`。默认行为不变，`/users` 路由调用方零影响。

### 2.4 `apps/api/src/app/modules/auth/repository.py`（1 处，计划外但必需）

- 新增 `AuthRepository.get_role_by_id`。**原因**：`UserService.assign_roles` L737 调用了该方法但 AuthRepository 从未实现（`assign_roles` 为本次首次被真实触达的休眠路径），运行时报 `AttributeError`。补充标准按 ID 查询实现。

### 2.5 `apps/api/tests/integration/test_admin_user_real.py`（新建，323 行）

12 个用例覆盖 AC-1 ~ AC-12、AC-15、AC-17（详见 runtime-test-report.md）。

## 3. 实施中发现的问题

| # | 问题 | 处置 |
|---|------|------|
| 1 | `AuthRepository.get_role_by_id` 缺失（assign_roles 休眠 bug） | 补实现（见 2.4） |
| 2 | admin router `update_user` 旧调用缺 `db` 实参 | 顺带修复（见 2.2） |
| 3 | Mock 时期 `BusinessException("不能删除自己")` 默认 code=500 | 改用 `ValidationException`（400），语义正确且与 UserService 一致 |
| 4 | 测试环境 redis-py 版本无 `aclose()` | 测试代码改用 `close()` |
| 5 | `select(func.count())` 不触发 ORM 租户自动注入（entity=None） | public/stats 显式 `.where(tenant_id==...)`，与 admin/dashboard 现有写法一致 |

## 4. 与计划的偏差

- 计划未包含 `auth/repository.py` 变更 → 实施中由测试驱动发现，属"接通休眠路径"的必要修复，已记录。
- 其余严格按 implementation-plan.md 执行。

## 5. 数据兼容与迁移

- 无 DB 结构变更，无迁移。
- Mock 时期"创建"的用户从未落库，无脏数据需要清理。
