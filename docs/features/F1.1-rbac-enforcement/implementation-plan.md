# F1.1 — RBAC 权限校验真实生效 · 实施方案

> Feature ID：F1.1
> 作者：project-architect（分析）/ backend-engineer（执行）
> 日期：2026-09-27
> 关联文档：[requirement.md](./requirement.md) / [acceptance.md](./acceptance.md)
> 协作协议：`docs/ai/workflows/multi-agent-collaboration-v3.md`

---

## Root Cause

### 缺口 1：bypass 硬编码使全部权限校验失效

`apps/api/src/app/core/rbac/checker.py` L37-39 存在模块级常量 `PERMISSION_CHECK_BYPASS = True`，4 个校验函数（`check_permission` L203、`check_permissions` L251、`check_role` L295、`check_roles` L360）入口均 `if PERMISSION_CHECK_BYPASS: return True` 短路。后果：只要通过认证（有合法 JWT），任何用户可调用任何端点，RBAC 体系形同虚设。

### 缺口 2：5 个 router 无任何授权装饰器 + 2 个模块写端点裸奔

- `common/router.py`：`upload_image` 无角色限制；`test_token` 端点**无认证即可生成指定用户 JWT**（严重认证绕过）。
- `ai/router.py`：`GET /ai/intents` 无认证，泄露内部意图配置。
- `tenant/router.py` `get_tenant_settings`、`teacher/router.py` `get_current_teacher`/`update_current_teacher`、`auth/router.py` `update_me`：仅认证无授权。
- `booking/router.py`：`create_booking`/`cancel_booking`/`cancel_booking_by_schedule` 未限制学员角色（教师也可预约）。
- `membership/router.py`：`activate_card`/`student_unfreeze_card` 未限制学员角色。

### 缺口 3：种子数据与装饰器引用不匹配

- 权限表缺 `admin:all`/`super:manage` 两个权限码（被 `admin/router.py` 装饰器引用）。
- admin 角色缺 7 个权限（`course:delete`/`user:delete`/`user:reset_password`/`classroom:delete`/`role:create`/`role:update`/`role:delete`），关闭 bypass 后 admin 调用这些端点会 403。
- `admin/router.py:473` `batch_delete_users` 引用不存在的 `security_admin` 角色且 `require_all=True` → 无人能通过。
- `admin/router.py:333` `GET /admin/settings` 函数签名缺 `db` 参数：bypass 开启时短路掩盖了该缺陷，关闭后装饰器 `kwargs.get("db")` 得 None → `db_session.execute()` 抛 AttributeError → 被 except 吞掉返回 False → admin 也 403。

## Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/core/rbac/checker.py` | 删硬编码常量，新增 `_is_permission_check_bypass()` 运行时读配置，4 处短路改调用 |
| 2 | `apps/api/src/app/core/config.py` | Settings 新增 `PERMISSION_CHECK_BYPASS: bool = False` |
| 3 | `apps/api/src/app/modules/common/router.py` | 删 3 个调试端点及孤儿 import；`upload_image` 加 `@require_roles(四角色)` + `db` 参数 |
| 4 | `apps/api/src/app/modules/admin/router.py` | `batch_delete_users` 改 `@require_roles("super_admin")`；`system_settings` 改 `@require_roles("admin","super_admin")` 并补 `db` 参数 |
| 5 | `apps/api/src/app/modules/auth/router.py` | `update_me` 加 `@require_roles(四角色)` |
| 6 | `apps/api/src/app/modules/booking/router.py` | 3 个写端点加 `@require_roles("student")` |
| 7 | `apps/api/src/app/modules/membership/router.py` | `activate_card`/`student_unfreeze_card` 加 `@require_roles("student")` |
| 8 | `apps/api/src/app/modules/teacher/router.py` | `get_current_teacher`/`update_current_teacher` 加 `@require_roles("teacher")` |
| 9 | `apps/api/src/app/modules/tenant/router.py` | `get_tenant_settings` 加 `@require_roles("admin","super_admin")` |
| 10 | `apps/api/src/app/modules/ai/router.py` | `get_supported_intents` 加 `Depends(get_current_user)` |
| 11 | `apps/api/src/app/ai/mcp_server.py` | `_require_auth` docstring 更新（注释级） |
| 12 | `apps/api/scripts/seed.py` | 权限表 +2（admin:all/super:manage），admin 角色 +7 权限 |
| 13 | `apps/api/tests/conftest.py` | 与 seed.py 同步 |
| 14 | `.env` / `.env.example` | 新增 `PERMISSION_CHECK_BYPASS=false` |
| 15 | `apps/api/tests/integration/test_rbac_enforcement.py` | **新建**，17 个用例 |

## Exact Fix（要点）

### checker.py

