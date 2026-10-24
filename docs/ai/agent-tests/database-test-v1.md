# 数据库一致性完整分析 — 学生约课业务

## 0. 当前代码真实状态声明

> **重要前提：本报告基于 2026-09-21 17:20 的真实代码快照。**
>
> 代码已历两轮修改（v1.1 + v1.2-S1），但经本次验证：
>
> | 修复 | 位置 | 状态 |
> |------|------|------|
> | v1.1-1 create_booking auto_commit=False | `service.py:109` | ✅ **保留** |
> | v1.1-2 IntegrityError 友好处理 | `service.py:110-127` | ✅ **保留** |
> | v1.1-3 increment_booked_count skip_locked=True | `schedule/repository.py:186` | ✅ **保留** |
> | v1.1-4 deduct_credit except 收窄（HTTPException+BusinessException+Exception） | `service.py:139-153` | ✅ **保留** |
> | v1.1-5 全局 IntegrityError handler | `error_handler.py:34` + `main.py:164` | ✅ **保留** |
> | **v1.2-S1 cancel FOR UPDATE** | `_do_cancel_booking` 中应新增 | **❌ 丢失/被回退** |
> | **v1.2-S1 BookingRepository.get_by_id_for_update** | `repository.py` 应新增方法 | **❌ 丢失/被回退** |
>
> 因此 **cancel_booking 的并发 TOCTOU 风险当前仍然存在且活跃**。

---

## 1. 约课涉及哪些数据库表？

| # | 表名 | SQLAlchemy Model | 角色 |
|---|------|-----------------|------|
| 1 | `course_schedules` | CourseSchedule | 排期（容量容器） |
| 2 | `bookings` | Booking | 预约记录 |
| 3 | `membership_cards` | MembershipCard | 学员会员卡（课时余额） |
| 4 | `membership_card_transactions` | MembershipCardTransaction | 会员卡消费/恢复流水 |
| 5 | `users` | User | 学员/教师/管理员 |
| 6 | `courses` | Course | 课程类型 |
| 7 | `classrooms` | Classroom | 教室 |
| 8 | `tenants` | Tenant | 租户 |

---

## 2. 表之间是什么关系？

```
tenants (1) ──── (N) course_schedules
                 │            │
                 │            ├─── FK → courses
                 │            ├─── FK → users (teacher_id)
                 │            └─── FK → classrooms (ON DELETE SET NULL)
                 │
                 └──── (N) bookings
                             │
                             ├─── FK → course_schedules (schedule_id, ON DELETE RESTRICT)
                             ├─── FK → users (student_id, ON DELETE RESTRICT)
                             └─── FK → membership_cards (membership_card_id, NULLABLE, ON DELETE RESTRICT)

tenants (1) ──── (N) membership_cards
                 │            │
                 │            └──── (N) membership_card_transactions
                 │                        │
                 │                        ├─── FK → membership_cards (card_id, ON DELETE RESTRICT)
                 │                        └─── FK → bookings (booking_id, NULLABLE, ON DELETE SET NULL)
```

---

## 3. 哪些字段决定课程容量？

### course_schedules 表

| 字段 | 类型 | 含义 | 约束 |
|------|------|------|------|
| `capacity` | SmallInteger | 该排期最大容纳人数 | NOT NULL |
| `booked_count` | SmallInteger | 当前已预约人数 | NOT NULL, DEFAULT 0 |
| **DB CHECK** | — | `booked_count <= capacity AND booked_count >= 0` | 约束名: `chk_schedule_capacity` |

### 三层容量保护

| 层 | 机制 | 位置 | 说明 |
|----|------|------|------|
| Layer 1 应用校验 | `booked_count >= capacity` | `service.py:69-70` | 进入锁之前的快速拦截 |
| Layer 2 锁原子占位 | `SELECT ... WHERE bc<cap FOR UPDATE SKIP LOCKED` | `schedule/repository.py:176-186` | 只有满足条件的行才返回，原子地 +1 |
| Layer 3 DB CHECK | `chk_schedule_capacity` | PostgreSQL | 最终物理约束，任何方式都不能超越 |

