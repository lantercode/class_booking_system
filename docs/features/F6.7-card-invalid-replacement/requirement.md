# F6.7 需求：卡失效替代与受影响预约（D3）

> 来源：`docs/delivery/feature-backlog.md`「Feature 6.7」（L560-577）、F6.0 open-decisions D3（2026-10-16 确认）。
> 日期：2026-10-22。风险等级 **L4**（backend + admin-web + miniapp，无 DB 结构变更；改派事务复用 F6.5 已交付能力）。

## 1. Stage 1 READY 结论

| 项 | 结论 |
|----|------|
| Selected Feature | F6.7 卡失效替代与受影响预约（D3） |
| Why | 冻结/作废当前直接改状态、无预约影响面（`membership/service.py:1153-1221, 2187-2234`）；`conflict-check` 只查同课程类型卡冲突、不查预约（`service.py:1320-1362`）；学员侧无任何换卡自助入口 |
| Dependencies | F6.5（原子改派 `POST /bookings/{id}/reschedule`，card_swap 模式）✅ 已交付；F6.3（卡状态机 PENDING=0/ACTIVE=1/EXPIRED=2/FROZEN=3/CANCELLED=6）✅；F6.6（recommend-card，可作替代卡选择器数据源）✅ |
| Existing Capabilities | 见 §1.2 |
| Missing Capabilities | 见 §1.3 |
| Risks | 见 implementation-plan.md §风险 |
| Required Agents | backend-engineer、frontend-engineer、project-architect（契约/复核） |
| Definition of Ready | **READY**：K1–K3 已由用户冻结（2026-10-22） |

### 1.1 已冻结契约（K1–K3）

| # | 决策 | 结论 |
|---|------|------|
| K1 | 「受影响预约」口径 | 预约状态 ∈ {BOOKED(1), CHECKED_IN(3)} 且排期 `start_at` 在未来；排除 COMPLETED(4)/NO_SHOW(5)/CANCELLED(2) 与已开始课程 |
| K2 | 端点形态 | 单端点 `GET /api/v1/membership/cards/{card_id}/affected-bookings`；admin/super_admin 可查本租户任意卡；student 仅可查本人卡 |
| K3 | 换卡改派 | 复用 F6.5 `POST /api/v1/bookings/{booking_id}/reschedule`（同排期纯改派：`new_schedule_id` = 原排期 + `new_membership_card_id` = 替代卡），本 Feature 不新增改派事务 |

### 1.2 可复用能力（真实代码证据）

| 能力 | 位置 | 说明 |
|------|------|------|
| 卡查询（404/跨租户） | `membership/service.py:493-501` `get_card` | 不存在→404「会员卡不存在」；`TenantAwareRepository` 自动注入使跨租户查询返回 None→404；手工 tenant 校验兜底 403 |
| 按卡查预约（存在性） | `booking/repository.py:367-388` `exists_card_booking_with_statuses` | 查询模式可复用（card_id + tenant_id + status IN），但仅返回 bool，不满足明细需求 |
| 预约 JOIN 排期 | `booking/repository.py:390-418` `get_earliest_card_booking_start` | Booking JOIN CourseSchedule 模式可复用 |
| 混合角色判定 | `core/rbac/checker.py:335` `check_roles` | `require_roles` 装饰器底层 helper，可在 Service 内直接调用于「admin 或本人」作用域判定 |
| 归属校验先例 | `membership/service.py:1417-1418`（student_unfreeze 403）、`booking/service.py:381-382`（reschedule `PermissionException` 403） | 项目统一约定：同租户非本人 → 403 |
| 改派事务 | `booking/service.py:344+` `reschedule_booking` | card_swap 模式原地更新 `membership_card_id`，名额不变；advisory→booking→schedule(id ASC)→card(id ASC) 固定锁序 + 幂等键 |
| 预约↔卡映射字段 | `booking/schemas.py:52` `BookingResponse.membership_card_id` | 小程序预约列表项已带卡 ID，可在前端做卡状态 join |
| 管理端预检对话框模式 | `admin-web/src/views/membership/index.vue:930-963` `handleAdminUnfreeze` | 先调 `checkConflict` 再分支展示，F6.7 同构复用该交互模式 |
| 测试夹具 | `apps/api/tests/membership_support.py` | `create_course/schedule/product/card/booking/student`、`fetch_*`、`cleanup`、`future_start`、`db_factory`、`login/headers` 齐备 |