```python
# 删除：PERMISSION_CHECK_BYPASS = True（及注释）
# 新增：
def _is_permission_check_bypassed() -> bool:
    """是否跳过权限检查（每次调用时实时读取配置，便于测试动态覆盖）。
    生产环境必须保持 False（Settings 默认值）。"""
    return get_settings().PERMISSION_CHECK_BYPASS

# 4 处 if PERMISSION_CHECK_BYPASS: → if _is_permission_check_bypassed():
```

选择函数内实时读取而非模块级缓存的原因：`get_settings()` 有 `lru_cache`，开销可忽略；函数内读取便于测试通过 monkeypatch 环境变量动态覆盖。

### admin/router.py 两处

```python
# L333 system_settings：
#   @require_permissions("admin:all", "super:manage", require_all=False)
#   → @require_roles("admin", "super_admin")
#   签名补 db: AsyncSession = Depends(get_session)  ← 关键：否则关闭 bypass 后 403
# L473 batch_delete_users：
#   @require_roles("super_admin", "security_admin", require_all=True)
#   → @require_roles("super_admin")
```

### 其余端点装饰器

按 acceptance.md AC-4 表格逐一添加，均保证签名含 `db`（装饰器从 kwargs 取）。

## Why This Fix Is Sufficient

1. **不重构 RBAC 架构**：装饰器、checker、缓存、DB 模型均既有且被 8 个 router 生产使用；本 Feature 只是"接通"既有能力。
2. **装饰器容错链完整**：`cache.py:get_cached_permissions` 对 `redis_client=None` 有容错（L61-63）；checker 异常兜底返回 False（宁可 403 不可放行），方向安全。
3. **FastAPI 执行序保证**：Pydantic 422 先于装饰器执行，非法请求不会绕过授权到达业务层；401（认证）先于 403（授权）。
4. **种子补齐方向正确**：只加权限不删权限，admin 能力域扩大属恢复设计意图（装饰器本就引用这些权限码）。

## Dependency Analysis

- `get_settings`：`app/core/config.py`，`lru_cache` 单例，checker 调用无循环导入（config 不依赖 rbac）。
- 种子一致性：`scripts/seed.py` 与 `tests/conftest.py` 两处权限列表人工 diff 保持一致（长期看应收敛为单一数据源，登记为改进项）。
- 外部依赖：Redis（权限缓存 + token 黑名单），生产环境 lifespan 已强制可达。

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 遗漏端点未加装饰器 | 中 | 13 个 router 全量审计；集成测试覆盖代表端点 |
| 关闭 bypass 暴露签名缺 `db` 的隐藏端点 | 中 | 已发现 1 处（admin/settings）并修复；集成测试 admin 正向用例兜底 |
| 存量库权限缺失导致 admin 403 | 高 | release-note 提供手工 SQL；测试库由 conftest 全新种子保证 |
| 前端依赖 403 文案 | 低 | 统一异常信封不变，仅状态码语义变化（200→403 属修复目标） |

## Implementation Steps（实际执行顺序）

1. T1.1.1：seed.py + conftest.py 权限同步；admin/router.py 两处装饰器修复。
2. T1.1.2：common 删端点 + 5 个 router 补装饰器。
3. T1.1.3：config.py + checker.py + .env/.env.example + mcp_server.py 注释。
4. 每改完一个 Python 文件即 `py_compile`。
5. T1.1.4：编写 test_rbac_enforcement.py 并迭代至 17/17 通过（期间发现并修复 3 个 dev 库数据污染问题，见 implementation-report.md §5）。
6. 回归：test_auth_api（单独运行）、test_rbac_real_redis、test_agent_runtime。

## Verification Plan

| AC | 方式 |
|----|------|
| AC-1.x | grep + 读代码 |
| AC-2/3/4.6-4.11/5/6 | `pytest tests/integration/test_rbac_enforcement.py -v`（17 用例） |
| AC-4.1-4.5 装饰器存在性 | grep `@require_roles` |
| AC-7 | diff seed.py vs conftest.py 权限段 |
| AC-8 | 三个既有测试文件分别运行 |
| AC-9 | `git diff --stat` 与白名单比对（仅允许上述 15 个文件） |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 曾观察到 user_roles (2,3) 被回退为 (2,4) 一次，后续未复现；疑似 docker-api-1 容器（旧代码 + APScheduler，连同一 DB）干扰 | 测试前核对种子状态；CI 环境无此容器 |
| U2 | 前端是否有页面在运行时依赖了被删调试端点 | 已 grep 四端无引用；如有隐藏依赖会以 404 形式暴露，易发现 |
| U3 | 存量生产库的角色-权限实际分布未知 | 上线前按 release-note SQL 审计并补齐 |
