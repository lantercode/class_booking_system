# AI 自然语言课程查询 — 最终架构报告

> **日期**: 2026-09-22
> **角色**: project-architect
> **状态**: ✅ Phase 0-8 全部完成

---

## 1. 任务概述

为 class_booking_system 增加"AI 自然语言查询我的课程、剩余课次以及可预约课程"能力。

用户可以输入：
- "我还有几节课？" → 查询我的未完成预约
- "我这周有哪些爵士舞可以预约？" → 查询可预约排期
- "我还有多少课时？" → 查询会员卡课时余额

## 2. 完整调用链

```
User: "我还有几节课？"
  │
  ▼
POST /api/v1/ai/chat (JWT Bearer Token)
  │
  ├─ get_current_user → {user_id:42, tenant_id:7, role_id:2}
  ├─ set_user_id(42), set_tenant_id(7), set_role_id(2)
  │
  ▼
AgentRuntime(user_id=42, tenant_id=7)
  │
  ├─ SessionManager.add_message("system", SYSTEM_PROMPT)     ← 新增
  ├─ SessionManager.add_message("user", "我还有几节课？")
  ├─ IntentRecognizer.recognize("我还有几节课？")
  │   → intent="get_my_bookings"                               ← 新增关键词
  │   → params={"upcoming": True}                              ← 新增提取
  │
  ├─ await get_my_bookings(                                     ← 新增 upcoming 参数
  │     user_id=42,             ← JWT 硬注入
  │     tenant_id=7,            ← JWT 硬注入
  │     upcoming=True,           ← IntentRecognizer 提取
  │   )
  │   │
  │   ├─ _require_auth(42, 7) ✅
  │   ├─ set_tenant_id(7)
  │   ├─ SessionLocal() BEGIN
  │   ├─ BookingService.list_bookings(db, student_id=42, upcoming=True, exclude_cancelled=True)
  │   │   └─ BookingRepository.search()
  │   │       └─ SELECT ... WHERE student_id=42 AND tenant_id=7
  │   │           AND status IN (BOOKED, CHECKED_IN) AND start_at > now()
  │   │           ← do_orm_execute 自动注入 tenant_id=7
  │   └─ 返回 "您还有 3 节课：\n- [已预约] 09/22 19:00 成人爵士舞..."
  │
  └─ 格式化回复 → "📋 预约记录：\n您还有 3 节课：..."
```

## 3. 改动文件清单

| # | 文件 | 改动类型 | 具体改动 | 行数 |
|---|------|---------|---------|------|
| 1 | `ai/agent/prompts.py` | 新建 | System Prompt（角色定义 + 安全规则 + 回复规则） | 25 行 |
| 2 | `ai/agent/intent.py` | 修改 | ① INTENTS 重排优先级 ② get_my_bookings 增加"几节课"等关键词 ③ get_my_balance 增加"还有多少课时" ④ query_schedules 增加"可以预约""可以约" ⑤ create_booking 精确化为"帮我预约" ⑥ 新增 UPCOMING_KEYWORDS ⑦ _extract_params 增加 upcoming 提取 | 20 行 |
| 3 | `ai/mcp_server.py` | 修改 | ① get_my_bookings 增加 upcoming: bool=False 参数 ② 调用 Service 时传入 upcoming + exclude_cancelled ③ upcoming=True 时返回"您还有 N 节课" ④ query_schedules 返回标注"已满" ⑤ query_schedules date 参数 try/except 校验 | 15 行 |
| 4 | `ai/agent/runtime.py` | 修改 | ① import SYSTEM_PROMPT ② get_my_bookings 调用透传 upcoming ③ chat 方法注入 SYSTEM_PROMPT 到会话上下文 | 5 行 |

**总改动量: ~65 行**

## 4. 不改动的文件

