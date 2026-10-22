# F6.6 最终 Review：多卡默认推荐策略（D6）

> 日期：2026-10-22。阶段：feature-delivery-lifecycle Stage 10（最终门禁复核）。
> 角色：project-architect。结论取值仅允许 `READY_FOR_ACCEPTANCE` / `NEEDS_FIX`。
> 本 Review 不复核工作区中 F6.5 之前的历史未提交改动；范围严格限定 F6.6 产物与下列文件。

## 1. Review Scope

### 1.1 复核输入

| 类型 | 内容 |
|------|------|
| Feature 产物 | `requirement.md`、`user-flow.md`、`acceptance.md`、`implementation-plan.md`、`implementation-report.md`、`static-verification.md`、`runtime-test-report.md` |
| 后端代码 | `apps/api/src/app/modules/membership/service.py`、`apps/api/src/app/modules/membership/router.py` |
| 后端测试 | `apps/api/tests/unit/test_card_recommendation.py`、`apps/api/tests/integration/test_card_recommendation.py` |
| 小程序 | `apps/miniapp/src/api/index.ts`、`apps/miniapp/src/pages/student/booking-confirm/index.vue` |
| 生成物 | `packages/api-types/openapi.json`、`packages/api-types/schema.d.ts` |
| 流程 / 规则 | `.trae/skills/orchestration/feature-delivery-lifecycle/SKILL.md`、`.trae/rules/architecture/*`、`.trae/rules/security/*`、`.trae/rules/ai/*`、`docs/ai/workflows/multi-agent-collaboration-v3.md` |

### 1.2 本次实际执行的验证命令与结果

| # | 命令 | 结果 |
|---|------|------|
| V1 | `cd apps/api && .venv/bin/python -m py_compile src/app/modules/membership/service.py src/app/modules/membership/router.py` | PASS |
| V2 | `cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_card_recommendation.py -q` | **18 passed** |
| V3 | `cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_card_recommendation.py -q` | **9 passed** |
| V4 | `cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_membership_card_state_machine.py tests/integration/test_membership_period_card_lifecycle.py tests/integration/test_period_card_booking_validation.py tests/integration/test_booking_card_authorization.py -q` | **29 passed** |
| V5 | `cd apps/api && .venv/bin/ruff check`（仅 4 个改动文件） | All checks passed |
| V6 | 导入 `app.main` 生成 OpenAPI 与 `packages/api-types/openapi.json` 逐对象比较（不写文件） | `paths_equal=True`、`schema_equal=True`、81 路径 |
| V7 | `npx --no-install openapi-typescript packages/api-types/openapi.json -o /tmp/schema_f66.d.ts` 后与 `schema.d.ts` diff | 完全一致（生成物无手改） |
| V8 | `cd apps/miniapp && pnpm type-check` | PASS |

补充说明：

- 未重复执行 `pnpm build:mp-weixin`（会生成构建产物），以 `runtime-test-report.md` 的记录为证据；`vue-tsc` 已由本 Review 复跑。
- 按任务要求**未执行任何 git 操作**，因此无法用 `git diff` 独立证明“工作区改动 ⊆ 白名单”。范围结论基于逐文件代码检查与报告交叉核对，见 §5.2 的 UNKNOWN。
- 未修改任何业务代码、其他 Feature 产物或生成物。

## 2. Findings

### 2.1 Blocker

无。

### 2.2 Major

无。

### 2.3 Minor

#### M-1 推荐端点响应未建模，OpenAPI 200 为泛型对象

- 证据：
  - `apps/api/src/app/modules/membership/router.py:260-276`：`response_model=dict`。
  - `packages/api-types/openapi.json:6519-6530`：200 schema 为 `type=object / additionalProperties=true`。
  - `packages/api-types/schema.d.ts:6839-6850`：响应类型为 `{[key: string]: unknown}`。
  - `apps/miniapp/src/pages/student/booking-confirm/index.vue:445-452`：前端以 `any` 消费 `available_cards / recommended_card_id / message`。