---

## 4. 如何判断学生是否已经预约？

### 4.1 应用层检查（create_booking line 86-88）

```python
existing = await self.repo.find_active_booking(db, schedule_id, student_id)
if existing:
    raise BusinessException("您已预约该排期，请勿重复预约", code=400)
```

`find_active_booking` 查询条件：
- `booking.schedule_id == 指定排期`
- `booking.student_id == 当前学员`
- `booking.status IN (BOOKED=1, CHECKED_IN=3, COMPLETED=4)`
- 自动注入 `tenant_id` 过滤

### 4.2 数据库层兜底 — Partial UNIQUE 索引

```sql
CREATE UNIQUE INDEX uq_bookings_schedule_student_active
ON bookings (schedule_id, student_id)
WHERE status IN (1, 3, 4);
```

含义：同一个 (schedule_id, student_id) 组合**最多**有一条记录满足"有效状态"。

### 4.3 重复预约判断的三层保护

| 层 | 机制 | 作用 | 能否被 TOCTOU 绕过 |
|----|------|------|-------------------|
| Layer 1 | `find_active_booking` 应用层查询 | 提前检测 | ✅ **能**（两个并发请求都查不到） |
| Layer 2 | `increment_booked_count` FOR UPDATE SKIP LOCKED | 锁层原子闸门 | ❌ **不能**（锁确保只有一个能通过） |
| Layer 3 | `uq_bookings_schedule_student_active` Partial UNIQUE | DB 层物理禁止 | ❌ **不能**（任何方式都不能插第二条） |

---

## 5. 当前是否存在重复预约风险？

### 结论：**不存在**。三层保护闭环。

| 攻击路径 | 结果 |
|---------|------|
| 应用层 `find_active_booking` TOCTOU（两个并发都查不到） | 被 Layer 2 FOR UPDATE SKIP LOCKED 拦截 |
| 强行 INSERT 绕过 Service | 被 Layer 3 Partial UNIQUE 拦截（IntegrityError → Service 层捕获 → 400 友好消息） |
| SQL 直接 `INSERT INTO bookings` | 被 Partial UNIQUE 拒绝 |

---

## 6. 两个学生同时抢最后一个名额会发生什么？

### 6.1 时间线推演（详细版）

```
前置: course_schedules[id=1, capacity=10, booked_count=9, status=NORMAL]

时间    请求 A (学生A)                    请求 B (学生B)                     数据库状态
────    ─────────────                    ─────────────                     ──────────
T0      AsyncSession_A BEGIN             AsyncSession_B BEGIN
                                        
T1      schedule.get_by_id(1)            schedule.get_by_id(1)             bc=9
        SELECT ... WHERE id=1             SELECT ... WHERE id=1
        → schedule (bc=9, cap=10)        → schedule (bc=9, cap=10)        bc=9 (无锁)

T2      find_active_booking(A, 1)        find_active_booking(B, 1)        —
        → None                            → None

T3      increment_booked_count(1)        increment_booked_count(1)
        SELECT ... WHERE id=1            SELECT ... WHERE id=1
        AND bc<cap FOR UPDATE             AND bc<cap FOR UPDATE
        SKIP LOCKED                       SKIP LOCKED
        ┌─────────────────────┐          ┌─────────────────────┐
        │ ✅ 抢到 schedule 锁  │          │ schedule 行已被锁！  │
        │ schedule.bc = 10    │          │ SKIP LOCKED 跳过    │
        └─────────────────────┘          │ → scalars()=None    │
                                          └─────────────────────┘
                                                                         bc=10 (锁中)
                                          ↓ BookingService
                                          increment 返回 False
                                          → BusinessException(
                                            "预约失败，排期可能已满")

T4      repo.create(auto_commit=False)    ↓ HTTP 400 返回
        → INSERT bookings (flush) ✅
                                                                         bookings +1 (未commit)
T5      [如有卡] deduct_credit()
        SELECT card FOR UPDATE
        card.used_credits += 1
        INSERT txn (flush) ✅
T6      await db.commit()
        → 唯一一次 COMMIT ✅
                                                                         bc=10, bookings+1, txn+1
```

