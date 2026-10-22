# F6.6 验收标准：多卡默认推荐策略

> 结果词表：PASS / FAIL / BLOCKED / UNKNOWN / NOT TESTED。禁止「基本通过」。

## A. 静态 / 构建

| # | 验收项 | 判定方式 | 预期 |
|---|--------|---------|------|
| A-1 | 分层合规 | Code review | Router 只做参数/依赖/调用 Service；无业务判断、无 SQL |
| A-2 | 跨模块调用 | Code review | membership 只调 `ScheduleService.get_schedule_by_id`，不直接查 schedule 表 |
| A-3 | 无租户绕过 | Code review | 复用 `card_repo.get_all_cards_by_student(student_id, tenant_id)`；无裸 SQL |
| A-4 | 无写操作/锁 | Code review | 推荐链路无 `commit/flush/FOR UPDATE` |
| A-5 | 判定单一来源 | Code review | `is_bookable_card` 与推荐共用同一判定函数 |
| A-6 | 契约 | OpenAPI diff | 新增 1 条 GET 路径；`my-cards` 无变化 |
| A-7 | 生成类型 | `pnpm gen:types` + `git diff` | 产物由命令生成，无手改 |
| A-8 | Python 语法 | `python3 -m py_compile` | 每个改动文件通过 |
| A-9 | Lint | `ruff check` | 无新增错误 |
| A-10 | 小程序构建 | `vue-tsc` / `pnpm build` | 通过（以实际脚本为准） |

## B. 单元测试（纯逻辑）

| # | 验收项 | 判定方式 | 预期 |
|---|--------|---------|------|
| B-1 | D6 排序：过期优先 | `test_card_recommendation.py` | `expire_at` 早者在前 |
| B-2 | `expire_at=NULL` 排在最后 | 同上 | 无限卡/未定期卡在末尾 |
| B-3 | 剩余次数少优先 | 同上 | 同到期次卡 `remaining 1` 在 `remaining 5` 前 |
| B-4 | 同分先发放 | 同上 | `created_at` 早者在前；相同则 `id` 小者在前 |
| B-5 | 期卡/无限卡无剩余语义 | 同上 | 同到期时排在同到期次卡之后 |
| B-6 | 排除规则 | 同上 | 过期/冻结/作废/未生效/次卡用尽/课程类型不适用/指定课程不匹配 均排除 |
| B-7 | 期卡 PENDING 且 `valid_from IS NULL` | 同上 | 判定可用（D9） |
| B-8 | `PENDING` 已定生效日 | 同上 | 判定不可用 |
| B-9 | 按排期日判定有效期 | 同上 | `expire_at` 当天可用；次日不可用 |
| B-10 | 空态文案聚合 | 同上 | 无卡 →「您还没有会员卡」；有卡全排除 → 含原因 |

## C. 集成测试（HTTP + PostgreSQL）

| # | 验收项 | 判定方式 | 预期 |
|---|--------|---------|------|
| C-1 | 正常返回 | `GET /membership/recommend-card?schedule_id=` | 200，`code=0`，`recommended_card_id=available_cards[0].id` |
| C-2 | 排序稳定 | 固定卡集合 | 顺序符合 D6，重复请求一致 |
| C-3 | 排除规则端到端 | 造过期/冻结/作废/未生效/用尽/类型不匹配卡 | 均不在 `available_cards` |
| C-4 | 无可用卡 | 全部排除 | 200，`recommended_card_id=null`，`available_cards=[]`，`message` 非空 |
| C-5 | 学员无卡 | 无卡数据 | 200，`message="您还没有会员卡"` |
| C-6 | 未认证 | 无 Token | 401 |
| C-7 | 排期不存在 | 随机 id | 404 |
| C-8 | 跨租户 | 其他租户排期 id | 404，不泄露排期信息 |
| C-9 | 只读性 | 调用前后对比卡/流水 | 无数据变化 |
| C-10 | 回归 | `test_membership_period_card_lifecycle.py`、`test_period_card_booking_validation.py`、`test_booking_card_authorization.py` | 全通过 |

## D. 前端行为

| # | 验收项 | 判定方式 | 预期 |
|---|--------|---------|------|
| D-1 | 默认选中 | 页面运行 / 代码 review | 等于 `recommended_card_id` |
| D-2 | 列表顺序 | 页面运行 | 与 `available_cards` 顺序一致 |
| D-3 | 手动换卡 | 页面运行 | 可切换，确认预约传新卡 id |
| D-4 | 空态与原因 | 无可用卡数据 | 卡片区直接展示后端 `message`，确认按钮禁用，不依赖选择器 |
| D-5 | 加载/错误态 | 断网 / 404 | Toast 提示，不渲染本地兜底推荐 |
| D-6 | 无重复规则 | Code review | 删除本地 `allCardsWithStatus` / `getDefaultSelectedCard` |
| D-7 | 未知卡类型 | 单测 + Code review | ACTIVE 但 `card_type` 非三类时排除，不误判可用 |

## E. 权限 / 租户 / 安全

| # | 验收项 | 判定方式 | 预期 |
|---|--------|---------|------|
| E-1 | 身份来源 | Code review + 集成测试 | 仅 `current_user`，请求体无身份参数 |
| E-2 | 他人卡不可读 | 集成测试（同租户两学员） | 只返回本人卡 |
| E-3 | 跨租户隔离 | 集成测试 | 404 / 空结果，无跨租户数据 |
| E-4 | 错误不泄露 | 集成测试 | 响应无 traceback/SQL/内部 URL |

## F. 人工验收

| # | 验收项 | 判定方式 |
|---|--------|---------|
| F-1 | 真机/开发者工具选卡流程 | 用户人工确认 |
| F-2 | 无可用卡空态文案可读 | 用户人工确认 |
| F-3 | 与 `create_booking` 判定一致性抽查 | 用户人工确认（选推荐卡下单成功；排除卡下单被拒） |