- 影响：路径与 query 参数在 OpenAPI 中真实存在，运行时字段经集成测试验证；但响应结构无法由生成类型静态校验，违反 `architecture/contracts.md` “响应 DTO 以后端 Pydantic 模型为准”的精神。
- 定级理由：`GET /membership/my-cards` 同样使用 `response_model=dict`（`router.py:247-257`，OpenAPI 同样为泛型），本 Feature 延续既有约定且未造成契约破坏，故不阻断验收；登记为技术债 `D-F6.6-1`。

#### M-2 booking-confirm 残留引用已删除字段的死代码

- 证据：
  - 原 `apps/miniapp/src/pages/student/booking-confirm/index.vue:309-335`（已删除）：`getStatusBadgeClass` 引用已删除的 `card.unavailableReason`；`getCardIcon` 亦无调用方。
  - 同文件模板与脚本中不存在对这两个函数的引用（`getStatusBadgeClass`、`getCardIcon` 仅定义处出现）。
- 影响：无运行时影响，但属于本地规则清理不彻底，容易被后续维护者误认为仍存在前端可用性判定。
- 处置：Stage 10 后已在本次 Feature 内删除这两个死函数（`vue-tsc --noEmit` 复跑通过）；`D-F6.6-2` 关闭。

#### M-3 D6 排序对“期卡/无限卡无剩余次数”的判定依赖数据为 NULL

- 证据：
  - `apps/api/src/app/modules/membership/service.py:1026-1040`：排序键用 `remaining_credits is None` 区分“不限次卡”，而非 `card_type`。
  - `apps/api/src/app/modules/membership/service.py:652-673`：“次卡已用完”仅对 `CardType.COUNT` 生效。
  - `apps/api/src/app/modules/membership/service.py:455-472`：发放时 `total_credits = data.total_credits or product.total_credits`，未按卡类型强制置空。
  - `apps/api/tests/unit/test_card_recommendation.py:109-125`：B-5 用例显式传入 `remaining_credits=None`。
- 影响：正常发放（期卡/无限卡产品 `total_credits=NULL`）下排序完全符合 D6；若历史/手工数据给期卡或无限卡写入了 `total_credits`，该卡会按“剩余次数”参与排序，偏离“期卡/无限卡视为不限、排在同到期次卡后”的口径。
- 定级理由：当前发放路径与测试数据均满足前提，属数据完整性边界风险；登记为 `D-F6.6-3`（UNKNOWN 数据面）。

#### M-4 推荐请求失败时复用“空态”渲染，与 user-flow §4 的“错误态”要求不完全一致

- 证据：
  - `apps/miniapp/src/pages/student/booking-confirm/index.vue:453-458`：`catch` 仅 Toast“加载失败”，未设置独立错误态，也未清空已加载的排期信息。
  - 同文件 `113-116`：`selectedCard` 为空时直接渲染 `noAvailableMessage`（默认“暂无可用的会员卡”）。
  - `docs/features/F6.6-card-recommendation/user-flow.md:48-52`：要求“任一失败进入错误态，不渲染半成品选卡区域”。
- 影响：推荐接口失败时用户会同时看到 Toast 与“暂无可用会员卡”空态文案，存在“把错误误读为无卡”的体验风险；但没有渲染本地兜底推荐，D-5 的验收口径仍成立。
- 定级理由：无业务规则错误、无越权与数据风险；登记为 `D-F6.6-4`。

#### M-5 requirement 示例信封与项目统一 `success()` 输出存在文案差异

- 证据：
  - `docs/features/F6.6-card-recommendation/requirement.md:89-115`：示例为 `msg: "success"`，未含 `request_id`。
  - `apps/api/src/app/core/response.py:18-24`：统一 `success()` 返回 `code=0`、`msg="ok"`，并附带 `request_id`。
- 影响：仅为文档示例与统一信封的文案差异；实际实现使用全项目统一 helper，与 `my-cards` 等端点一致，前端只判断 `code`，无契约破坏。
- 处置：以真实代码为准；建议后续文档示例与统一信封对齐，不阻断验收。

