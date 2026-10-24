# 产品交付差距分析（Product Gap Analysis）

> 审计日期：2026-09-24
> 所有问题基于真实代码验证，每条附带证据（文件路径+行号）
> 分级：P0 阻塞上线 / P1 影响核心业务 / P2 体验与可维护性 / P3 后续优化

---

## P0 — 阻塞上线（安全 / 数据正确性 / 核心流程不可用）

| # | 问题 | 域 | 证据 |
|---|------|----|------|
| P0-1 | RBAC 权限校验全局 bypass，所有接口无权限控制 | 安全 | `core/rbac/checker.py:39` `PERMISSION_CHECK_BYPASS = True` |
| P0-2 | `/common/test-token` 可伪造任意身份 Token（user_id=1, tenant_id=10），无需认证 | 安全 | `modules/common/router.py:89-104` |
| P0-3 | 未注册通用 Exception 处理器，`debug=True` 时未捕获异常泄露完整 traceback | 安全 | `main.py:163-164`, `config.py:35` |
| P0-4 | admin 模块用户管理全部是 Mock（create/update/delete/list 返回假数据，不操作 DB） | 后端 | `modules/admin/service.py:55-212` TODO |
| P0-5 | JWT access_token 黑名单未校验，登出后 2h 内仍可访问所有接口 | 安全 | `deps/auth.py:11-31` |
| P0-6 | 生产环境 Redis 无密码认证 | 安全 | `infra/docker/docker-compose.prod.yml:18-28` |
| P0-7 | APScheduler 定时任务无租户隔离（ContextVar 为空，tenant_query 注入失败） | 多租户 | `schedule/scheduler.py:37`, `membership/scheduler.py` |
| P0-8 | miniapp 教师排期页加载即崩溃（`extractList` 未导入） | 前端 | `apps/miniapp/src/pages/teacher/schedule/index.vue:190` |
| P0-9 | miniapp 教师学员页加载即崩溃（`extractList` 未导入） | 前端 | `apps/miniapp/src/pages/teacher/students/index.vue:134,153` |
| P0-10 | miniapp 学员排期页加载即崩溃（`tenantApi` 未导入） | 前端 | `apps/miniapp/src/pages/student/schedule/index.vue:570` |
| P0-11 | AI 多轮预约流程断裂：`_parse_schedules` 解析格式与 `query_schedules` 输出不匹配，永远返回空 | AI | `ai/agent/runtime.py:482` vs `ai/mcp_server.py:161` |

---

## P1 — 影响核心业务 / 明显影响交付

### 后端 / 业务

| # | 问题 | 证据 |
|---|------|------|
| P1-1 | AI 接口异常处理访问不存在的 `e.status_code`/`e.message`（实际是 `code`/`msg`），业务错误被吞为 500 | `modules/ai/router.py:87` |
| P1-2 | `cancel_schedule` 中会员卡回补失败时不回滚，booking 已 CANCELLED 但课时未恢复 | `modules/schedule/service.py:272-300` |
| P1-3 | `check_in_booking` / `complete_booking` 无行锁，并发状态竞态 | `modules/booking/service.py:282,306` |
| P1-4 | `delete_schedule` Router 层直接操作 Repository，绕过 Service | `modules/schedule/router.py:211-230` |
| P1-5 | `GET /bookings` 传 schedule_id 时 student_id=None，任意用户可查看该排期所有学员预约 | `modules/booking/router.py:66` |
| P1-6 | `GET /bookings/{id}` 无归属校验，任意登录用户可查看任意预约详情 | `modules/booking/service.py:321-331` |
| P1-7 | `admin/users/{id}/assign-roles` 和 `batch-delete` 仅清缓存，不真正执行 | `modules/admin/router.py:370-392,474-501` |
| P1-8 | `membership/service.py` 混用 `HTTPException`，响应格式不统一且可能泄露内部信息 | `modules/membership/service.py` 多处 |
| P1-9 | `JWT_SECRET` 默认值 `change_me`，生产未覆盖则 Token 可伪造 | `core/config.py:43` |
| P1-10 | `clear_role_permissions_cache` 未实现（仅 logger.info + return 0），角色权限变更后缓存不失效 | `core/rbac/cache.py:179-202` |
| P1-11 | RateLimiterMiddleware 已实现但未注册，API 无限流保护 | `main.py:179-183` |
| P1-12 | CI 仅运行 unit 测试，integration（auth/user/rbac/tenant）不执行 | `.github/workflows/ci.yml:64` |