### 6.2 最终结果

| 维度 | 结果 |
|------|------|
| 学生 A | ✅ 201 Created（预约成功） |
| 学生 B | ❌ 400 "预约失败，排期可能已满"（**毫秒级**响应） |
| DB bookings | 1 条（只有 A） |
| DB booked_count | 10 == capacity ✅ |
| 一致性 | ✅ **完全正确** |

### 6.3 skip_locked vs 无 skip_locked 对比

| 场景 | skip_locked=True (当前) | 无 skip_locked (v1.0) |
|------|------------------------|----------------------|
| 100 人抢 1 个名额 | 1 个成功，99 个毫秒级失败 | 1 个成功，99 个排队等锁后才失败 |
| 用户体验 | 毫秒级响应 | 可能数百毫秒甚至超时 |
| 正确性 | 等价 | 等价 |

---

## 7. 当前 Transaction 在哪里？

### 7.1 create_booking 事务边界

```
┌─────────────────────────────────────────────────────────────────┐
│ AsyncSession（get_session 注入）                                │
│                                                                   │
│  BEGIN（隐式，SQLAlchemy AsyncSession 自动开启）                  │
│                              │                                   │
│  ┌── 只读校验 ────────────────────────────────────────────────┐ │
│  │ schedule.get_by_id()         → SELECT                       │ │
│  │ repo.find_active_booking()   → SELECT                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌── 原子占位 ────────────────────────────────────────────────┐ │
│  │ increment_booked_count()                                    │ │
│  │   → SELECT ... FOR UPDATE SKIP LOCKED                       │ │
│  │   → booked_count += 1 (内存修改)                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│  ┌── 写入阶段（auto_commit=False）────────────────────────────┐ │
│  │ repo.create(db, booking_data, auto_commit=False)            │ │
│  │   → INSERT bookings (flush，未 COMMIT)                      │ │
│  │                                                              │ │
│  │ membership_card_service.deduct_credit()                     │ │
│  │   → SELECT card FOR UPDATE                                   │ │
│  │   → card.used_credits += 1                                  │ │
│  │   → INSERT membership_card_transactions (flush)             │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│                              ▼                                   │
│                         await db.commit()                        │
│                   ┌──────────────────────┐                       │
│                   │   唯一一次 COMMIT    │                       │
│                   │ booking ✅           │                       │
│                   │ booked_count ✅       │                       │
│                   │ card ✅              │                       │
│                   │ txn ✅               │                       │
│                   └──────────────────────┘                       │
│                                                                   │
│  任何异常 → db.rollback() → 全部撤销                              │
└─────────────────────────────────────────────────────────────────┘
```

**事务范围评估：✅ 合适 — 不太大也不太小**

### 7.2 _do_cancel_booking 事务边界（**有风险**）