## 3. AC Traceability

> 结果词：PASS / PARTIAL / FAIL。B/C 的 PASS 均有本次实际复跑证据（V2/V3/V4），非仅引用报告。

### 3.1 A. 静态 / 构建

| # | 结果 | 证据 |
|---|------|------|
| A-1 | PASS | `router.py:260-276` 仅参数、依赖、Service 调用、`success()`；无业务判断/SQL |
| A-2 | PASS | `service.py:1066-1070` 仅调用 `ScheduleService.get_schedule_by_id`，未查 schedule 表 |
| A-3 | PASS | `service.py:1072` 复用 `get_all_cards_by_student(student_id, tenant_id)`；`repository.py:137-200` 参数化查询，Repository 继承 `TenantAwareRepository` |
| A-4 | PASS | `service.py:1055-1096` 无 `commit/flush/FOR UPDATE`；`core/database.py:16-22` 会话仅 rollback |
| A-5 | PASS | `is_bookable_card` 委托 `card_unavailable_reason`（`service.py:630-650`）；推荐仅追加余额规则（`652-673`） |
| A-6 | PASS | 实际生成 OpenAPI 与产物完全一致（V6），81 路径；新路径 `openapi.json:6481`；`my-cards` 路由体未改（`router.py:247-257`）。注：响应 schema 为泛型，见 M-1 |
| A-7 | PASS | V7 重新生成 `schema.d.ts` 到临时文件，与仓库产物 diff 一致 |
| A-8 | PASS | V1 `py_compile` 通过 |
| A-9 | PASS | V5 `ruff check` 四文件全部通过 |
| A-10 | PASS | V8 `pnpm type-check` 通过；`build:mp-weixin` 以 `runtime-test-report.md` 的 PASS 记录为准（本 Review 未复跑） |

### 3.2 B. 单元测试

| # | 结果 | 证据（`tests/unit/test_card_recommendation.py`） |
|---|------|------|
| B-1 | PASS | `63-69` |
| B-2 | PASS | `72-77` |
| B-3 | PASS | `80-87` |
| B-4 | PASS | `90-106` |
| B-5 | PASS | `109-125` |
| B-6 | PASS | `142-197`（状态/未生效/过期/课程/用尽） |
| B-7 | PASS | `200-213` |
| B-8 | PASS | `216-229` |
| B-9 | PASS | `232-245` |
| B-10 | PASS | `297-309` |

V2 结果：18 passed，用例数与报告一致。

### 3.3 C. 集成测试

| # | 结果 | 证据（`tests/integration/test_card_recommendation.py`） |
|---|------|------|
| C-1 | PASS | `90-143`，断言 200/`code=0`/推荐 id=首卡 |
| C-2 | PASS | `131-137`，重复请求顺序与推荐 id 不变 |
| C-3 | PASS | `147-216`，八类排除卡 + 1 张有效卡 |
| C-4 | PASS | `220-254`，200 + null + 空列表 + 原因聚合 |
| C-5 | PASS | `258-279`，无卡文案精确等于“您还没有会员卡” |
| C-6 | PASS | `283-288`，无 Token → 401 |
| C-7 | PASS | `292-301`，随机 id → 404，响应无 traceback/SQL/内部地址 |
| C-8 | PASS | `305-324`，跨租户排期 → 404，不泄露排期 id |
| C-9 | PASS | `328-362`，调用前后卡状态、次数、有效期、流水均不变 |
| C-10 | PASS | V4 回归 29 passed（状态机 + 期卡生命周期 + 期卡下单校验 + 卡授权） |

V3/V4 结果与 `runtime-test-report.md` 的 9 passed / 29 passed 一致。

### 3.4 D. 前端行为