### 数据库

| # | 问题 | 证据 |
|---|------|------|
| P1-13 | `bookings.membership_card_id` 无外键约束 | `booking/models.py:52-55` |
| P1-14 | `orders.membership_card_id` 无外键约束 | `order/models.py:58-62` |
| P1-15 | `unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` 锁顺序不确定，死锁风险 | `membership/service.py:904-953,1036-1090` |
| P1-16 | 迁移 `76e435f0156c` 执行不可逆 DELETE 且 downgrade 为 pass | `alembic/versions/76e435f0156c_cleanup_old_membership_products.py:22-24` |

### 前端

| # | 问题 | 证据 |
|---|------|------|
| P1-17 | admin tenant 页为静态硬编码，保存按钮无 handler | `apps/admin-web/src/views/tenant/index.vue:11-48` |
| P1-18 | 后端 POST 路由使用尾斜杠 `/`，与 `redirect_slashes=False` 规则冲突 | `course/router.py:226`, `booking/router.py:22` 等 |
| P1-19 | miniapp 无类型检查脚本，30+ TS 错误流入生产 | `apps/miniapp/package.json:5-10` |
| P1-20 | miniapp 声明后端不存在的端点 `sendSms`、`bindAccount` | `apps/miniapp/src/api/index.ts:309-325` |

### AI / MCP

| # | 问题 | 证据 |
|---|------|------|
| P1-21 | 写操作 Tool 无 RBAC 授权校验 | `ai/mcp_server.py` 各 Tool |
| P1-22 | `_handle_business_error` 异常映射表为死代码（英文 key vs 中文消息），兜底回显原始异常 | `ai/agent/runtime.py` |

---

## P2 — 体验问题 / 可维护性 / 技术债

### 后端

| # | 问题 | 证据 |
|---|------|------|
| P2-1 | `/api/v1/courses` 跳过租户中间件，禁用租户用户可访问 | `middleware/tenant_middleware.py:36` |
| P2-2 | 多处 Router 层直接 `db.commit()`，事务边界上移至 Router | `course/router.py:46,100,119` 等 |
| P2-3 | `update_me`、`update_current_teacher`、`admin_unfreeze_card` 用 `data: dict` 无 Pydantic 校验 | `auth/router.py:158`, `teacher/router.py:61`, `membership/router.py:308` |
| P2-4 | `/common/test-exception` 调试接口无认证暴露 | `modules/common/router.py:45-63` |
| P2-5 | Login Token 不含 role 信息，`/admin/my-permissions` 中 role_codes 恒为 None | `modules/auth/service.py:227-232` |
| P2-6 | `auto_cancel_underbooked_schedules` 内部 commit + scheduler commit 双层提交 | `schedule/scheduler.py:150+166` |
| P2-7 | `require_roles` 异常信息包含 `type(e).__name__: {e}` 泄露 | `core/rbac/decorator.py:257` |

### 数据库

| # | 问题 | 证据 |
|---|------|------|
| P2-8 | 排期创建 TOCTOU 竞态，并发可插入时间冲突排期 | `schedule/service.py:72-123` |
| P2-9 | 所有 status 字段无 Check 约束，可写入非法状态值 | 各 models.py |
| P2-10 | `bookings.membership_card_id`、`orders.membership_card_id` 无索引 | booking/models.py, order/models.py |
| P2-11 | `idx_schedules_course` 无 tenant_id 前缀，跨租户查询可能全表扫描 | `schedule/models.py:74` |
| P2-12 | `BaseRepository.count()` 硬编码 `deleted_at.is_(None)`，对无软删除模型抛 AttributeError | `base_repository.py:390` |