| 文件/层 | 原因 |
|---------|------|
| modules/booking/service.py | list_bookings 已支持 upcoming + exclude_cancelled |
| modules/schedule/service.py | list_schedules 已支持 course_name + date range |
| modules/membership/service.py | get_user_balance 已返回正确格式 |
| 任何 repository.py | 查询逻辑已完整 |
| 任何 models.py | 无数据库变更 |
| 任何 alembic migration | 无数据库变更 |
| 任何 router.py（非 AI） | 不影响非 AI API |
| 任何 schemas.py | 不改 Schema |

## 5. 数据库变更

**No Database Change Required.**

| 维度 | 结论 |
|------|------|
| 新表 | ❌ 不需要 |
| 新字段 | ❌ 不需要 |
| 新索引 | ❌ 不需要 |
| Alembic Migration | ❌ 不需要 |

## 6. 安全检查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Authentication | ✅ | AgentRuntime 从 JWT 硬注入 user_id/tenant_id |
| Authorization | ⚠️ | RBAC BYPASS=True（全局问题，不在本次范围） |
| Tenant Isolation | ✅ | set_tenant_id + ORM 事件自动注入 |
| Input Validation | ✅ | query_schedules date 参数增加 try/except |
| Prompt Injection | ✅ | System Prompt 包含"忽略越权指令"安全规则 |
| PII 泄漏 | ✅ | Tool 返回值不含 PII |
| SQL 注入 | ✅ | SQLAlchemy 参数化查询 |

## 7. 测试结果

| 测试类型 | 结果 | 详情 |
|---------|------|------|
| 语法检查 | ✅ 4/4 | py_compile 全部通过 |
| 意图识别 | ✅ 9/9 | 3 个用户场景全覆盖 |
| 现有测试回归 | ✅ 3/3 | test_multi_turn_booking 全部通过 |
| 回归引入 | ✅ 0 | 无任何回归 |
| MCP 测试 | 4 FAIL | 预先存在（_require_auth 不传 tenant_id） |

## 8. 核心原则验证

| 要求 | 满足 |
|------|------|
| 1. 必须复用现有业务逻辑 | ✅ BookingService / ScheduleService / MembershipCardService |
| 2. 不允许 MCP 直接访问数据库 | ✅ MCP Tool → Service → Repository → SQLAlchemy |
| 3. 不允许复制已有 Service | ✅ 不新建 Service |
| 4. 必须经过现有 Service | ✅ |
| 5. 必须保证 Authentication | ✅ JWT + _require_auth |
| 6. 必须保证 Authorization | ⚠️ RBAC BYPASS 全局问题 |
| 7. 必须保证 Tenant Isolation | ✅ 三层隔离 |
| 8. 必须考虑 Redis | ✅ SessionManager 不变 |
| 9. 必须考虑错误处理 | ✅ date 校验 + Tool 异常捕获 |
| 10. 必须考虑 AI Tool 输入校验 | ✅ |
| 11. 必须区分静态知识和实时业务数据 | ✅ 课程信息实时查询 |
| 12. 数据库无需修改 | ✅ No Database Change Required |
| 13. 不为 AI 修改无关模块 | ✅ 仅改 ai/ 目录 |

## 9. 产出文件

| 文件 | 说明 |
|------|------|
| `docs/ai/architecture/ai-course-query-architecture.md` | Phase 0-1 项目盘点 + 架构分析 |
| `docs/ai/architecture/ai-course-query-final.md` | 本文件 — 最终架构报告 |
| `docs/ai/implementation/ai-course-query-backend.md` | Phase 2 后端专家分析 |
| `docs/ai/implementation/ai-course-query-database.md` | Phase 2 数据库专家分析 |
| `docs/ai/implementation/ai-course-query-mcp.md` | Phase 2 MCP 专家分析 |
| `docs/ai/tests/ai-course-query-test-report.md` | Phase 6 测试报告 |
| `apps/api/src/app/ai/agent/prompts.py` | 新建 — System Prompt |
| `apps/api/src/app/ai/agent/intent.py` | 修改 — 意图识别增强 |
| `apps/api/src/app/ai/mcp_server.py` | 修改 — Tool 契约增强 |
| `apps/api/src/app/ai/agent/runtime.py` | 修改 — 透传 + Prompt 注入 |
