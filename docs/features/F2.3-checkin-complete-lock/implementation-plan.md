# F2.3 — 签到/完成加行锁 · 实施方案

> Feature ID：F2.3
> 作者：backend-engineer
> 日期：2026-09-28
> 关联文档：[requirement.md](./requirement.md) / [user-flow.md](./user-flow.md) / [acceptance.md](./acceptance.md)

---

## Root Cause

两个写操作端点的 Service 实现采用"读-改-写"无锁模式，存在 TOCTOU（Time-of-Check to Time-of-Use）竞态：

1. **`check_in_booking` 无锁**：[service.py:283](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L283) `booking = await self.repo.get_by_id(db, booking_id)` → 普通 SELECT，不阻塞并发读 → 两并发请求同时读到 `BOOKED` → 同时写 `CHECKED_IN`。
2. **`complete_booking` 无锁**：[service.py:307](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L307) 同模式。

**对照**：`_do_cancel_booking`（[service.py:199-273](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L199-273)）已是正确锁模式——开头 `get_by_id_for_update` → 拿锁后重检 status → 后续全用 `locked_booking`。本 Feature 让 check_in/complete 与之对齐，统一并发安全模型。

## 已核查的代码事实（Evidence）

| 事实 | 证据 |
|------|------|
| `get_by_id_for_update` 已存在且含租户过滤 | [repository.py:202-224](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/repository.py#L202-224)：`select(Booking).where(Booking.id == booking_id).with_for_update()` + `tenant_id` 条件；不用 `skip_locked` |
| cancel 已用同构锁模式 | [service.py:213-219](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L213-219)：`locked_booking = await self.repo.get_by_id_for_update(db, booking.id)` → 拿锁后重检 status |
| `datetime` / `UTC` 已在 service 导入 | [service.py:13](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L13)：`from datetime import UTC, datetime, timedelta` |
| `BookingStatus` / `BusinessException` / `NotFoundException` 已导入 | [service.py:21-28](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L21-28) |
| 端点装饰器 `@require_permissions("booking:manage")` 不变 | [router.py:195](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/router.py#L195) / [router.py:212](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/router.py#L212) |
| Service 签名不变 | `check_in_booking(db, booking_id)` / `complete_booking(db, booking_id)` —— Router 无需改动 |

## Affected Files

| # | 文件 | 改动性质 |
|---|------|---------|
| 1 | `apps/api/src/app/modules/booking/service.py` | `check_in_booking` / `complete_booking` 各 1 处：`get_by_id` → `get_by_id_for_update`；变量名 `booking` → `locked_booking`（与 cancel 对齐）；加注释说明 FOR UPDATE 锁保护 |
| 2 | `apps/api/tests/integration/test_checkin_complete_lock.py` | 新建，覆盖 AC-1 ~ AC-6 |

**不在改动范围**：repository / router / models / schemas / OpenAPI / 前端 / MCP。

## Exact Fix

### 1. `check_in_booking`（service.py:275-297）

```python
async def check_in_booking(
    self,
    db: AsyncSession,
    booking_id: int,
) -> BookingResponse:
    """签到

    并发安全：FOR UPDATE 行锁序列化并发签到请求，拿到锁后重新检查 status
    （等待锁期间另一并发签到可能已完成），与 _do_cancel_booking 同构。
    """
    logger.info(f"[BookingService] 签到: booking_id={booking_id}")

    # 🔑 FOR UPDATE 锁住 booking 行，序列化并发签到
    locked_booking = await self.repo.get_by_id_for_update(db, booking_id)
    if not locked_booking:
        raise NotFoundException("预约不存在")

    # 🔑 拿到锁后重新检查 status（等待锁期间另一并发签到可能已完成）
    if locked_booking.status != BookingStatus.BOOKED.value:
        raise BusinessException("当前预约状态无法签到", code=400)

    locked_booking.status = BookingStatus.CHECKED_IN.value
    locked_booking.checked_in_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(locked_booking)

    logger.info(f"[BookingService] ✅ 签到成功: id={booking_id}")
    return self._to_response(locked_booking)
```

### 2. `complete_booking`（service.py:299-320）

```python
async def complete_booking(
    self,
    db: AsyncSession,
    booking_id: int,
) -> BookingResponse:
    """完成课程

    并发安全：FOR UPDATE 行锁序列化并发完成请求，拿到锁后重新检查 status
    （等待锁期间另一并发完成可能已完成），与 _do_cancel_booking 同构。
    """
    logger.info(f"[BookingService] 完成课程: booking_id={booking_id}")

    # 🔑 FOR UPDATE 锁住 booking 行，序列化并发完成
    locked_booking = await self.repo.get_by_id_for_update(db, booking_id)
    if not locked_booking:
        raise NotFoundException("预约不存在")

    # 🔑 拿到锁后重新检查 status
    if locked_booking.status not in [BookingStatus.BOOKED.value, BookingStatus.CHECKED_IN.value]:
        raise BusinessException("当前预约状态无法完成", code=400)

    locked_booking.status = BookingStatus.COMPLETED.value

    await db.commit()
    await db.refresh(locked_booking)

    logger.info(f"[BookingService] ✅ 课程完成: id={booking_id}")
    return self._to_response(locked_booking)
```

## 关键决策记录（Decision）

| # | 决策 | 理由 |
|---|------|------|
| D1 | 复用既有 `get_by_id_for_update`，不新增 Repository 方法 | 该方法已含租户过滤、按主键 FOR UPDATE、不用 skip_locked；cancel 已验证；零新增基础设施 |
| D2 | 不引入 `skip_locked` | 与 `get_by_id_for_update` 既有约定一致（注释明示"取消操作应排队序列化，而非快速失败"）；签到/完成同属状态机写操作，排队语义正确——第二个请求应看到前一个的提交结果并据此拒绝，而非"快速失败返回 409" |
| D3 | 变量名 `booking` → `locked_booking` | 与 `_do_cancel_booking` 命名同构，自文档化"后续操作均作用于锁定对象"；零行为变更 |
| D4 | status 检查逻辑保持不变 | 拿到锁后重新读取 `locked_booking.status` 即为"重检"——`with_for_update` 保证读到的是最新已提交值；无需额外查询 |
| D5 | 不改 Router / OpenAPI / 前端 / MCP | Service 签名（`db, booking_id`）不变；端点契约不变；check_in/complete 不在 MCP Tool 集合 |
| D6 | 不改 DB 结构 | FOR UPDATE 按主键 `bookings.id` 命中，已有主键索引；无需新索引 |
| D7 | 事务边界仍在 Service | `db.commit()` 仍在 Service 内（与 cancel 一致）；锁随 session 在 commit 后释放 |

## Dependency Analysis

- 复用：`BookingRepository.get_by_id_for_update`（既有）。
- 无新外部依赖；无 DB 结构变更；无 Redis key 变更；无 OpenAPI 变更；无前端影响；无 MCP 影响。
- 契约：`POST /bookings/{id}/check-in` / `POST /bookings/{id}/complete` 路径/方法/请求体/响应模型不变 → 无需 `pnpm gen:types`。

## Regression Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 行锁增加签到/完成请求的串行等待 | 低 | 同一 booking 并发签到/完成是罕见场景（同一学员重复签到）；不同 booking 间无锁竞争（按主键行锁，不锁表）；正常单请求无额外开销（仅 SELECT 多 `FOR UPDATE` 子句） |
| 修复后并发测试仍无法复现双签到 | 低 | live_server 是真实 Uvicorn，FastAPI 在 DB IO `await` 时切换协程，两并发请求的 SELECT 必交错；测试用 `asyncio.gather` 同时发起，且先在"修复前"理论分析确认 TOCTOU 成立 |
| `get_by_id_for_update` 在测试库不被支持 | 低 | PostgreSQL 原生支持 `SELECT ... FOR UPDATE`；该方法已被 cancel_booking 使用并经 F2.2 回归验证 |
| 测试种子数据无可用 booking | 中 | conftest 仅种子用户/角色/权限，无 booking 种子 → 测试内自建课程+教室+排期+预约（参照 F2.2 测试 fixture 模式） |

## Implementation Steps

1. `booking/service.py` 改 `check_in_booking` → py_compile。
2. `booking/service.py` 改 `complete_booking` → py_compile。
3. 静态审查 diff（仅允许 service.py + 新测试文件）。
4. 编写 `test_checkin_complete_lock.py`，迭代至全绿。
5. 回归：`test_booking_ownership.py` + `test_auth_api.py`。

## Verification Plan

| AC | 方式 |
|----|------|
| AC-1 | `test_concurrent_check_in_only_one_succeeds` |
| AC-2 | `test_concurrent_complete_only_one_succeeds` |
| AC-3 | `test_single_check_in_ok` |
| AC-4 | `test_single_complete_ok` |
| AC-5 | `test_check_in_already_checked_in_fails` |
| AC-6 | `test_complete_already_completed_fails` |
| AC-7 | 回归 `test_booking_ownership.py` + `test_auth_api.py` |
| AC-8 | 静态 grep：service 调 `repo.get_by_id_for_update`；无裸 `with_for_update` / `execute` 直写；`db.commit()` 在 Service |

## UNKNOWN

| # | 项 | 处置 |
|---|----|------|
| U1 | 是否有其他仓库内脚本直接调 `BookingService.check_in_booking`/`complete_booking` | grep 已确认仅 router 两处调用；MCP 无此二工具；Service 签名不变 |
| U2 | 并发测试在 live_server 是否真实复现竞态 | 真实 Uvicorn + asyncpg，DB IO `await` 切换协程；`asyncio.gather` 同时发起 → 真实复现；修复前必双签到，修复后必序列化 |
| U3 | `with_for_update()` 在测试库是否生效 | PostgreSQL 原生支持；`get_by_id_for_update` 已被 cancel 使用验证 |
