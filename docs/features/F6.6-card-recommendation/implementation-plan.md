# F6.6 实施计划：多卡默认推荐策略（D6）

> 日期：2026-10-22。风险等级 L3。前置：K1–K4 已冻结（见 `requirement.md` §1.1）。
> 本文与真实代码对账完成，未发现未决 Conflict。

## 1. 方案概要

新增一个**只读**端点：

```
GET /api/v1/membership/recommend-card?schedule_id={int}
```

后端读取排期 → 读取当前学员全部卡 → 判定可用性 → 按 D6 排序 → 返回可用卡与推荐卡 id。小程序预约确认页改为消费该端点，删除本地排序与本地可用性过滤。

不新增表、不新增迁移、不写库、不加锁、不改 OpenAPI 之外的既有契约。

## 2. 文件白名单（files_expected）

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `apps/api/src/app/modules/membership/service.py` | 修改 | 共享判定函数 + 推荐 Service 方法 |
| 2 | `apps/api/src/app/modules/membership/router.py` | 修改 | 新增 GET 路由 |
| 3 | `apps/api/tests/unit/test_card_recommendation.py` | 新增 | 纯逻辑单测 |
| 4 | `apps/api/tests/integration/test_card_recommendation.py` | 新增 | HTTP + DB 集成测试 |
| 5 | `apps/miniapp/src/api/index.ts` | 修改 | 新增 `getRecommendCard` |
| 6 | `apps/miniapp/src/pages/student/booking-confirm/index.vue` | 修改 | 消费推荐、删除本地规则 |
| 7 | `packages/api-types/openapi.json` | 生成 | `pnpm gen:types` |
| 8 | `packages/api-types/schema.d.ts` | 生成 | `pnpm gen:types` |
| 9 | `docs/features/F6.6-card-recommendation/*` | 新增 | 9 份产物 |
| 10 | `docs/engineering/task-records/20261022-F6.6-card-recommendation.md` | 修改 | 遥测补全 |
| 11 | `docs/delivery/feature-backlog.md` + `docs/delivery/release-roadmap.md` | 修改 | Stage 12 Close |

**不在白名单**：其他模块 service/repository、数据库迁移、管理端、student-web、MCP/AI、`packages/api-client`（miniapp 使用自有请求层）。

## 3. Spec vs Code 对账

| # | 事实 | 证据 |
|---|------|------|
| C1 | 可用性判定已存在：状态 + 排期日有效期 + 课程类型/课程 | `membership/service.py:550-592` |
| C2 | 下单校验与 C1 同构，返回 400 文案 | `membership/service.py:594-657` |
| C3 | 期卡 `PENDING + valid_from IS NULL` 可预约（D9） | `membership/service.py:538-548` |
| C4 | 学员全部卡查询含 `product_name`/剩余次数/时间字段 | `membership/repository.py:137-200` |
| C5 | Service 已有 `get_student_all_cards` | `membership/service.py:918-934` |
| C6 | 响应 DTO 字段固定 | `membership/schemas.py:160-195` |
| C7 | 排期读取 Service 入口 | `schedule/service.py:523-546` |
| C8 | `my-cards` 无推荐 | `membership/router.py:247-257` |
| C9 | 小程序本地可用性 + 推荐 | `booking-confirm/index.vue:264-379,552-615` |
| C10 | miniapp 请求层对 GET 使用 `data` 作为 query | `apps/miniapp/src/api/index.ts:203-260` |

**结论**：C1 可复用；需补「次卡剩余 > 0」；C4 可直接作为数据源；C7 可跨模块调用。

## 4. 后端实现

### 4.1 `membership/service.py`

**T6.6.1 共享判定（行为保持）**

将现 `is_bookable_card`（`service.py:550-592`）的判断体下沉为：

```python
@staticmethod
def _card_field(card, name):
    return card.get(name) if isinstance(card, dict) else getattr(card, name)

def card_unavailable_reason(
    self,
    card,
    *,
    schedule_start_at: datetime,
    course_id: int,
    course_type_code: str | None,
) -> str | None:
    """返回不可用原因；可用返回 None。仅覆盖状态/有效期/课程适用。"""

def is_bookable_card(self, card, *, schedule_start_at, course_id, course_type_code) -> bool:
    return self.card_unavailable_reason(
        card,
        schedule_start_at=schedule_start_at,
        course_id=course_id,
        course_type_code=course_type_code,
    ) is None
```

原因文案（固定，便于测试）：

