# F2.2 — 静态验证报告

> 日期：2026-09-28

## 1. py_compile

```bash
cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
  src/app/core/rbac/checker.py \
  src/app/core/rbac/__init__.py \
  src/app/modules/booking/repository.py \
  src/app/modules/booking/service.py \
  src/app/modules/booking/router.py \
  src/app/ai/mcp_server.py \
  tests/integration/test_booking_ownership.py
# → COMPILE_OK_ALL（全部通过，无输出错误）
```

## 2. Mock / 硬编码 残留检查

本 Feature 不涉及清除 Mock（与 F2.1 不同）。本次重点核查：

- `get_user_role_codes` 不返回硬编码集合，而是真实 DB 查询。
- `list_bookings` / `get_booking_by_id` 不存在绕过分流/归属校验的"放行旁路"。

```bash
grep -n "is_admin\s*=\s*True\|return set()" apps/api/src/app/core/rbac/checker.py
# → 仅异常/缺身份分支返回 set()（正确，最小权限默认）
```

## 3. Diff 审查（改动面白名单）

```bash
git diff --stat -- apps/api/src/app/core/rbac/ \
  apps/api/src/app/ai/mcp_server.py \
  apps/api/src/app/modules/booking/
```

| 文件 | 变化 | 审查结论 |
|------|------|---------|
| `core/rbac/__init__.py` | +2 | 仅导出新增函数，无逻辑变更 |
| `core/rbac/checker.py` | +75 量级 | 新增 `get_user_role_codes`，复用 `check_roles` SQL 模式；非授权决策（仍返回集合给 Service 分流）；异常时返回空集合（最小权限默认） |
| `modules/booking/repository.py` | +50 量级 | `search` 加 `teacher_id` 参数；统一 `needs_schedule_join` 判定避免重复 JOIN；既有过滤逻辑不动 |
| `modules/booking/service.py` | +161 量级 | `list_bookings` / `get_booking_by_id` 加 `current_user` keyword-only 参数并按角色分流；`_get_schedule_info_map` 返回值补 `teacher_id`；`_to_response` 不消费该字段 → 零响应泄露 |
| `modules/booking/router.py` | +19 量级 | 删除 `list_bookings` 内 `student_id` 推导；`list_bookings` / `get_booking` 透传 `current_user`；装饰器/路径/方法/查询参数/请求体未动；无业务判断下沉违规 |
| `ai/mcp_server.py` | 含其他 Feature 改动 | 本 Feature 仅改 `get_my_bookings` 一处：`student_id=user_id` → `current_user={"user_id","tenant_id"}`；身份来自 AgentRuntime 受信上下文 |

注：工作区存在其他 Feature 的未提交变更（`git diff --stat apps/api/src` 显示 32 文件），本 Feature 实际触碰仅上述 6 个源文件 + 1 个新测试文件 + `docs/features/F2.2-booking-ownership/`。

## 4. 越权残留 grep（router 层）

```bash
grep -n "student_id\s*=\s*current_user" apps/api/src/app/modules/booking/router.py
# 36:    student_id = current_user.get("user_id")      # create_booking (写操作, @require_roles("student"))
# 150:   student_id = current_user.get("user_id")      # cancel_booking (写操作, @require_roles("student"))
# 174:   student_id = current_user.get("user_id")      # cancel_booking_by_schedule (写操作, @require_roles("student"))
```

| 行 | 端点 | 是否在 F2.2 Scope | 结论 |
|----|------|------|------|
| L36 | `POST /bookings` (`create_booking`) | 否（写操作） | `@require_roles("student")` 已限定只有学员能调；`student_id` 是写操作的 actor 自身身份，非越权过滤。不在 F2.2 Scope（F2.2 仅 `GET /bookings` + `GET /bookings/{id}`） |
| L150 | `POST /bookings/{id}/cancel` (`cancel_booking`) | 否（写操作） | 同上；Service `cancel_booking` 内部已对 `student_id` 做归属校验（只允许取消自己的预约） |
| L174 | `POST /bookings/cancel` (`cancel_booking_by_schedule`) | 否（写操作） | 同上 |

`list_bookings`（L51 起）与 `get_booking`（L124 起）**无** `student_id = current_user` 残留——已完全下沉到 Service 层。

## 5. 分层合规检查

| 规则 | 检查 | 结果 |
|------|------|------|
| Router 不写业务判断 | `list_bookings` / `get_booking` 仅"提取参数 → 调 Service → success()"；删除了原 `student_id` 推导 if/else | ✅ |
| Service 承载业务规则 | 角色分流 / owner OR teacher-of-schedule OR admin 放行 / 最小权限默认 均在 `booking/service.py` | ✅ |
| Repository 仅数据访问 | `booking/repository.py` `search` 加 `teacher_id` 过滤，无业务决策 | ✅ |
| 跨模块复用只调 Service | MCP `get_my_bookings` → `BookingService.list_bookings`（不直查 Repository） | ✅ |
| 租户隔离 | `BookingRepository` 继承 `TenantAwareRepository`；`get_by_id` 跨租户返回 None → 404（不泄露存在性）；`get_user_role_codes` 用 `or_(Role.tenant_id == tid, Role.tenant_id.is_(None))` 兼容全局角色 | ✅ |
| RBAC | 装饰器 `@require_permissions("booking:list")` / `@require_permissions("booking:read")` 原样保留；`get_user_role_codes` 非授权决策（不替代 `check_permissions`） | ✅ |
| 认证/机密 | `current_user` 由 `Depends(get_current_user)` 注入；MCP 身份来自 AgentRuntime 受信上下文，不接受 LLM/前端传入 | ✅ |
| AI 边界 | `get_my_bookings` Tool 只调 Service，不直查 Repository / 裸 SQL / 直连 Redis | ✅ |

## 6. 契约一致性

- OpenAPI 路径 / 方法 / 查询参数 / 请求体 / 响应模型全部不变。
- `current_user` 是 `Depends` 注入，不出现在 OpenAPI schema → 无需 `pnpm gen:types`。
- 响应字段集合不变（`_to_response` 不消费新增的 `teacher_id`）。
- 前端 4 端影响评估：`GET /bookings` / `GET /bookings/{id}` 被 admin-web / student-web / teacher-web / miniapp 消费，但**接口契约不变**，仅是后端按角色强制归属过滤——学员端原本就只能看自己（行为一致），教师端从"空"改为"见自己排期预约"（符合 T2.2.3 预期），admin 端全量不变。4 端均**无代码改动**。
