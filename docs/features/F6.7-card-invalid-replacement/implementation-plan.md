# F6.7 实施计划：卡失效替代与受影响预约（D3）

> 日期：2026-10-22。依据 requirement.md（K1–K3 冻结）、acceptance.md（A–F 分层）。
> Agent 分工：backend-engineer（T6.7.1–T6.7.2、T6.7.5 后端部分）、frontend-engineer（T6.7.3、T6.7.4、T6.7.5 前端部分）、project-architect（契约复核/Review）。

## 1. 架构决策

### 1.1 查询归属：BookingService 新增只读方法（决策）

**决策**：`BookingService.get_affected_bookings_by_card()`，由 membership 模块路由调用。

理由（证据）：
1. 分层规则禁止跨模块 Repository 直调——「按卡查预约」的数据访问必须落在 booking 模块（`BookingRepository`）。
2. `booking/service.py:45` 已顶层持有 `membership_card_service` 单例；反向（membership/service.py → booking.service）会构成**循环 import**（membership/service.py 当前不 import 任何其他模块 service，证据：其 import 区仅含自身 models/repository/schemas）。
3. 归属校验（R-5）与既有 `reschedule_booking` 归属校验（`booking/service.py:381-382`）同模块同约定，内聚。
4. 明细所需排期关联字段复用 booking 模块既有 `_get_schedule_info_map` 模式，无重复实现。

**备选（已否决）**：membership Service 函数内 lazy import booking_service——可破循环但引入非常规 import 风格，且把预约投影逻辑放进 membership 模块，内聚性差。

### 1.2 调用链

```
GET /api/v1/membership/cards/{card_id}/affected-bookings
  → membership/router.py（参数/DI 仅：card_id、page、page_size、db、current_user、redis_client）
  → BookingService.get_affected_bookings_by_card(db, card_id=, tenant_id=, requester_user_id=, redis_client=, page=, page_size=)
      ① membership_card_service.get_card(db, card_id, tenant_id)   # 404 / 跨租户屏蔽（复用 service.py:493-501）
      ② check_roles(db, ["admin","super_admin"], redis_client, requester_user_id, tenant_id)  # checker.py:335
         非 admin 且 card.student_id != requester_user_id → PermissionException(403)
      ③ BookingRepository.list_affected_by_card(db, card_id, tenant_id, now=datetime.now(UTC), page, page_size)
      ④ 排期/课程/教室/教师信息组装 → AffectedBookingsResponse
```

### 1.3 Repository 新增（必需）

`BookingRepository` 当前仅有存在性查询（`exists_card_booking_with_statuses`，`:367-388`）与最早时间聚合（`:390-418`），**无明细+计数能力** → 新增：

```python
async def list_affected_by_card(
    self, db, card_id: int, tenant_id: int, *, now: datetime,
    page: int, page_size: int,
) -> tuple[int, list[Booking]]:
    # WHERE membership_card_id = :card_id AND tenant_id = :tenant_id
    #   AND status IN (BOOKED, CHECKED_IN)
    #   AND schedule.start_at > :now          # JOIN CourseSchedule
    # ORDER BY schedule.start_at ASC, booking.id ASC
    # 返回 (total, items)；显式 tenant_id 条件与既有方法同风格（:372,382 先例）
```

- 排期字段可随 JOIN 一次性 SELECT（`join` + `add_entity`/列查询），避免 N+1。
- 无新表、无迁移、无索引改动（`membership_card_id` 查询走既有索引；数据量小）。

### 1.4 端点注册与权限形态

- 位置：`membership/router.py`，置于 `/cards/{card_id}`（`:279`）之后任意 GET 区段（路径不同无匹配冲突）。
- **不挂** `@require_roles`（混合角色端点）；函数签名含 `db`、`current_user`、`redis_client`（`redis_client=Depends(get_redis_client)`，供 `check_roles` 使用）。
- 路由内不做任何业务判断（归属在 Service）。

## 2. 文件白名单（允许改动）

### 后端（apps/api）

| 文件 | 改动 |
|------|------|
| `src/app/modules/booking/repository.py` | 新增 `list_affected_by_card` |
| `src/app/modules/booking/service.py` | 新增 `get_affected_bookings_by_card`（只读） |
| `src/app/modules/booking/schemas.py` | 新增 `AffectedBookingItem`、`AffectedBookingsResponse` |
| `src/app/modules/membership/router.py` | 新增 GET 端点（import `booking_service`、`get_redis_client`） |
| `tests/test_membership_affected_bookings.py`（新） | B/C 级测试（含并发 C-11/C-12） |

### 前端共享包与 admin-web

| 文件 | 改动 |
|------|------|
| `packages/api-client/src/membership.ts` | 新增 `AffectedBookingsResponse` 类型 + `membershipCardApi.getAffectedBookings(id, params)` |
| `apps/admin-web/src/views/membership/index.vue` | 冻结弹窗（`:363-392`）与作废弹窗（`:394-414`）内嵌影响面区域；`openFreezeDialog/openCancelDialog`（`:902,988`）触发查询；新增局部状态（affected loading/error/total/items） |

### miniapp

| 文件 | 改动 |
|------|------|
| `apps/miniapp/src/api/index.ts` | `bookingApi` 新增 `reschedule(bookingId, data, idempotencyKey)`；`membershipApi` 新增 `getAffectedBookings(cardId)`（可选调用，本期主要用于核对场景） |
| `apps/miniapp/src/pages/student/bookings/index.vue` | my-cards 并行加载与 join；警示条渲染；换卡按钮；选卡弹层（消费 recommend-card）；空态「联系机构」 |

### 明确禁止改动