| 条件 | 文案 |
|------|------|
| `CANCELLED` | `已作废` |
| `EXPIRED` | `已过期` |
| `FROZEN` | `已冻结` |
| `PENDING` 且不可预约 | `未激活` |
| 其他非 ACTIVE | `已停用` |
| 未知 `card_type`（非 count/period/unlimited） | `不支持的卡类型` |
| 排期日 < `valid_from` | `尚未生效（YYYY-MM-DD 生效）` |
| 排期日 > `expire_at` | `已过期（YYYY-MM-DD 到期）` |
| 课程类型不匹配 | `不适用于此课程类型` |
| 指定课程不匹配 | `不适用于此课程` |

> `is_bookable_card` 行为必须与改造前完全一致（先跑既有单测确认）；`card_type` 必须先校验，未知类型直接返回「不支持的卡类型」，避免 ACTIVE + 未知类型被误判为可用。「次卡用尽」不在共享函数内，仅在推荐链路追加。

**T6.6.2 排序与推荐**

```python
@staticmethod
def _recommend_sort_key(card) -> tuple:
    expire = card.get("expire_at")
    remaining = card.get("remaining_credits")
    created = card.get("created_at")
    max_dt = datetime.max.replace(tzinfo=UTC)
    return (
        expire is None,
        expire or max_dt,
        remaining is None,           # 期卡/无限卡视为不限，排在同到期次卡之后
        remaining if remaining is not None else 0,
        created or max_dt,
        card.get("id") or 0,
    )
```

说明：`expire_at` 升序、NULL 最后；次卡按剩余升序；期卡/无限卡剩余视为 `None` 排在同到期次卡后；`created_at, id` 同分。

```python
async def recommend_card_for_schedule(
    self, db, student_id: int, tenant_id: int, schedule_id: int
) -> dict:
    from app.modules.schedule.service import ScheduleService  # 避免模块级循环导入

    schedule = await ScheduleService().get_schedule_by_id(db, schedule_id)
    if schedule.tenant_id != tenant_id:  # 防御；正常由租户注入 404
        raise HTTPException(status_code=404, detail="排期不存在")

    cards = await self.card_repo.get_all_cards_by_student(db, student_id, tenant_id)
    available, reasons = [], []
    for card in cards:
        reason = self.card_unavailable_reason(
            card,
            schedule_start_at=schedule.start_at,
            course_id=schedule.course_id,
            course_type_code=schedule.course_type_code,
        )
        if reason is None and card.get("card_type") == CardType.COUNT.value:
            if (card.get("remaining_credits") or 0) <= 0:
                reason = "次卡已用完"
        if reason is None:
            available.append(card)
        else:
            reasons.append(reason)

    available.sort(key=self._recommend_sort_key)
    if not cards:
        message = "您还没有会员卡"
    elif not available:
        message = "暂无可用会员卡：" + "；".join(dict.fromkeys(reasons))
    else:
        message = None

    return {
        "schedule_id": schedule_id,
        "recommended_card_id": available[0]["id"] if available else None,
        "available_cards": [MembershipCardResponse.model_validate(c) for c in available],
        "message": message,
    }
```

> `ScheduleResponse` 是否暴露 `tenant_id` 需在实现时确认；若未暴露，依赖 `get_schedule_by_id` 的租户感知查询（不存在即 404），删除该防御分支。

### 4.2 `membership/router.py`

放在 `my-cards` 之后（`router.py:257` 后），避免与 `/cards/{card_id}` 路径冲突：

```python
@router.get("/recommend-card", response_model=dict, summary="获取排期推荐会员卡（学员端）")
async def recommend_card(
    schedule_id: int = Query(..., ge=1, description="排期ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user.get("tenant_id")
    student_id = current_user.get("user_id")
    result = await membership_card_service.recommend_card_for_schedule(
        db, student_id, tenant_id, schedule_id
    )
    return success(data=result)
```

- 认证：`get_current_user`；读本人数据，不需要 `@require_roles`（与 `my-cards` 一致）。
- 无身份参数、无租户参数。

## 5. 小程序实现

### 5.1 `apps/miniapp/src/api/index.ts`

```ts
getRecommendCard(scheduleId: number) {
  return request("/membership/recommend-card", "GET", { schedule_id: scheduleId });
},
```

### 5.2 `booking-confirm/index.vue`

| 改动 | 说明 |
|------|------|
| 删除 `membershipCards` + `allCardsWithStatus`（L264-379） | 可用性判定下沉后端 |
| 删除 `getDefaultSelectedCard`（L552-615） | 推荐改为后端 |
| 新增 `availableCards = ref<any[]>([])`、`noAvailableMessage = ref("")` | 后端结果 |
| `loadData` 中 `getMyCards` → `getRecommendCard(scheduleId)`（L641-655） | 设置列表、选中 id、空态文案 |
| `handleCardSelect` 去掉 `isAvailable` 分支 | 列表只含可用卡 |
| 模板空态：卡片区 `v-else` 直接显示 `noAvailableMessage` | 不依赖选择器；`selectedCard` 为空时也渲染原因 |
| 选择器保留（仅展示 `availableCards`） | 有卡时可手动切换 |
| 保留 `getCardRemainingText` / `getCardApplicableText` / 课程类型映射 | 展示不变 |
| `selectedCard` 改为基于 `availableCards` | 保持既有展示 |