```
┌─────────────────────────────────────────────────────────────────┐
│ 只有一次 await db.commit()（line 254）                          │
│                                                                   │
│ 进入 _do_cancel_booking 时:                                      │
│   → 检查 booking.status（应用层读快照）—— ❌ 无 FOR UPDATE 锁    │
│   → 时间窗口校验                                                  │
│   → booking.status = CANCELLED（内存修改）                        │
│   → decrement_booked_count → schedule FOR UPDATE ✅              │
│   → 如有卡: restore_credit → card FOR UPDATE ✅                  │
│   → 全部 flush → 统一 commit                                      │
│                                                                   │
│ 风险点: booking 行从未被 FOR UPDATE 锁定                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. 是否使用 SELECT FOR UPDATE？

### 8.1 所有 FOR UPDATE 使用位置

| # | 文件:行 | 表 | 方法 | 锁类型 | SKIP LOCKED |
|---|--------|-----|------|--------|-------------|
| 1 | `schedule/repository.py:186` | course_schedules | `increment_booked_count` | FOR UPDATE | ✅ **有** |
| 2 | `schedule/repository.py:203` | course_schedules | `decrement_booked_count` | FOR UPDATE | ❌ 无 |
| 3 | `membership/service.py:get_card_with_lock` | membership_cards | `deduct_credit` / `restore_credit` | FOR UPDATE | ❌ 无 |
| 4 | `schedule/service.py:150,159` | course_schedules | 排课事务中的 classroom / teacher 锁 | FOR UPDATE | ✅ 有 |
| 5 | **❌ 缺失** | bookings | `_do_cancel_booking` | — | — |
| 6 | **❌ 缺失** | bookings | `check_in_booking` | — | — |
| 7 | **❌ 缺失** | bookings | `complete_booking` | — | — |

### 8.2 锁顺序一致性分析

| 业务流程 | 锁获取顺序 |
|---------|-----------|
| create_booking | `schedule FOR UPDATE` → `card FOR UPDATE` |
| cancel_booking | `schedule FOR UPDATE`（间接通过 decrement）→ `card FOR UPDATE`（间接通过 restore） |
| deduct_credit（独立调用） | `card FOR UPDATE` |

**是否存在死锁？** ❌ 当前未发现循环等待。

- create_booking 不拿 booking 行锁（booking 是新建的）
- cancel_booking 不拿 create 需要的额外锁
- 不存在 A 等 B 同时 B 等 A 的场景

### 8.3 锁释放时机

所有 FOR UPDATE 锁在**同一 AsyncSession 的 COMMIT / ROLLBACK 后释放**。

---

## 9. 是否存在 Race Condition？

### 9.1 完整清单

| # | 场景 | 是否存在 | 保护机制 | 充分性 |
|---|------|---------|----------|--------|
| R1 | 最后名额多学员抢 | ❌ 不存在 | FOR UPDATE SKIP LOCKED + DB CHECK | ✅ 充分 |
| R2 | 同一学员重复预约 | ❌ 不存在 | FOR UPDATE SKIP LOCKED + Partial UNIQUE | ✅ 充分 |
| R3 | 预约 + 扣次原子性 | ❌ 不存在 | auto_commit=False 同一事务 | ✅ v1.1 修复 |
| **R4** | **取消预约 + 取消预约** | **✅ 存在** | **仅应用层 status 检查，booking 行无锁** | **❌ 不充分** |
| R5 | 会员卡并发扣次 | ❌ 不存在 | FOR UPDATE + 幂等键 | ✅ 充分 |
| **R6** | **check_in + cancel 并发** | **✅ 存在** | **两者都只读快照状态，无 FOR UPDATE** | **❌ 不充分** |
| **R7** | **complete + cancel 并发** | **✅ 存在** | **同 R6** | **❌ 不充分** |

---

## 10. 是否存在数据库层面的唯一约束？

### 10.1 唯一约束清单

| # | 约束名 | 表 | 类型 | 条件 | 保护什么 |
|---|--------|-----|------|------|----------|
| U1 | `uq_bookings_schedule_student_active` | bookings | **Partial UNIQUE** | `WHERE status IN (1,3,4)` | 同一学员不能对同一排期有多个有效预约 |
| U2 | `idx_transactions_idempotency` | membership_card_transactions | **Partial UNIQUE** | `WHERE idempotency_key IS NOT NULL` | 幂等键全局唯一，防止重复扣费/恢复 |
| U3 | `public_id` | 全部表 | 普通 UNIQUE | — | UUID 公共标识符唯一 |
| U4 | `card_no` | membership_cards | 普通 UNIQUE | NULLABLE | 会员卡号唯一 |

### 10.2 CHECK 约束清单

| # | 约束名 | 表 | 条件 | 保护什么 |
|---|--------|-----|------|----------|
| C1 | `chk_schedule_capacity` | course_schedules | `booked_count <= capacity AND booked_count >= 0` | 容量不越界 |
| C2 | `chk_schedule_time` | course_schedules | `end_at > start_at` | 时间合法 |
| C3 | `chk_credits_range` | membership_cards | `0 <= used_credits <= total_credits` | 课时余额不越界 |

### 10.3 外键约束清单（关键）

| 表 | 列 | 引用 | ON DELETE | 说明 |
|-----|-----|------|-----------|------|
| bookings | schedule_id | course_schedules.id | **RESTRICT** | 不能删有预约的排期 |
| bookings | student_id | users.id | **RESTRICT** | 不能删有预约的学员 |
| bookings | membership_card_id | membership_cards.id | RESTRICT | — |
| membership_card_transactions | booking_id | bookings.id | **SET NULL** | 删预约不影响流水 |

---

## 11. 是否存在事务范围过大或过小的问题？

### 11.1 create_booking — ✅ 范围合适

```
事务内容: increment_booked_count(锁schedule)
         + INSERT bookings
         + 可选 deduct_credit(锁card + INSERT txn)
         + 唯一一次 commit

