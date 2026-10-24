# F2.1 — admin 用户管理真实化 · 实施方案

> Feature ID：F2.1
> 作者：backend-engineer
> 日期：2026-09-27
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

`apps/api/src/app/modules/admin/service.py` 是 RBAC 演示时期编写的 Mock 实现（文件头自述"仅用于演示 RBAC 权限系统的使用方式，不包含真实的数据库操作"）。F1.1 接通 RBAC 后，admin 端点的权限校验已真实生效，但业务层仍返回伪造数据，导致"权限通过 + 数据造假"的不一致状态。真实业务能力早已存在于 `UserService`（被 `/api/v1/users` 生产使用），admin 模块未复用。

## 已核查的代码事实（Evidence）

| 事实 | 证据 |
|------|------|
| UserService 方法签名与内部事务 | [user/service.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/user/service.py)：`create_user` L56（内部 commit L150）、`update_user` L201（commit L304，传 role_ids 时内部调 assign_roles L308-311）、`delete_user` L369（经 `BaseRepository.delete(auto_commit=True)` 提交）、`get_user_by_id` L432、`list_users` L499、`assign_roles` L681（commit L820 + 清缓存 L826-827） |
| UserService 已处理缓存失效 | `assign_roles` L826-827、`delete_user` L425-426 均调 `clear_user_permission_cache`；admin 层不重复清（批量删除除外，见下） |
| User 模型无 `username` 字段 | [user/models.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/user/models.py) L23-47：仅 `nickname`/`real_name` |
| 前端无 `/admin/users*` 消费 | grep `apps/admin-web/src` 仅 `views/dashboard/index.vue:116` 消费 `/admin/dashboard`；`packages/api-types` 为生成物含旧定义但无运行时消费者 |
| 租户中间件不含 public/stats 白名单 | [tenant_middleware.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/middleware/tenant_middleware.py) L24-37：`/api/v1/admin/public/stats` 不在 SKIP 列表 → 请求必须携带租户头，ContextVar 必有 tenant_id |
| count 查询不触发 ORM 租户注入 | [tenant_query.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/core/tenant_query.py) L53-57：`select(func.count())` 的 `column_descriptions` entity 为 None → 自动注入跳过，必须显式 `.where(tenant_id == ...)`（与 admin/dashboard 现有写法一致） |
| 批量删除可统一事务 | [database.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/core/database.py) L16-22：`get_session` 异常时自动 rollback |
| admin/UserCreate 与 user/UserCreate 字段差异 | admin schemas 有 `username`/`is_active`；user schemas 有 `nickname`/`status` → 需在 admin Service 做映射 |

## Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/modules/admin/service.py` | 重写：全部 Mock 方法改为调用 `UserService`；新增 `get_user` / `assign_roles` / `batch_delete_users` / `get_public_stats`；`get_my_permissions` 原样保留 |
| 2 | `apps/api/src/app/modules/admin/router.py` | `get_user` 改调 Service（去内联 Mock）；`assign_user_roles` 改调 Service（去内联缓存清理）；`batch_delete_users` 改调 Service；`public_stats` 注入 db 并改调 Service |
| 3 | `apps/api/src/app/modules/user/service.py` | `delete_user` 增加 keyword-only 参数 `auto_commit: bool = True`，透传至 `user_repo.delete`（默认行为不变，向后兼容 `/users` 路由） |
| 4 | `apps/api/tests/integration/test_admin_user_real.py` | 新建，覆盖 AC-1 ~ AC-15 |

## Exact Fix（要点）

### 1. admin/service.py 重写

