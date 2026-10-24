# Phase 2: Database Engineer Analysis

> **日期**: 2026-09-22
> **角色**: database-engineer

---

## 1. 数据库变更评估

### 1.1 查询能力与表结构对照

| 用户意图 | 依赖表 | 现有字段 | 是否充足 |
|---------|--------|---------|---------|
| "我还有几节课？" → 查询我的预约 | `bookings` + `course_schedules` | bookings.student_id, bookings.status, bookings.schedule_id, course_schedules.start_at | ✅ 完全充足 |
| "这周有哪些爵士舞可预约？" → 查询可预约排期 | `course_schedules` + `courses` | course_schedules.course_id, course_schedules.start_at, course_schedules.capacity, course_schedules.booked_count, course_schedules.status, courses.name | ✅ 完全充足 |
| "我还有多少课时？" → 查询课时余额 | `membership_cards` | membership_cards.student_id, membership_cards.total_credits, membership_cards.used_credits, membership_cards.status | ✅ 完全充足 |

### 1.2 Repository 层验证

#### BookingRepository.search (`booking/repository.py:22-64`)

已支持参数:
- ✅ `student_id` 过滤
- ✅ `statuses` 列表过滤（IN 多值）
- ✅ `upcoming=True` → JOIN `course_schedules` 并过滤 `start_at > now()`
- ✅ `exclude_cancelled` 排除已取消
- ✅ tenant_id 自动注入（TenantMixin + do_orm_execute）

#### ScheduleRepository.search (`schedule/repository.py:22-81`)

已支持参数:
- ✅ `course_name` LIKE 关键词搜索
- ✅ `start_from` / `start_to` 日期范围
- ✅ `status` 状态过滤
- ✅ 返回 `capacity` 和 `booked_count` 字段
- ✅ tenant_id 自动注入

#### MembershipCardService.get_user_balance (`membership/service.py:560-584`)

已支持:
- ✅ 按 `student_id` 过滤
- ✅ 按 `status=ACTIVE` 过滤
- ✅ 聚合 `SUM(total_credits)` 和 `SUM(used_credits)`
- ✅ 计算 `remaining = total - used`

### 1.3 索引覆盖检查

| 查询模式 | 需要的索引 | 现有索引 | 状态 |
|---------|----------|---------|------|
| bookings WHERE student_id=? AND status=? | idx_bookings_student_status | ✅ 存在 | ✅ |
| bookings JOIN schedules WHERE start_at > now() | idx_schedules_start_at | ✅ 存在 | ✅ |
| schedules WHERE course_name LIKE ? AND start_at BETWEEN ? | idx_schedules_start_at | ✅ 存在 | ✅ |
| membership_cards WHERE student_id=? AND status=? | idx_membership_cards_student | ✅ 存在 | ✅ |

---

## 2. 结论

### **No Database Change Required**

| 维度 | 结论 |
|------|------|
| 新表 | ❌ 不需要 |
| 新字段 | ❌ 不需要 |
| 新索引 | ❌ 不需要 |
| 新约束 | ❌ 不需要 |
| Alembic Migration | ❌ 不需要 |
| 数据回填 | ❌ 不需要 |
| 锁表风险 | ❌ 不适用 |

所有三个查询意图所依赖的表结构、Repository 查询能力、索引覆盖均已完整存在。本次改动纯限于 AI 层（IntentRecognizer + MCP Tool + AgentRuntime），不触及数据库。
