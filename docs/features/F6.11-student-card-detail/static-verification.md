# F6.11 静态验证

> 日期：2026-10-25。覆盖 A 静态/构建、A-5 契约、A-6 分层相关项。

## 1. 后端

| 命令 | 结果 |
|------|------|
| `python -m py_compile`（service/repository/router + 新增测试） | ✅ 4 文件 OK |
| `ruff check`（membership 模块 + 新增测试） | ✅ All checks passed |
| `pytest tests/test_membership_requester_scope.py` | ✅ 14 passed |
| `pytest tests/test_membership_affected_bookings.py` | ✅ 24 passed |
| `pytest tests/test_card_recommendation.py` | ✅ 9 passed |

> 14 + 24 + 9 全通过；任务记录另记一次「38 passed」复跑（14 + 24 同批执行）。

## 2. 前端构建

| 命令 | 结果 |
|------|------|
| `pnpm --filter dance-miniapp build:mp-weixin`（`vue-tsc --noEmit && uni build -p mp-weixin`） | ✅ 类型检查通过 + `DONE Build complete.` |
| `pnpm --filter student-web build`（`vue-tsc -b && vite build`） | ✅ `✓ built in 4.15s` |
| student-web 分包产物 | ✅ 含 `membership` 列表/详情/transactions 分包 |

未执行：`packages/api-client` 独立构建（本期未改该包）；admin-web / teacher-web 构建（本期未改）。

## 3. 契约对齐（A-5 / D-*）

| # | 核对项 | 结论 |
|---|--------|------|
| 1 | 端点存在性 | 三端点均在 `membership/router.py` 真实存在，未调用虚构端点 |
| 2 | query 一致 | 详情用 Path `card_id`；列表 `page/page_size/student_id/...`；流水 `page/page_size/card_id/operation_type` |
| 3 | DTO 字段 | 卡消费字段 ⊆ `MembershipCardResponse`；流水消费字段 ⊆ `MembershipCardTransactionResponse` |
| 4 | 枚举 | 0/1/2/3/6 与 `CardStatus` 一致；7 个流水类型与 `TransactionType` 一致 |
| 5 | OpenAPI | 无 diff |
| 6 | 生成类型 | `packages/api-types` 未重生成 |
| 7 | api-client | 未改；`MembershipCard` 缺 `cancelled_*`，详情页局部扩展（D-F6.11-1） |

## 4. 分层合规（A-6）

| 层 | 结论 | 证据 |
|----|------|------|
| Router | ✅ 只做参数解析、依赖注入、调用 Service、信封返回 | `list_cards` 仅解析 `status` 逗号串并透传；无归属 if/else |
| Service | ✅ 归属判断、状态语义、空页处理均在 Service | 3 个 requester 方法 |
| Repository | ✅ 继承 `TenantAwareRepository`；`card_ids` 为纯增量过滤 | `MembershipCardTransactionRepository` |
| 前端 | ✅ 仅经既有请求层；未复制后端归属/状态机作为最终校验 | miniapp `membershipApi`；Web `membershipCardApi` |

## 5. 四态与安全审查

| # | 项 | 结论 |
|---|----|------|
| 1 | miniapp 详情 | loading / error / data；空以 404 文案承担 |
| 2 | miniapp 流水 | loading / empty / error / data + loadingMore |
| 3 | student-web 列表/详情/流水 | loading / empty(或 404) / error / data |
| 4 | 错误回显 | 仅文案 + 后端 `msg`，无堆栈/SQL/内部 URL |
| 5 | 内部字段 | 页面未渲染 `operator_id` / `idempotency_key` / `public_id` |
| 6 | 租户 | 不信任前端 `tenant_id`；由 Middleware/ContextVar + Service 校验 |
| 7 | 鉴权开关 | 不依赖 `PERMISSION_CHECK_BYPASS`；`check_roles` fail-closed |
| 8 | 写操作 | 本期无新增写操作；激活/解冻仍走既有端点 |