```python
class AdminUserService:
    def __init__(self):
        self.user_service = UserService()

    async def create_user(self, db, data: dict, current_user: dict) -> dict:
        # admin 契约 → user 契约映射：username → nickname
        payload = UserCreate(
            phone=data["phone"], password=data["password"],
            email=data.get("email"), nickname=data.get("username"),
            role_ids=data.get("role_ids") or [],
        )
        result = await self.user_service.create_user(db, payload, operator_id=current_user["user_id"])
        return self._to_admin_dict(result)   # UserResponse.model_dump() + username/is_active 兼容别名

    async def update_user(self, db, user_id, data: dict, current_user, redis_client=None) -> dict:
        payload = UserUpdate(
            phone=data.get("phone"), email=data.get("email"), nickname=data.get("username"),
            status=(1 if data["is_active"] else 0) if data.get("is_active") is not None else None,
            role_ids=data.get("role_ids"),
        )
        result = await self.user_service.update_user(
            db, user_id, payload, operator_id=current_user["user_id"], redis_client=redis_client)
        return self._to_admin_dict(result)

    async def delete_user(self, db, user_id, current_user, redis_client=None) -> dict:
        if user_id == current_user["user_id"]:
            raise BusinessException("不能删除自己的账号")   # 预检，保持原错误类型
        await self.user_service.delete_user(db, user_id, operator_id=current_user["user_id"], redis_client=redis_client)
        return {"message": f"用户 {user_id} 已删除"}

    async def list_users(self, db, page=1, page_size=20, keyword=None) -> dict:
        result = await self.user_service.list_users(db, keyword=keyword, page=page, page_size=page_size)
        return {"total": result.total, "page": result.page, "page_size": result.page_size,
                "items": [self._to_admin_dict(u) for u in result.items]}

    async def get_user(self, db, user_id) -> dict:        # 新增
        return self._to_admin_dict(await self.user_service.get_user_by_id(db, user_id))

    async def assign_roles(self, db, user_id, role_ids, current_user, redis_client=None) -> dict:  # 新增
        await self.user_service.assign_roles(db, user_id, role_ids,
            operator_id=current_user["user_id"], redis_client=redis_client)  # 内部已 commit + 清缓存
        return {"user_id": user_id, "role_ids": role_ids}

    async def batch_delete_users(self, db, user_ids, current_user, redis_client=None) -> dict:     # 新增
        operator_id = current_user["user_id"]
        if operator_id in user_ids:
            raise BusinessException("不能删除自己的账号")
        for uid in user_ids:   # 同一 AsyncSession，逐条校验+软删但不提交
            await self.user_service.delete_user(db, uid, operator_id=operator_id, auto_commit=False)
        await db.commit()      # 统一提交（原子）；任一异常由 get_session rollback
        if redis_client:       # 提交后统一清缓存
            for uid in user_ids:
                await clear_user_permission_cache(redis_client, current_user.get("tenant_id"), uid)
        return {"deleted_count": len(user_ids), "user_ids": user_ids}
```

`_to_admin_dict(UserResponse)`：`model_dump()` 后追加 `username = nickname or phone`、`is_active = (status == 1)`（AC-15 兼容别名）。

### 2. admin/router.py 四处

- `get_user`：删内联假 dict，改 `await admin_user_service.get_user(db, user_id)`。
- `assign_user_roles`：删内联日志/缓存清理，改 `await admin_user_service.assign_roles(db, user_id, role_ids, current_user, redis_client)`；响应体保持 `{"user_id", "role_ids"}`。
- `batch_delete_users`：删内联循环清缓存，改 `await admin_user_service.batch_delete_users(...)`；响应体保持 `{"deleted_count", "user_ids"}`。
- `public_stats`：签名补 `db: AsyncSession = Depends(get_session)`，改调 `admin_user_service.get_public_stats(db)`。

装饰器、路径、方法、请求体 schema 一律不动。

### 3. user/service.py 一处

```python
async def delete_user(self, db, user_id, operator_id, redis_client=None, *, auto_commit: bool = True) -> bool:
    ...
    success = await self.user_repo.delete(db, user_id, auto_commit=auto_commit)
```

### 4. get_public_stats（admin/service.py）

按当前租户显式过滤（count 查询不触发 ORM 自动注入，见事实表）：

- `total_students` / `total_teachers`：`count(distinct User.id)` join `UserRole`/`Role`（`Role.code == 'student'/'teacher'`、`User.deleted_at.is_(None)`、`User.tenant_id == tid`；Role join 条件 `or_(Role.tenant_id == tid, Role.tenant_id.is_(None))` 以兼容全局角色）。
- `total_classes`：`count(Course)` where `deleted_at is None` + 租户。
- `total_bookings`：`count(Booking)` + 租户（Booking 无 deleted_at 字段，不过滤）。

## 关键决策记录（Decision）