| # | 结果 | 证据 |
|---|------|------|
| D-1 | PASS | `index.vue:450`，`selectedCardId = recommended_card_id` |
| D-2 | PASS | `index.vue:447-449` 直接保存后端数组；模板 `179-216` 按 `availableCards` 顺序渲染 |
| D-3 | PASS | `index.vue:411-413` 手动切换；`467-484` 确认时传当前 `selectedCardId` |
| D-4 | PASS | `index.vue:113-116` 卡片区直接展示 `noAvailableMessage`；`154-160` 无选中卡时按钮禁用；选择器仅由选中卡区域打开（`416-418`） |
| D-5 | PASS | `index.vue:453-458` Toast“加载失败”，无本地兜底推荐。注：错误态与空态共用渲染，见 M-4 |
| D-6 | PASS | 全文已无 `allCardsWithStatus` / `getDefaultSelectedCard` / `getMyCards` 调用；本地仅保留展示格式化函数。注：残留死代码见 M-2 |
| D-7 | PASS | `tests/unit/test_card_recommendation.py:248-267`，ACTIVE + `card_type="vip"` 判为“不支持的卡类型” |

### 3.5 E. 权限 / 租户 / 安全

| # | 结果 | 证据 |
|---|------|------|
| E-1 | PASS | `router.py:265-275` 仅 `get_current_user` 提供身份；端点无 `student_id/tenant_id` 入参 |
| E-2 | PASS | `tests/integration/test_card_recommendation.py:366-390`，同学员两卡只返回当前登录学员的卡 |
| E-3 | PASS | C-8（`305-324`）跨租户排期 404；卡查询显式 tenant + TenantAwareRepository 双重隔离 |
| E-4 | PASS | C-7/C-8 断言响应不含 `Traceback/SELECT/postgresql/127.0.0.1/.py`。500 分支未构造确定性触发点，记为 UNKNOWN（见 §4.2），沿用全局异常处理 |

### 3.6 F. 人工验收

| # | 结果 | 说明 |
|---|------|------|
| F-1 | PARTIAL | 代码路径与类型检查已复核；真机/开发者工具选卡流程待 Stage 11 用户人工确认 |
| F-2 | PARTIAL | 空态文案由后端 `message` 直出（`index.vue:451-452`）；可读性待人工确认 |
| F-3 | PARTIAL | 推荐为只读，未自动下单；需人工抽查“推荐卡可下单、排除卡被拒” |

F 组未执行为流程设计使然，不构成代码缺陷，也不影响 `READY_FOR_ACCEPTANCE`。

## 4. Architecture Boundary Check

### 4.1 边界逐项核对

| 边界 | 结论 | 证据 / 说明 |
|------|------|-------------|
| 调用链 | PASS | `miniapp → GET /api/v1/membership/recommend-card → Router → MembershipCardService → ScheduleService / MembershipCardRepository → PostgreSQL` |
| Router 薄层 | PASS | `router.py:260-276` 无业务判断、无 ORM 查询、无 SQL |
| 跨模块复用 | PASS | 仅调用 `ScheduleService.get_schedule_by_id`（`service.py:1066-1070`）；未访问 schedule Repository/表 |
| 只读事务 | PASS | 无 `commit/flush/with_for_update`；C-9 验证卡与流水零变化 |
| 租户隔离 | PASS | 租户与学员均来自 `get_current_user`（`router.py:271-272`）；排期租户感知查询 + 防御性 `schedule.tenant_id != tenant_id`（`service.py:1068-1070`）；卡查询显式 tenant |
| 权限 | PASS | 学员读本人数据，无需管理 RBAC；无越权参数入口 |
| 数据最小化 | PASS | 复用 `MembershipCardResponse`，未新增卡字段；仅返回登录者本人卡（含既有 `student_phone` 字段，非新增泄露面） |
| 契约 | PASS（有债务） | OpenAPI 产物与实现一致（V6），路径/参数真实存在；响应未 Pydantic 建模（M-1 / D-F6.6-1） |
| 前端请求层 | PASS | 复用 `apps/miniapp/src/api/index.ts` 既有 `request`（`624-628`），未新增第三套请求层 |
| 无本地重复规则 | PASS（有残留） | 本地可用性/排序规则已删除；残留未引用死代码（M-2） |
| AI / MCP | N/A | 本 Feature 不涉及 AI/MCP |
| 数据库 | PASS | 无迁移、无索引变更、无写库 |