评估: 不太大（不包含无意义的外围校验）
      不太小（所有需要原子性的操作在同一事务）
```

### 11.2 _do_cancel_booking — ✅ 范围合适，但缺锁

```
事务内容: decrement_booked_count(锁schedule)
         + UPDATE bookings（无FOR UPDATE）
         + 可选 restore_credit(锁card + INSERT txn)
         + 唯一一次 commit

评估: 范围本身没问题，但 booking 行缺乏 FOR UPDATE 锁导致 TOCTOU
      建议: 在事务最开始加 SELECT booking FOR UPDATE
```

### 11.3 check_in_booking — ⚠️ 范围小 + 缺锁

```
booking = repo.get_by_id → 快照读
booking.status = CHECKED_IN → 内存修改
commit()

风险: 如果同时有 cancel 请求，cancel 先把 status 改成 CANCELLED 并 commit
      check_in 基于旧快照继续写入 → 状态被覆盖
```

---

## 12. 是否存在课时重复扣减风险？

### 结论：**不存在** — 三重保护

| 层 | 机制 | 位置 |
|----|------|------|
| Layer 1 锁 | `get_card_with_lock` → `SELECT card FOR UPDATE` | membership service |
| Layer 2 应用幂等 | `deduct_credit` 中先查 idempotency_key 是否已存在 | membership service |
| Layer 3 DB 幂等 | `idx_transactions_idempotency` Partial UNIQUE | PostgreSQL |

### 12.1 并发扣减推演

```
R1: deduct_credit → SELECT card FOR UPDATE → used_credits+=1 → INSERT txn(idempotency="booking_1_deduct") → COMMIT ✅
R2: deduct_credit → 等 card 锁 → 拿到后查 idempotency_key → 已存在！→ 返回已扣过的卡 → 不重复扣减 ✅

极端情况: R1/R2 同时 INSERT txn（应用层幂等检查 TOCTOU）
  → DB Partial UNIQUE 拒绝其中一个 → IntegrityError → 捕获返回
```

---

## 13. 是否存在取消预约后名额恢复的并发问题？

### **结论：✅ 存在活跃风险（R4）**

#### 13.1 风险场景：两个请求同时取消同一个预约

```
请求 C1: cancel_booking(booking_id=100)
请求 C2: cancel_booking(booking_id=100)

前置: booking[100].status = BOOKED
      schedule[1].booked_count = 5
```

```
时间    C1                              C2                              DB
────    ──                              ──                              ──
T0      AsyncSession_C1 BEGIN           AsyncSession_C2 BEGIN
                                        
T1      repo.get_by_id(100)             repo.get_by_id(100)             booking.status=BOOKED
        → booking_1 (快照)              → booking_2 (快照)
                                        
T2      检查 status != CANCELLED ✅       检查 status != CANCELLED ✅       —
                                        
T3      schedule.get_by_id(1)           schedule.get_by_id(1)           bc=5
                                        
