# F6.6 实施报告

> 日期：2026-10-22。执行：backend-engineer（后端）+ frontend-engineer（小程序），主 Agent 验证与收口。

## 1. Changed Files

| # | 文件 | 类型 |
|---|------|------|
| 1 | `apps/api/src/app/modules/membership/service.py` | 修改 |
| 2 | `apps/api/src/app/modules/membership/router.py` | 修改 |
| 3 | `apps/api/tests/unit/test_card_recommendation.py` | 新增（18 用例） |
| 4 | `apps/api/tests/integration/test_card_recommendation.py` | 新增（9 用例） |
| 5 | `apps/miniapp/src/api/index.ts` | 修改 |
| 6 | `apps/miniapp/src/pages/student/booking-confirm/index.vue` | 修改 |
| 7 | `packages/api-types/openapi.json` / `schema.d.ts` | 生成 |

## 2. Exact Changes

### 2.1 后端 `membership/service.py`

- 新增 `_card_field`：统一读取 ORM/dict 字段。
- 新增 `card_unavailable_reason`：状态、排期日有效期、课程适用性三类原因；未知 `card_type` 返回「不支持的卡类型」。
- `is_bookable_card` 改为委托上述函数，行为与改造前一致（未知类型仍 False）。
- 新增 `card_recommend_unavailable_reason`：在共享判定上追加「次卡已用完」。
- 新增 `_recommend_sort_key`：`expire_at ASC（NULL 最后）→ remaining ASC（None 最后）→ created_at ASC → id ASC`；naive/aware 统一为 UTC。
- 新增 `_recommend_message`：无卡 / 全排除的聚合文案。
- 新增 `recommend_card_for_schedule`：只读，跨模块调用 `ScheduleService.get_schedule_by_id`，租户不匹配 404。

### 2.2 后端 `membership/router.py`

- 新增 `GET /api/v1/membership/recommend-card`，`schedule_id: Query(ge=1)`，仅 `get_current_user`，`response_model=dict`。
- 位于 `my-cards` 之后、`/cards/{card_id}` 之前。

### 2.3 小程序

- `membershipApi.getRecommendCard(scheduleId)`（GET，`schedule_id` 作为 query）。
- `booking-confirm`：
  - 删除 `allCardsWithStatus`、`getDefaultSelectedCard`、`getMyCards` 调用；
  - 新增 `availableCards`、`noAvailableMessage`；
  - 默认选中 `recommended_card_id`，列表严格按后端顺序；
  - 「使用会员卡」卡片体新增 `v-else` 空态，直接展示 `message`；
  - `handleCardSelect` 去掉不可用分支；
  - 保留手动换卡、确认预约、卡展示文案与现有视觉样式。

## 3. Tests Run

| 项 | 命令 | 结果 |
|----|------|------|
| py_compile | `.venv/bin/python -m py_compile service.py router.py` | PASS |
| 新增单测 | `pytest tests/unit/test_card_recommendation.py` | 18 passed |
| 新增集成 | `pytest tests/integration/test_card_recommendation.py` | 9 passed |
| 合并运行 | `pytest tests/unit/test_card_recommendation.py tests/integration/test_card_recommendation.py -q` | **27 passed** |
| 会员卡回归 | `pytest test_membership_card_state_machine.py test_membership_period_card_lifecycle.py test_period_card_booking_validation.py test_booking_card_authorization.py -q` | **29 passed** |
| ruff（改动文件） | `ruff check service.py router.py tests/...` | PASS |
| OpenAPI 生成 | `pnpm gen:types` | PASS（81 路径） |
| 小程序类型 | `pnpm type-check` | PASS |
| 小程序构建 | `pnpm build:mp-weixin` | PASS（Build complete） |

ruff 全目录检查仅剩 `membership/schemas.py:330 W292`，为工作区既有问题，不在本次白名单。

## 4. Scope Verification

- 后端改动仅 2 个文件，符合白名单。
- 新增测试 2 个文件，无修改既有测试。
- 小程序改动仅 API 与 booking-confirm。
- 生成物仅 OpenAPI 两条新增；`my-cards` 契约无变化。
- 未触碰：数据库迁移、`my-cards`、`create_booking`、卡状态机、期卡冲突逻辑、管理端、student-web、MCP/AI、`packages/api-client`。
- 工作区存在 F6.6 之前的历史未提交改动，本 Feature 未回滚、未覆盖。

## 5. Risks

| # | 风险 | 处置 |
|---|------|------|
| R1 | 推荐与下单判定共用基础规则，但期卡区间冲突仍由下单校验（K4） | 预期内；下单失败由 `create_booking` 返回明确错误 |
| R2 | `remaining_credits` 依赖 dict 完整性 | 集成 C-1 已断言 |
| R3 | 小程序空态使用后端文案 | D-4 已覆盖；人工验收确认可读性 |

## 6. UNKNOWN

- E-4 的 500 分支未构造确定性触发；已验证 401/404 不含 traceback/SQL/内部地址。
- 真机选卡体验与文案可读性待人工验收。

## 7. Handoff

- Stage 10：project-architect 复核。
- Stage 11：用户人工验收（真机/开发者工具选卡 + 空态）。
- Stage 12：Backlog/Roadmap/遥测收口。