### 1.3 缺失能力

1. 后端无「按卡查受影响预约明细 + 计数」查询（Repository/Service/端点三层均缺）。
2. admin-web 冻结弹窗（`index.vue:363-392`）与作废弹窗（`:394-414`）仅原因表单，无影响面展示。
3. `packages/api-client/src/membership.ts` 无 affected-bookings 方法。
4. 小程序预约列表（`miniapp/src/pages/student/bookings/index.vue`）无卡失效警示；**全部前端（admin-web/student-web/miniapp/api-client）均无任何 reschedule 调用**（全库 grep 无匹配）——F6.5 仅交付后端，小程序改派 UI 需从零构建（API 方法 + 选卡弹层 + 确认 + 刷新）。
5. 小程序无替代卡空态与「联系机构」引导。

## 2. Scope

### 2.1 In Scope

- 后端新增 `GET /api/v1/membership/cards/{card_id}/affected-bookings`：归属校验、租户隔离、分页、计数。
- admin-web：冻结/作废确认弹窗内展示「该卡有 N 个有效预约」+ 明细预览（前几条的课程/时间）。
- miniapp：我的预约列表对「卡已失效」的预约展示警示条 + 「换卡」入口（调 F6.5 改派）；无替代卡时空态引导联系机构。
- OpenAPI 重新生成（`pnpm gen:types`），生成产物不手改。
- 测试：单元（口径/归属）+ 集成（HTTP 契约）+ 并发专项（冻结/作废 vs 改派竞态 ≥1 条）。

### 2.2 Out of Scope

- 自动顺延、自动取消预约、通知推送（F6.2）。
- 批量作废（`batch_cancel_cards`）影响面聚合展示（对话框在 `index.vue:416+`，本期不做，登记为后续候选）。
- student-web / teacher-web 任何改动（F6.11 未落地，本期无学员 Web 端自助场景）。
- 冻结/作废事务本身改动（不新增锁、不改状态机）；改派事务改动（F6.5 已冻结）。
- CHECKED_IN 预约的自助改派（`reschedule_booking` 仅允许 BOOKED，`booking/service.py:403-404`，不在本期放宽）。

## 3. 业务规则

| # | 规则 |
|---|------|
| R-1 | 「受影响」精确定义：`Booking.membership_card_id = card_id` AND `Booking.status ∈ (1 BOOKED, 3 CHECKED_IN)` AND `CourseSchedule.start_at > now(UTC)`（严格大于）。比较方式与 `reschedule_booking` 已开始判定一致（`booking/service.py:409`，`start_at <= now` 视为已开始）。 |
| R-2 | **CHECKED_IN 未开始真实存在**：`check_in_booking`（`booking/service.py:876-904`）仅校验 `status == BOOKED`，无签到时间窗口——提前签到可产生 CHECKED_IN + 未来 start_at。K1 将其纳入口径正确；但该状态的预约**不可自助改派**（R-6）。 |
| R-3 | 时区：全链路使用 timezone-aware UTC（`datetime.now(UTC)`，`membership/service.py:1183`、`booking/service.py:409`）；`start_at` 为 UTC 存储，边界「开始时刻 == now」视为已开始（排除）；「当天稍晚的未来时刻」包含。前端展示按设备本地时区格式化，不影响口径。 |
| R-4 | 身份与租户只来自 `get_current_user` 的 JWT payload（`user_id`、`tenant_id`，`deps/auth.py:40-66`）；端点不接收 student_id/tenant_id 参数。 |
| R-5 | 角色作用域：admin/super_admin（经 `check_roles` 判定）可查本租户任意卡；其余角色（student）要求 `card.student_id == user_id`，否则 403「无权查看该卡的受影响预约」（与 `student_unfreeze_card`、`reschedule_booking` 归属校验同约定）。 |
| R-6 | 改派入口仅对 BOOKED 预约开放；CHECKED_IN 预约的警示文案引导「联系机构处理」，不展示换卡按钮（后端 `reschedule_booking` 会 400 拒绝，前端不兜底重试）。 |
| R-7 | 冻结/作废仅「展示影响面」，不阻断操作（D3-a 为警示策略）；影响面数据为实时查询结果，操作完成时以实际为准（TOCTOU 已知限制，见 acceptance 并发专项）。 |
| R-8 | 只读端点：不开事务、不加锁、不写库；不得因本端点在 `freeze_card`/`cancel_card` 内新增预约侧校验（保持事务边界不变）。 |
| R-9 | 错误不回传 traceback/SQL/内部信息；走统一异常体系信封 `{code,msg,data}`。 |
| R-10 | 排序：`start_at ASC, booking.id ASC`（稳定次序，便于前后端对拍）。 |