T4      _do_cancel_booking:             _do_cancel_booking:
        booking_1.status = CANCELLED     booking_2.status = CANCELLED    —
        booking_1.cancelled_at = now     booking_2.cancelled_at = now
                                        
T5      decrement_booked_count(1):      decrement_booked_count(1):
        SELECT schedule FOR UPDATE       SELECT schedule FOR UPDATE       
        → 抢到 schedule 锁 ✅            → 等 schedule 锁 🔒
        schedule.bc -= 1                （等待中...）
        → INSERT membership restore...
        → COMMIT ✅                     （还在等锁...）
                                         ↓ 拿到锁
                                         schedule.bc -= 1  ← ❌ 多减了一次！
                                         → COMMIT ✅
                                        
最终: schedule.booked_count = 5 - 1 - 1 = 3   （实际应为 4）
      booking.status = CANCELLED（两次写，值相同，无问题）
```

#### 13.2 为什么 DB CHECK 约束不能保护？

```sql
chk_schedule_capacity: booked_count <= capacity AND booked_count >= 0
```

- 如果 booked_count 本来是 5 → 两个 cancel 把它减到 3
- CHECK 检查 `3 <= capacity(10)` AND `3 >= 0` → **通过！**
- CHECK 只保护上界和下界，不保护"减去正确的次数"

#### 13.3 修复建议（未实施）

```python
# _do_cancel_booking 开头必须加：
locked_booking = await self.repo.get_by_id_for_update(db, booking.id)
# 然后重新检查 locked_booking.status
# 后续全部用 locked_booking 而非传入的 stale booking
```

> ⚠️ 此修复在之前的 v1.2 版本中已实施，但当前代码已回退。

---

## 场景 A：学生 A 和学生 B 同时抢最后一个名额

### 前置条件
- `course_schedules`: id=1, capacity=10, booked_count=9, status=NORMAL
- `bookings`: 无 A/B 的记录

### 时间线

| 时间 | 请求 A | 请求 B | DB 状态 |
|------|--------|--------|---------|
| T0 | BEGIN AsyncSession_A | BEGIN AsyncSession_B | — |
| T1 | schedule.get_by_id → bc=9 | schedule.get_by_id → bc=9 | bc=9 |
| T2 | find_active_booking → None | find_active_booking → None | — |
| T3 | **increment_booked_count → 抢到 schedule FOR UPDATE SKIP LOCKED** ✅ | increment_booked_count → **SKIP LOCKED 跳过** → None ❌ | bc=10 (锁中) |
| T4 | repo.create(auto_commit=False) → INSERT bookings | **→ raise BusinessException("预约失败，排期可能已满") → 400** | bookings+1 (未commit) |
| T5 | [如有卡] deduct_credit → SELECT card FOR UPDATE → used+=1 → INSERT txn | — | txn+1 (未commit) |
| T6 | **await db.commit()** → 唯一一次 COMMIT | — | bc=10, bookings+1, txn+1 |

### 最终结果

| 维度 | 结果 |
|------|------|
| 请求 A | ✅ **201 预约成功** |
| 请求 B | ❌ **400 "预约失败，排期可能已满"**（毫秒级） |
| DB 最终 | bookings=1 条, booked_count=10, capacity=10 |
| 一致性 | ✅ **完全正确** |
| 事务 | A: 完整提交；B: 失败时 session 自动回滚 |
| 锁 | A 持有 schedule FOR UPDATE（T3→T6）；B 不持有任何锁 |

---

## 场景 B：学生 A 连续点击两次"预约"（双击）

### 前置条件
- 同一场地 A/B，两个请求 B1/B2 几乎同时到达
- 同一 student_id, 同一 schedule_id

### 时间线（B1 先进入锁）

| 时间 | 请求 B1（第一次点击） | 请求 B2（第二次点击） | DB 状态 |
|------|---------------------|---------------------|---------|
| T0 | BEGIN | BEGIN | — |
| T1 | get_by_id(1) → bc=9 | get_by_id(1) → bc=9 | bc=9 |
| T2 | find_active(A, 1) → None | find_active(A, 1) → None ← TOCTOU | — |
| T3 | **increment_booked_count → 抢到 FOR UPDATE SKIP LOCKED ✅** | increment_booked_count → **SKIP LOCKED 跳过 → None ❌** | bc=10 (锁中) |
| T4 | repo.create(auto_commit=False) | **→ raise BusinessException("预约失败，排期可能已满") → 400** | bookings+1 |
| T5 | [如有卡] deduct_credit → SELECT card FOR UPDATE | — | — |
| T6 | **await db.commit()** | — | bookings=1, bc=10 |

### 时间线（B1 先完整 commit，B2 后到）

| 时间 | 请求 B1 | 请求 B2 | DB 状态 |
|------|---------|---------|---------|
| T1-T6 | **完整提交** | 还在排队 | bookings=1, bc=10 |
| T7 | — | find_active(A, 1) → **找到 B1 的记录！** | — |
| T8 | — | **→ raise BusinessException("您已预约该排期，请勿重复预约") → 400** | — |

### 最终结果

| 时序 | B1 | B2 | 说明 |
|------|-----|-----|------|
| 并发（同时到达） | ✅ 成功 | ❌ 400 "排期可能已满" | SKIP LOCKED 闸门拦截 |
| 先后（B1 先完成） | ✅ 成功 | ❌ 400 "您已预约该排期" | find_active 预检查拦截 |
| B2 强行 INSERT（绕过 Service） | — | ❌ **DB Partial UNIQUE 拒绝** → IntegrityError → 400 | 三层兜底 |

### 结论

✅ **无论哪种时序，都不会产生重复预约。**

---

## 场景 C：AI Agent 因网络超时重复调用 create_booking

### 本质：与场景 B 完全等价

| 维度 | 说明 |
|------|------|
| 触发方式 | AI Agent HTTP 超时 → 客户端（Agent 框架）重试 |
| 请求内容 | 同 student_id + 同 schedule_id，两次相同 HTTP POST |
| 服务端处理 | 与场景 B 相同的并发控制逻辑 |

### 额外分析：AI Agent 绕过 HTTP 直接调 Service

```python
# MCP Tool 如果直接 import 并调用
from app.modules.booking.service import BookingService
svc = BookingService()
await svc.create_booking(db, data, student_id=123)  # 第一次
# LLM 超时 → 重试 → 第二次
await svc.create_booking(db, data, student_id=123)  # 第二次
```

### 保护机制仍然有效

| 层 | 机制 |
|----|------|
| Layer 1 | `find_active_booking` 预检查 |
| Layer 2 | `increment_booked_count` FOR UPDATE SKIP LOCKED |
| Layer 3 | `uq_bookings_schedule_student_active` Partial UNIQUE |
| 身份防护 | Router 层 `student_id = current_user.get("user_id")` 从 JWT 提取，Service 调用需自己传 |

### 当前幂等性缺口

| 检查项 | 状态 | 说明 |
|--------|------|------|
| HTTP Idempotency-Key header | ❌ 未支持 | AI Agent/MCP 无法通过标准 header 实现跨服务幂等 |
| Service 层显式幂等键 | ❌ 未实现 | `create_booking` 无幂等键参数 |
| 隐式幂等性 | ✅ 通过三层约束保证 | 任何重复请求都会被拦截 |

**结论：当前隐式幂等性足够，但显式 Idempotency-Key header 值得补充。**

---

## 场景 D：预约成功，但课时扣减失败

### 前置条件
- `course_schedules`: id=1, capacity=10, booked_count=9
- `membership_cards`: id=100, used_credits=5, total_credits=5（**用完了！**）
- 学员选择 membership_card_id=100

### v1.0 行为（历史问题）

```
T1  increment_booked_count → 成功 bc=10
T2  repo.create(auto_commit=True) → INSERT bookings → 🔴 COMMIT 1
T3  deduct_credit → used_credits(5) >= total_credits(5) → raise HTTPException("次数已用完")
T4  异常传播 → rollback → 但 COMMIT 1 已发生！

