# F2.1 — 静态验证报告

> 日期：2026-09-27

## 1. py_compile

```bash
cd apps/api && .venv/bin/python -m py_compile \
  src/app/modules/admin/service.py \
  src/app/modules/admin/router.py \
  src/app/modules/user/service.py \
  src/app/modules/auth/repository.py \
  tests/integration/test_admin_user_real.py
# → 全部通过（COMPILE_OK，无输出错误）
```

## 2. Mock 残留检查

```bash
grep -rn "9999\|13800138000\|user_{i}\|5000\|10000" apps/api/src/app/modules/admin/
# → No matches found
```

`admin/service.py` 与 `admin/router.py` 中不存在任何硬编码假数据返回。

## 3. Diff 审查（改动面白名单）

```bash
git diff --stat apps/api/src/app/modules/admin/ \
  apps/api/src/app/modules/user/service.py \
  apps/api/src/app/modules/auth/repository.py
```

| 文件 | 变化 | 审查结论 |
|------|------|---------|
| `admin/service.py` | +320/-80 量级重写 | Mock 全部移除；仅调用 UserService / 聚合查询 / rbac cache；无 Repository/SQL 直连（统计为 Service 内既有模式的 count 查询） |
| `admin/router.py` | 91 行变更 | 仅 4 端点改调 Service + update_user 补 db/redis_client；装饰器/路径/方法/请求 schema 未动；无业务逻辑下沉违规 |
| `user/service.py` | +6/-2 | 仅 `delete_user` 增加 keyword-only `auto_commit=True` 并透传；向后兼容 |
| `auth/repository.py` | +15 | 仅新增 `get_role_by_id` 标准查询方法 |

注：工作区存在其他 Feature 的未提交变更（66 文件），本 Feature 实际触碰仅上述 4 个源文件 + 1 个新测试文件 + `docs/features/F2.1-admin-user-real/`。

## 4. 分层合规检查

| 规则 | 检查 | 结果 |
|------|------|------|
| Router 不写业务逻辑 | router 四处改动均为"提取参数 → 调 Service → success()" | ✅ |
| 跨模块复用只调 Service | admin → UserService（未触碰 UserRepository/AuthRepository 直查，统计除外且为既有模式） | ✅ |
| 租户隔离 | UserRepository 继承 TenantAwareRepository；`get_by_id`（被 update/delete 内部调用）带租户校验；create 自动注入 tenant_id；业务 tenant_id 取自 ContextVar 而非请求体 | ✅ |
| 事务 | 批量删除同一 AsyncSession 统一 commit；异常由 `get_session` rollback | ✅ |
| RBAC | 装饰器全部保留未动；assign-roles 双重校验（角色+权限）保留 | ✅ |
| 认证/机密 | 无硬编码密钥；日志不输出敏感信息 | ✅ |

## 5. 契约一致性

- OpenAPI 路径/方法/请求体未变更（`username`/`is_active`/`role_ids` 等 admin schema 字段原样保留）。
- 响应端点均为 `response_model=dict`，新增字段（`public_id`/`status` 等）属兼容变更；`username`/`is_active` 保留为别名。
- 前端 4 端影响评估：grep 确认仅 `/admin/dashboard` 被 admin-web 消费且未改动 → admin-web / student-web / teacher-web / miniapp 均**不涉及**；无需 `pnpm gen:types`。
