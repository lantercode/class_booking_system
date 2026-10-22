# F6.6 需求：多卡默认推荐策略（D6）

> 来源：`docs/delivery/feature-backlog.md`「Feature 6.6」（L532-548）、`docs/features/F6.0-membership-card-prototype/open-decisions.md` D6（L48-54、L146）。
> 日期：2026-10-22。风险等级 **L3**（backend + miniapp，无 DB 结构变更、无事务改动）。

## 1. Stage 1 READY 结论

| 项 | 结论 |
|----|------|
| Selected Feature | F6.6 多卡默认推荐策略（D6） |
| Why | F6.3/F6.4/F6.5 已稳定卡状态与预约语义；D6 已冻结；小程序本地规则与 D6 相反，存在两端不一致风险 |
| Dependencies | F6.3（卡状态/有效期/课程适用语义）✅；F6.5 已交付 ✅ |
| Existing Capabilities | `MembershipCardService.is_bookable_card`（`service.py:550-592`）、`get_student_all_cards`（`service.py:918-934`）、`MembershipCardResponse`（`schemas.py:160-195`）、`GET /membership/my-cards`（`router.py:247-257`） |
| Missing Capabilities | 后端无推荐端点；小程序本地排序未按 D6（`booking-confirm/index.vue:552-615`） |
| Risks | 可用性判定与 `create_booking` 存在漂移风险；期卡 PENDING 语义易误排除 |
| Required Agents | backend-engineer、frontend-engineer、project-architect（契约/复核） |
| Definition of Ready | **READY**：4 项契约决策已由用户冻结（2026-10-22） |

### 1.1 已冻结决策（2026-10-22）

| # | 决策 | 结论 |
|---|------|------|
| K1 | 接口形态 | 新增独立端点 `GET /api/v1/membership/recommend-card?schedule_id=`；`my-cards` 不变 |
| K2 | 同分排序键 | `created_at ASC, id ASC` |
| K3 | 无可用卡 | HTTP 200 + `recommended_card_id=null` + `available_cards=[]` + `message` |
| K4 | 排除范围 | 仅基础可用性；期卡区间冲突仍由下单时 `validate_period_card_booking` 校验 |

## 2. 问题（真实代码证据）

1. **本地推荐与 D6 相反**：小程序默认选中逻辑按 `unlimited → period → count` 类型优先，次卡按剩余次数**降序**（`apps/miniapp/src/pages/student/booking-confirm/index.vue:552-615`）。D6 要求「先过期优先 → 剩余次数少优先 → 同分取先发放」。
2. **可用性判定在前端**：状态、有效期、课程适用、余额均在 `allCardsWithStatus` 本地计算（`index.vue:264-379`），与后端 `validate_card_for_booking`（`service.py:594-657`）形成两套规则。
3. **后端无推荐能力**：`membership/router.py` 无 recommend 路由；`my-cards` 返回全部卡（`router.py:247-257`），过滤责任落在客户端。
4. **无可用卡时无理由展示**：模板仅渲染 `availableCards`（`index.vue:172-217`），空态固定文案「暂无可用的会员卡」，未说明原因。

## 3. 目标

- 后端提供唯一权威的「按排期推荐会员卡」只读能力，返回按 D6 排序的可用卡与推荐卡 id。
- 小程序预约确认页消费该端点，删除本地推荐/过滤规则。
- 无可用卡时展示后端聚合原因，而不是固定文案。

## 4. 范围

### 4.1 In Scope

- 新增 `GET /api/v1/membership/recommend-card`，仅接收 `schedule_id`。
- `MembershipCardService` 新增只读方法：读取排期（跨模块调 `ScheduleService`）→ 读取学员全部卡 → 可用性判定 → D6 排序 → 返回结果。
- 可用性判定复用 `is_bookable_card` 语义（状态 + 按排期日有效期 + 课程适用），并补充次卡剩余次数 > 0。
- 响应 DTO：`schedule_id`、`recommended_card_id`、`available_cards`（`MembershipCardResponse[]`）、`message`。
- 小程序 `booking-confirm` 改为调用新端点；选择器按后端顺序展示；空态展示 `message`。
- 单元测试（纯排序/判定/文案）+ 集成测试（HTTP 契约、排除规则、空态、权限）。
- OpenAPI 重新生成（`pnpm gen:types`），生成产物不手改。