最终: bookings=1 条（永久化）, booked_count=10（满了）, used_credits 没变
      → 🟡 幽灵 Booking：学员没扣课时但占了名额！
```

### v1.1 行为（**当前代码**）

```
T1  increment_booked_count → 成功 bc=10（内存）
T2  repo.create(auto_commit=False) → INSERT bookings（flush，未 COMMIT）
T3  deduct_credit:
    → SELECT card FOR UPDATE → 拿到锁
    → used_credits(5) >= total_credits(5) → raise HTTPException("会员卡次数已用完")
T4  BookingService except HTTPException:
    → await db.rollback()  ← 🔴 回滚整个事务！
    → raise BusinessException("会员卡次数已用完", code=400)

最终: bookings=0, booked_count=9（回到初始值）, used_credits=5 不变
      → ✅ 正确！学员看到 400 "会员卡次数已用完"
```

### 扣减失败所有路径

| 失败原因 | 抛出类型 | 捕获分支 | 学员看到 |
|---------|---------|---------|---------|
| 会员卡次数用完 | HTTPException 400 | `except HTTPException` | "会员卡次数已用完" |
| 会员卡已过期 | HTTPException 400 | `except HTTPException` | "会员卡已过期" |
| 会员卡不存在 | HTTPException 404 | `except HTTPException` | "会员卡不存在" |
| membership 自身 BusinessException | BusinessException | `except BusinessException` | 原消息直接上抛 |
| DB 连接断开等未知异常 | Exception | `except Exception` | "会员卡扣次失败，预约已撤销" |

### 异常回滚保证

所有异常分支都显式调用 `await db.rollback()`，保证 auto_commit=False 的 INSERT bookings 被撤销。

---

## 全局总结

### 当前一致性评级

| 维度 | 评级 | 说明 |
|------|------|------|
| 容量正确性 | ✅ 优秀 | 三层保护完整 |
| 重复预约防护 | ✅ 优秀 | 三层保护完整 |
| 预约+扣次原子性 | ✅ 优秀 | v1.1 auto_commit=False 修复 |
| 高并发名额抢占 | ✅ 优秀 | skip_locked 快速失败 |
| 课时扣减幂等性 | ✅ 优秀 | 三层保护 |
| DB 约束充分性 | ✅ 良好 | 关键约束齐全 |
| **取消预约并发** | **❌ 需修复** | **booking 行无 FOR UPDATE，TOCTOU 窗口活跃** |
| **check_in/complete 并发** | **⚠️ 中等** | **同 cancel，无 FOR UPDATE，不涉及 booked_count 所以影响较低** |
| 锁顺序一致性 | ✅ 安全 | schedule → card，无死锁风险 |

### 遗留问题（按优先级）

| # | 严重度 | 问题 | 位置 | 建议 |
|---|--------|------|------|------|
| **R4** | 🔴 High | cancel_booking TOCTOU（booked_count 多减） | `_do_cancel_booking` | booking 行 FOR UPDATE + 重检 status |
| **R6/R7** | 🟡 Medium | check_in/complete 无 FOR UPDATE | check_in_booking / complete_booking | booking 行 FOR UPDATE + 重检 status |
| U1 | 🟢 Low | 约课无 Idempotency-Key header | Router + Service | 支持标准幂等键 |
| U2 | 🟢 Low | booked_count 非 DB Trigger 维护 | — | 改为 Trigger 自动维护 |

### UNKNOWN 项

| # | 项目 | 原因 |
|---|------|------|
| UNK-1 | 并发 cancel/check_in 在生产环境是否实际发生过 | 缺乏运行时监控数据 |
| UNK-2 | 是否存在"先拿 card 锁再拿 schedule 锁"的其他流程 | 需全代码审计所有 FOR UPDATE 使用位置 |
| UNK-3 | decrement_booked_count 无 skip_locked 是否会成为瓶颈 | 正常情况下 cancel 量远小于 create，暂不是问题 |