- `membership/service.py`（freeze/cancel 事务不动）、`booking/service.py` 的 `reschedule_booking`/`create_booking` 事务路径
- `packages/api-types` 生成产物（只重新生成，不手改）
- student-web / teacher-web 全部文件
- 任何迁移文件、`.env*`、`membership_support.py` 既有夹具签名（可新增 helper，不改既有行为）

## 3. 任务拆分（T6.7.x）

| # | 任务 | Agent | 依赖 | 验收映射 |
|---|------|-------|------|----------|
| T6.7.1 | Repository `list_affected_by_card` + Service `get_affected_bookings_by_card`（含 404/403/口径/排序/分页）+ DTO | backend | — | B-1..B-12 |
| T6.7.2 | 端点注册 + redis_client DI + OpenAPI 复核 + `pnpm gen:types` | backend | T6.7.1 | A-3/A-4、C-1..C-10、E-1..E-4 |
| T6.7.3 | api-client 方法 + admin 双弹窗影响面区域（四态 + 不阻断） | frontend | T6.7.2（契约冻结后） | D-1..D-4、A-5 |
| T6.7.4 | miniapp：api 方法 + 警示条 join + 选卡弹层 + 改派 + 空态 | frontend | T6.7.2 | D-5..D-10、A-5 |
| T6.7.5 | 测试落地：B/C 用例（含并发 C-11 优先、C-12 次之）+ 前端自验（vue-tsc/build） | backend + frontend | T6.7.1–T6.7.4 | B、C、A-1/A-2/A-5 |

执行顺序：T6.7.1 → T6.7.2（**契约冻结点**：OpenAPI 生成后前端才开始）→ T6.7.3 ∥ T6.7.4 → T6.7.5 → Review。

## 4. 测试清单（落地到文件）

- `tests/test_membership_affected_bookings.py`：B-1..B-12（Service 层，`db_factory` 直造数据）、C-1..C-10（HTTP，`login/headers`）、C-11/C-12（`asyncio.gather` 竞态）。
- 夹具复用 `membership_support.py`：`create_card`、`create_booking`、`future_start(days=3)`、`fetch_booking`（直改 status=3 构造 CHECKED_IN 未来态）、`cleanup`。
- 前端自验：admin-web `vue-tsc -b && vite build`；miniapp `vue-tsc` + `build:mp-weixin`；`pnpm gen:types` 后 `packages/api-types` 与 OpenAPI 逐对象一致。
- 回归：membership 定向（F6.6 既有 29 例）+ booking/reschedule 定向（F6.5 既有并发用例）分批执行（注意 D-F6.5-6 会话级 fixture 债务，回归分批）。

## 5. 风险

| # | 风险 | 等级 | 缓解 |
|---|------|------|------|
| R-1 | 影响面 TOCTOU：admin 看到 N 后学员改派成功，实际作废时受影响数已变 | 低 | 查询只读 + 文案「以操作时实际为准」（R-7）；acceptance 并发专项验证结果可解释 |
| R-2 | 小程序「换卡」是**从零新建**的改派 UI（全前端无 reschedule 先例），工作量被低估风险 | 中 | T6.7.4 独立任务、选卡器复用 recommend-card 契约（F6.6 已验证）；不新建请求层 |
| R-3 | CHECKED_IN 未来态在真实数据中可能极少，前端分支漏测 | 低 | D-6 强制用例；B-2/C-7 覆盖 |
| R-4 | 混合角色端点漏挂归属校验（无装饰器兜底） | 中 | A-7 代码审查项 + B-8/C-3/E-2 实测；实现时对照 `reschedule_booking:381-382` |
| R-5 | F6.5 改派对「旧卡已作废」的回补路径未经单测（F6.5 B-14 NOT VERIFIED） | 中 | C-11 顺带覆盖；不修改派事务，仅观察断言账务守恒 |
| R-6 | 历史未提交改动（F6.5 之前）与本 Feature 文件交集 | 低 | 仅改白名单文件；实施前 `git status` 核对，不覆盖他人改动 |

## 6. UNKNOWN（实施期需确认，不阻塞开工）

| # | 问题 | 默认处理 |
|---|------|----------|
| U-1 | miniapp「联系机构」具体入口形态（电话直拨 vs 门店页跳转） | 复用 profile/门店既有入口；若均不存在则展示机构电话文案（不新增后端） |
| U-2 | recommend-card 对「卡已失效但有预约」场景返回的 `message` 文案是否需为换卡语境定制 | 本期原样展示（F6.6 契约不变）；文案优化登记后续 |
| U-3 | admin 明细预览条数（暂取 5）与是否需「查看全部」跳转 | 5 条 + 无跳转；若验收要求全量再加分页弹层 |
| U-4 | teacher 角色访问该端点的真实需求 | 按非 admin 处理（仅本人卡，E-3）；无需求不放开 |
| U-5 | 批量作废影响面是否在本期顺带展示聚合 N | 本期不做（Out of Scope 已登记）；若产品坚持，按 N 次单卡调用实现，不进事务 |

## 7. Handoff 摘要

- **→ backend-engineer**：实施 T6.7.1/T6.7.2 + C 级测试。关键约束：查询方法放 `BookingService`（循环 import 证据 §1.1）；端点无 `@require_roles`，归属校验在 Service；复用 `check_roles`（`core/rbac/checker.py:335`）；禁止改 freeze/cancel/reschedule 事务。
- **→ frontend-engineer**：T6.7.3/T6.7.4。契约冻结点 = T6.7.2 完成 + `pnpm gen:types`。admin 影响面查询失败不阻断主操作；miniapp 改派必须带幂等键；CHECKED_IN 分支不渲染换卡按钮。
- **冲突面**：暂无已知跨 Agent 冲突；U-1/U-3 若在实施期产生分歧，回 Architect 仲裁（不私下妥协）。