| # | 决策 | 理由 |
|---|------|------|
| D1 | admin Service 保持现有方法签名（`data: dict`），内部做 admin schema → user schema 映射 | router 零改动或少改动；admin `UserCreate.username` 保留在 OpenAPI 契约中（`username → nickname`） |
| D2 | 响应保留 `username`/`is_active` 兼容别名 | 前端虽无消费，但 `response_model=dict` 无约束，保留别名可避免任何潜在外部消费者破窗；真实字段（`status`/`nickname`/`public_id` 等）同时返回 |
| D3 | 批量删除采用原子语义（统一 commit，任一失败全回滚） | 满足"同一 AsyncSession 由 Service 统一提交"规则；super_admin 高危操作宁可全失败不留半成品 |
| D4 | `UserService.delete_user` 加 `auto_commit` 参数而非在 admin 层重写删除逻辑 | 遵守"跨模块复用只能调 Service"、"禁止重复实现已有业务逻辑"；默认 True 不影响 `/users` 路由 |
| D5 | public/stats 按**当前租户**聚合（非跨租户） | 中间件强制租户头（不在白名单），ContextVar 必有租户；"学校简介中的数字"语义上就是单个学校的数据；不扩大租户跳过白名单（安全规则） |
| D6 | 统计聚合查询写在 admin Service 内（不新建 Repository） | 与 `UserService` 内直写 `db.execute(select(...))` 的既有模式一致（L162-164 等）；纯 count 无业务规则 |
| D7 | `assign_roles` 不在 admin 层重复清缓存 | `UserService.assign_roles` L826-827 已清；重复清理无意义 |
| D8 | admin `create_user`/`update_user` 返回 UserResponse 全字段（含 phone） | admin 端点本身要求 user:* 权限，操作者为管理员，非 PII 泄露面；与 `/users` 路由行为一致 |

## Dependency Analysis

- 复用：`UserService`（user 模块）→ `UserRepository`（TenantAwareRepository）/ `AuthRepository` → 租户注入与软删除自动生效。
- `clear_user_permission_cache`：`app.core.rbac.cache`，对 `redis_client=None` 有容错。
- 无新外部依赖；无 DB 结构变更；无 Redis key 结构变更。
- 契约：OpenAPI 路径/方法/请求体不变；响应 `response_model=dict` 不变 → 无需 `pnpm gen:types`，前端 4 端确认无影响（已 grep）。

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| `/users` 路由受 `delete_user` 签名变更影响 | 低 | 新参数 keyword-only 且默认 True，行为等价；回归 test_user_api |
| admin 契约 `username` 语义变化（原 Mock 回显，现映射 nickname） | 低 | 无前端消费；响应保留 `username` 别名 |
| 批量删除原子语义与旧 Mock"总是成功"不同（含不存在 id 会整体失败） | 低 | 高危接口 fail-fast 更安全；release-note 说明 |
| `assign_roles` 中 UserService 对操作人角色的二次校验（须 admin/super_admin）使 manager 角色实际被拒 | 低 | 纵深防御方向正确；文档化（user-flow 流程 6） |
| 测试污染种子数据 | 中 | 测试内创建的用户全部在测试内删除；唯一手机号用时间戳生成 |

## Implementation Steps

1. 改 `user/service.py`（delete_user auto_commit）→ py_compile。
2. 重写 `admin/service.py` → py_compile。
3. 改 `admin/router.py` 四处 → py_compile。
4. 静态审查 diff（仅允许上表 4 个文件）。
5. 编写 `test_admin_user_real.py`，迭代至全绿。
6. 回归：`test_auth_api.py`、`test_rbac_enforcement.py`、`test_user_api.py`。

## Verification Plan

| AC | 方式 |
|----|------|
| AC-1~12, 15, 17 | `pytest tests/integration/test_admin_user_real.py -v` |
| AC-13/14 | 回归 `test_rbac_enforcement.py` / `test_auth_api.py` / `test_user_api.py` |
| AC-16 | grep Mock 残留（`9999`、`user_{i}`、`5000`） |
| 改动面 | `git diff --stat` 与白名单比对 |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | `packages/api-types/openapi.json` 中 admin 端点定义为旧 Mock 时期的生成物，重新生成会影响该文件（生成物 diff 不含本次语义变化，因为 response_model=dict） | 本 Feature 不执行 gen:types（契约未变）；如下一次任意契约变更触发 gen:types，admin 部分 diff 需复核 |
| U2 | 是否存在仓库外的脚本/工具消费 `/admin/users*` Mock 字段（如 `9999` id） | 无法穷举；保留 `username`/`is_active` 别名后风险收敛到 `id=9999` 这类硬编码依赖，概率极低 |
| U3 | 测试环境 DB 中可能残留历史脏数据（如 docker-api-1 容器干扰，F1.1 U1 曾观察） | 测试断言以"本测试创建的数据"为准，不断言绝对总数 |