### 4.2 Out of Scope

- 不做自动替卡/自动顺延（D3）。
- 不做多卡同时扣次，不改发卡/扣次/回补事务。
- 不做期卡区间冲突预校验（K4，仍由下单校验）。
- 不改 `my-cards`、卡列表页、管理端、student-web、MCP/AI。
- 不新增数据表、迁移或索引。
- 不改 F6.3/F6.4/F6.5 的既有判定结果。

## 5. 用户故事

| # | 角色 | 故事 |
|---|------|------|
| US-1 | 学员 | 打开预约确认页时，系统自动选中「最该先用」的卡，不用我理解卡规则。 |
| US-2 | 学员 | 我想知道为什么没有可用卡（已过期/次数用完/不适用），而不是只看到「暂无可用卡」。 |
| US-3 | 机构 | 小程序与管理端/后端对「可用卡」的判断一致，不出现前端能选、下单被拒。 |

## 6. 业务规则

| # | 规则 |
|---|------|
| R-1 | 身份与租户只来自认证上下文（`current_user`），请求不接收 `student_id/tenant_id`。 |
| R-2 | 排期必须存在且属于当前租户；不存在返回 404（复用 `ScheduleService.get_schedule_by_id`）。 |
| R-3 | 可用性判定以**排期日**（`schedule.start_at.date()`）比较有效期，不使用 `now`；`expire_at` 当天可用。 |
| R-4 | 次卡/无限卡必须 `ACTIVE`；期卡 `ACTIVE` 或 `PENDING` 且 `valid_from IS NULL`（D9）可用；`PENDING` 但已定生效日的期卡不可用。 |
| R-5 | `EXPIRED/FROZEN/CANCELLED` 及其他状态一律排除。 |
| R-6 | 次卡 `remaining_credits <= 0` 排除。 |
| R-7 | `applicable_course_type_code` 非空时必须等于排期课程类型；`applicable_course_ids` 非空时必须包含排期课程。 |
| R-8 | 排序：`expire_at ASC（NULL 最后）→ 剩余次数 ASC（期卡/无限卡视为不限，排在同到期次卡后）→ created_at ASC → id ASC`。 |
| R-9 | `recommended_card_id = available_cards[0].id`；无可用卡为 `null`。 |
| R-10 | 无可用卡仍返回 200；`message` 聚合原因：无卡 →「您还没有会员卡」；有卡但被排除 →「暂无可用会员卡：<原因>；<原因>」。 |
| R-11 | 只读：不写库、不加锁、不产生流水、不触发状态流转。 |
| R-12 | 响应字段沿用 `MembershipCardResponse`，不新增卡字段，避免契约漂移。 |

## 7. 响应契约

```json
{
  "code": 0,
  "msg": "ok",
  "request_id": "req_0123456789abcdef",
  "data": {
    "schedule_id": 6,
    "recommended_card_id": 12,
    "available_cards": [ /* MembershipCardResponse[]，按 R-8 排序 */ ],
    "message": null
  }
}
```

无可用卡：

```json
{
  "code": 0,
  "msg": "ok",
  "request_id": "req_0123456789abcdef",
  "data": {
    "schedule_id": 6,
    "recommended_card_id": null,
    "available_cards": [],
    "message": "暂无可用会员卡：次卡已用完；会员卡已过期"
  }
}
```

## 8. 依赖与风险

| 项 | 说明 |
|----|------|
| 依赖 | F6.3 卡状态语义；F6.4 排期时间；F6.5 已完成（无直接依赖） |
| 风险 1 | `is_bookable_card` 与推荐判定重复 → 重构为共享判定函数，`is_bookable_card` 委托，避免漂移 |
| 风险 2 | 期卡 PENDING 误排除 → 规则 R-4 显式覆盖，测试用例固定 |
| 风险 3 | 时区比较 → 统一使用排期日 `.date()`，与 `validate_card_for_booking` 一致 |
| 风险 4 | 小程序改造回归 → 保留手动换卡与无卡空态，构建校验 |