### 3.1 403 vs 404 决策（K2 遗留问题）

**结论：同租户非本人 → 403；跨租户/不存在 → 404。**

理由：① 项目既有约定统一——`get_card` 跨租户经租户自动注入返回 None→404（`service.py:495-497`），`student_unfreeze_card` 同租户非本人→403（`:1417-1418`），`reschedule_booking` 非本人→403；② 该端点是「卡的子资源」，卡本身的可见性已决定 404/403 语义，子资源不应另造约定；③ 403 不泄露额外信息（攻击者已知卡存在性才会探测子资源，而卡存在性本身受 404 保护）。

## 4. 响应契约

### 4.1 请求

```
GET /api/v1/membership/cards/{card_id}/affected-bookings?page=1&page_size=20
Headers: Authorization: Bearer <token>, x-tenant-slug: <slug>
Path: card_id int >= 1
Query: page int >= 1（默认 1）；page_size int 1..100（默认 20）
```

- 无尾斜杠；`redirect_slashes=False`。
- 身份/租户仅经请求头，**不接受**请求体或 query 中的身份参数。

### 4.2 响应（200）

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "card_id": 123,
    "card_status": 3,
    "total": 2,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "booking_id": 9001,
        "schedule_id": 501,
        "status": 1,
        "start_at": "2026-10-25T02:00:00Z",
        "end_at": "2026-10-25T03:00:00Z",
        "course_name": "爵士舞基础",
        "classroom_name": "A教室",
        "teacher_name": "王老师"
      }
    ]
  }
}
```

| 字段 | 说明 |
|------|------|
| `card_id` / `card_status` | 回显卡 ID 与当前卡状态（int，CardStatus 枚举） |
| `total` | 受影响总数（跨分页；admin 弹窗「N 条」取此值） |
| `items[].booking_id` | 改派与小程序警示匹配的主键 |
| `items[].status` | 1=BOOKED / 3=CHECKED_IN（前端区分「可换卡」与「联系机构」） |
| `items[].start_at/end_at/course_name/classroom_name/teacher_name` | 明细展示字段（复用 `BookingResponse` 关联字段口径，`booking/schemas.py:63-67`） |

- 不含学员 PII（卡归属已由端点语义隐含）；不含手机号。
- 分页决策：**保留分页**而非全量——期卡受影响预约理论上限约 90+（每日 1 约 × 有效期），admin 弹窗只需计数 + 前几条预览；page_size 上限 100 防滥用。

### 4.3 错误

| HTTP | 场景 |
|------|------|
| 401 | 未认证 / token 失效 |
| 403 | 同租户非本人卡（student 角色） |
| 404 | 卡不存在或跨租户（租户自动注入屏蔽） |
| 400 | 分页参数非法（Pydantic） |

### 4.4 四端影响面确认

| 端 | 影响 |
|----|------|
| admin-web | **改**：弹窗展示影响面（调本端点） |
| miniapp | **改**：可选调本端点核对；主流程用 my-cards + 预约列表 join（见 user-flow） |
| student-web | 不涉及（Out of Scope，显式确认） |
| teacher-web | 不涉及（显式确认） |

## 5. 用户故事

| # | 角色 | 故事 |
|---|------|------|
| US-1 | 机构管理员 | 冻结/作废卡之前，我能看到「该卡有 N 个有效预约」及明细，避免误操作引发学员投诉。 |
| US-2 | 学员 | 我的卡被冻结/过期/作废后，在预约列表能看到警示，并能一键把预约换到我的其他有效卡上。 |
| US-3 | 学员 | 如果我没有可替代的卡，告诉我联系机构，而不是让我反复尝试失败。 |
| US-4 | 机构 | 学员只能查询/改派自己的预约，不能看到他人的卡与预约。 |