改造后本地不再存在任何排序或可用性规则（AC D-6）。

## 6. 测试计划

### 6.1 单元测试 `tests/unit/test_card_recommendation.py`

直接调用 `MembershipCardService()` 的纯方法（不建库）：
- 排序：过期优先 / NULL 最后 / 次卡剩余升序 / `created_at,id` 同分 / 同到期期卡与无限卡排在次卡后。
- 判定：状态、排期日边界（当天可用、次日不可用）、`valid_from` 未生效、课程类型、指定课程、期卡 PENDING 两分支、未知 `card_type`。
- 文案聚合：无卡 / 全排除。

### 6.2 集成测试 `tests/integration/test_card_recommendation.py`

复用 `tests/membership_support.py`（`db_factory/get_seed_ids/create_course/create_schedule/create_card/create_product/cleanup/login/headers/future_start`）：
- C-1/C-2：多卡排序与推荐 id。
- C-3：过期/冻结/作废/未生效/用尽/类型不匹配排除。
- C-4/C-5：空态与文案。
- C-6/C-7/C-8：401 / 404 / 跨租户。
- C-9：调用前后卡与流水不变。
- E-2：同租户两学员只返回本人卡。
- E-4：404/500 响应不含 traceback、SQL、内部 URL。

### 6.3 回归

```bash
cd apps/api
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_card_recommendation.py tests/integration/test_card_recommendation.py -q
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_membership_card_state_machine.py tests/integration/test_membership_period_card_lifecycle.py tests/integration/test_period_card_booking_validation.py tests/integration/test_booking_card_authorization.py -q
```

小程序：

```bash
cd apps/miniapp
pnpm vue-tsc --noEmit   # 若脚本存在
pnpm build              # 以实际 package.json 为准
```

## 7. 静态验证

```bash
cd apps/api
.venv/bin/python -m py_compile src/app/modules/membership/service.py src/app/modules/membership/router.py
.venv/bin/ruff check src/app/modules/membership tests/unit/test_card_recommendation.py tests/integration/test_card_recommendation.py
pnpm --dir ../.. gen:types   # 仓库根实际命令为准
git diff --stat
```

## 8. 风险 / UNKNOWN

| # | 项 | 处理 |
|---|----|------|
| R1 | `is_bookable_card` 重构引入行为漂移 | 先跑既有单测；改造后逐条对照 |
| R2 | `ScheduleResponse` 无 `tenant_id` | 依赖租户感知查询；实现时确认，缺则删防御分支 |
| R3 | 期卡 PENDING 语义误判 | 单测固定 R-4 两分支 |
| R4 | 小程序无卡时无法打开选择器 | 模板增加空态可点击区域 |
| R5 | 时区边界 | 全部使用 `schedule.start_at.date()` 与 `.date()` 比较 |
| UNKNOWN | miniapp 构建脚本命名 | 实施时读 `apps/miniapp/package.json` 确认 |
| UNKNOWN | 集成测试种子数据是否含多条卡 | 实施时以 `membership_support.py` 实际 helper 为准 |

## 9. 任务拆分

| Task | 内容 | 执行者 |
|------|------|--------|
| T6.6.1 | 共享判定函数重构（保持 `is_bookable_card` 行为） | backend-engineer |
| T6.6.2 | Service 推荐方法 + 排序/文案 | backend-engineer |
| T6.6.3 | Router 端点 + 认证 | backend-engineer |
| T6.6.4 | 单元 + 集成测试 | backend-engineer |
| T6.6.5 | 小程序 API + 预约确认页改造 | frontend-engineer |
| T6.6.6 | OpenAPI 生成、静态验证、回归、9 份产物、遥测、Close | 主 Agent / architect |

## 10. 回滚

- 后端：移除 `recommend-card` 路由与两个 Service 方法；`is_bookable_card` 委托可保留（等价）。
- 前端：恢复 `getMyCards` + 本地过滤/排序（不推荐，回滚仅用于紧急）。
- 无数据库迁移，无数据回滚。

## 11. Out of Scope 守卫

实施中不得顺手修改：`my-cards` 行为、`create_booking` 校验、卡状态机、期卡冲突逻辑、`packages/api-client`、管理端/student-web、MCP/AI。