### 前端

| # | 问题 | 证据 |
|---|------|------|
| P2-13 | miniapp 租户 slug 缺失时硬编码 fallback `"dance-school"` | `apps/miniapp/src/api/index.ts:118-121` |
| P2-14 | AiAssistant storage 键不一致，sessionId 恒为 anon | `apps/miniapp/src/components/AiAssistant.vue:211` |
| P2-15 | 401 检测机制双端不一致（web 看 HTTP 状态码，miniapp 看业务 code） | `apps/miniapp/src/api/index.ts:167` |
| P2-16 | 多页面 loading 态未渲染 | student-web/schedule, teacher-web/schedule, admin-web/dashboard |
| P2-17 | 多页面列表加载无 error UI（catch 为空或仅 console） | student-web/courses, my-bookings, schedule; teacher-web/courses, schedule |

---

## P3 — 后续优化

| # | 问题 | 证据 |
|---|------|------|
| P3-1 | 定时任务间隔均为 5min（测试模式），生产需调大 | `main.py:77-138` |
| P3-2 | `notify_expiring_membership_cards` 仅打日志，未接入通知 | `membership/scheduler.py:330` |
| P3-3 | MyPy 类型检查 `continue-on-error: true` | `.github/workflows/ci.yml:56` |
| P3-4 | 迁移文件命名风格不统一（hash 前缀 vs snake_case） | `alembic/versions/` |
| P3-5 | `ai/tools/` 目录为历史残留，与 `mcp_server.py` 重复 | `apps/api/src/app/ai/tools/` |
| P3-6 | web 三端构建 chunk > 500kB，element-plus 未按需分包 | 各 app dist |
| P3-7 | AI 输入无 maxlength 校验（后端限制 500 字符） | `apps/miniapp/src/components/AiAssistant.vue:119-128` |
| P3-8 | `order`/`payment`/`notification`/`upload`/`student` 模块仅 models | `modules/{order,payment,notification,upload,student}/` |
| P3-9 | CI 仅 admin-web 跑 lint，student/teacher/miniapp 未校验 | `.github/workflows/ci.yml:88` |

---

## UNKNOWN 项（需进一步验证）

| # | 未知项 | 验证方法 |
|---|--------|---------|
| U1 | 线上数据库是否已执行全部 27 个迁移 | 查询 `alembic_version` 表 |
| U2 | 是否存在孤立预约（membership_card_id 指向不存在的卡） | `SELECT count(*) FROM bookings b LEFT JOIN membership_cards mc ON b.membership_card_id = mc.id WHERE b.membership_card_id IS NOT NULL AND mc.id IS NULL` |
| U3 | 并发压测下排期创建是否确实产生冲突重复 | locust/wrk 对 POST /schedules 并发压测 |
| U4 | `mcp_server.py` 是否实际启动为 stdio server（还是仅被 import 函数） | 读取 `mcp_server.py` 末尾是否有 `mcp.run()` |
| U5 | `PERMISSION_CHECK_BYPASS` 是否有运行时覆盖机制 | 全局搜索 `PERMISSION_CHECK_BYPASS` 赋值点 |
| U6 | 前端 `register` 页面实际可用性（验证码/租户选择流程） | 读取 register/index.vue |
| U7 | miniapp `notification/index` 和 `videos/player` 页面功能 | 读取对应 .vue |
| U8 | `order`/`payment` 模块是否计划接入发卡/扣次流程 | 确认产品需求 |
| U9 | `apps/api/uploads/` 下已存在的头像文件是否为测试数据 | 检查目录并确认 .gitignore |
| U10 | 生产环境实际部署的分支是 main 还是 production | 检查 deploy.yml environment 配置 |