### 4.2 对账结论

- `implementation-report.md`、`static-verification.md`、`runtime-test-report.md` 的关键数字（18/9/27/29、81 路径、type-check/build PASS）经本 Review 抽样复跑后一致；未发现报告夸大。
- 发现的文档与代码差异仅两处：user-flow §4 的“错误态”表述 vs 前端实现（M-4）、requirement §7 的 `msg` 示例 vs 统一信封（M-5）。均以真实代码为准，不影响功能正确性。
- UNKNOWN：① 500 分支未构造确定性触发；② 无 git diff 权限，工作区历史改动与白名单的边界仅能通过代码检查确认；③ 真机交互待 Stage 11。

## 5. Risk & Tech Debt

### 5.1 已接受的风险（非债务，按冻结决策）

| # | 风险 | 说明 |
|---|------|------|
| R-1 | 期卡区间冲突未在推荐阶段预校验 | K4 明确冻结；`validate_period_card_booking` 仍在下单时校验，推荐卡可能在下单时因区间冲突被拒 |
| R-2 | 推荐后卡状态并发变化 | 只读推荐不锁定卡；`create_booking` 的行锁与状态重检是最终权威 |
| R-3 | 排期容量/状态未在推荐中校验 | 不在 R-3~R-7 范围；下单仍由 `create_booking` 校验 |
| R-4 | 推荐响应复用 `MembershipCardResponse`，含本人 `student_phone/student_nickname` | 与 `my-cards` 既有契约一致，仅本人数据；若后续做字段最小化应两端统一评估 |

### 5.2 技术债登记

| 编号 | 内容 | 严重度 | 建议 |
|------|------|--------|------|
| D-F6.6-1 | `recommend-card` 使用 `response_model=dict`，OpenAPI 200 为泛型对象，生成类型无法表达响应字段 | Minor | 后续以 Pydantic `CardRecommendationResponse`（`available_cards: list[MembershipCardResponse]`）替换 `dict`，与 `my-cards` 一并治理 |
| D-F6.6-2 | `booking-confirm/index.vue` 残留 `getStatusBadgeClass`（引用已删除的 `unavailableReason`）与 `getCardIcon` 死代码 | Minor | **已在本次 Feature 内删除**，已关闭 |
| D-F6.6-3 | D6 排序以 `remaining_credits is None` 识别期卡/无限卡，依赖发放数据 `total_credits=NULL` | Minor | 在发放侧按期卡类型强制 `total_credits=None`，或排序键显式结合 `card_type` |
| D-F6.6-4 | 推荐请求失败与“无可用卡”共用空态渲染，未进入独立错误态 | Minor | 增加 `loadError` 状态，错误时隐藏选卡区或展示重试，不显示“暂无可用会员卡” |
| D-F6.6-5 | requirement 示例信封文案（`msg=success`）与统一 `success()`（`msg=ok` + `request_id`）不一致 | Minor（文档） | **已在本 Feature 内对齐统一信封**（`msg=ok` + `request_id`），已关闭 |

## 6. Conclusion

**READY_FOR_ACCEPTANCE**

- Blocker：0；Major：0；Minor：5（均为非阻断技术债或文档一致性问题，已登记 `D-F6.6-1` ~ `D-F6.6-5`）。
- A/B/C/D/E 全部 PASS；F-1~F-3 为 PARTIAL，待 Stage 11 用户人工验收。
- 核心判定已由真实代码 + 本次复跑证据确认：只读推荐链路、租户/本人卡隔离、`is_bookable_card` 行为保持、D6 排序与冻结排序键、无卡空态四字段、前端删除本地规则且未新增请求层。
- 建议进入 Stage 11 人工验收；Stage 12 Close 时将 §5.2 技术债写入 Backlog 附录，不在本 Feature 内顺手修复。
