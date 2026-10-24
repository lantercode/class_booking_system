# F2.3 — Review

> 日期：2026-09-28 ｜ 审查人：backend-engineer（自审 + 规则清单）

## Scope

- 变更严格限于 Feature 定义：`booking/service.py` 的 `check_in_booking` / `complete_booking` 两处（`get_by_id` → `get_by_id_for_update` + 变量名 + 注释）+ 新增测试 `test_checkin_complete_lock.py`。
- `create_booking` / `cancel_booking` / `cancel_booking_by_schedule` / `get_booking_by_id` / `list_bookings` 等其他方法**未动**。
- Router / Repository / models / schemas / OpenAPI / 前端 / MCP **均未改动**。
- 未引入新依赖、未改 DB 结构、未改 OpenAPI 路径/方法/请求体/响应模型。

## Architecture

- Router → Service → Repository 分层合规：Service 调 `repo.get_by_id_for_update`（行锁封装在 Repository，[repository.py:202-224](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/repository.py#L202-224)），不裸用 `with_for_update`、不裸 SQL。
- 事务边界在 Service：`db.commit()` 仍在 Service（[service.py:299](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L299) / [service.py:328](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L328)）；锁随 AsyncSession 在 commit 后释放。
- 与既有 `_do_cancel_booking` 锁模式同构（[service.py:213-219](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/service.py#L213-219)），并发安全模型统一、可审计。

## Code

- `check_in_booking`：开头 `get_by_id_for_update` → 拿锁后重检 `status == BOOKED` → 写 `CHECKED_IN` + `checked_in_at`。逻辑等价于"拿锁后读取即为重检"（FOR UPDATE 保证读到最新已提交值）。
- `complete_booking`：同模式，重检 `status in (BOOKED, CHECKED_IN)` → 写 `COMPLETED`。
- 变量名 `booking` → `locked_booking`，自文档化"后续操作均作用于锁定对象"，与 cancel 命名一致。
- 未改 status 分支条件，未改返回值，未改 Service 签名 → 对调用方透明。

## Security

- 端点 `@require_permissions("booking:manage")` 原样保留（Router 未动）；身份 `current_user = Depends(get_current_user)` 不变。
- 租户隔离：`get_by_id_for_update` 已含 `tenant_id` 过滤 → 跨租户 booking_id 返回 None → 404（不泄露存在性）。
- 不存在 booking_id → 404「预约不存在」（测试 `test_check_in_nonexistent_returns_404` 验证）。
- 失败响应符合统一信封 `{code:400, msg:"...", data:null}`，不回显 traceback（并发测试断言 `"Traceback" not in msg`）。

## Transaction / Concurrency

- **核心修复**：消除 `check_in_booking` / `complete_booking` 的 TOCTOU 竞态。
  - 修复前：两并发请求同时读到目标 status → 双签到 / 双完成。
  - 修复后：FOR UPDATE 行锁序列化 → 一成一败，DB 终态正确。
- 行锁按主键 `bookings.id` 命中（已有主键索引），不锁表；不同 booking 间无锁竞争。
- 不用 `skip_locked`：写操作排队序列化语义正确（第二个请求应看到前一个的提交结果并据此拒绝），与 cancel 既有约定一致。
- 锁生命周期由同一 AsyncSession 管理，commit 后释放，无锁泄漏。

## Regression

- `test_booking_ownership.py`（10/10）+ `test_auth_api.py`（25/25）：**35/35 通过** → AC-7 满足。
- 预约归属、JWT 双 token、黑名单、refresh、RBAC 行为未受影响。
- 本 Feature 仅替换取 booking 的 Repository 方法，未改 Service 签名 / 端点契约 / 状态机分支 → 回归零风险。

## Acceptance

- AC-1 / AC-2（并发只成一）：`test_concurrent_check_in_only_one_succeeds` / `test_concurrent_complete_only_one_succeeds` 通过（codes==[200,400]，DB 终态正确）。
- AC-3 / AC-4（正常单操作）：`test_single_check_in_ok` / `test_single_complete_ok` 通过。
- AC-5 / AC-6（重复操作失败）：`test_check_in_already_checked_in_fails` / `test_complete_already_completed_fails` 通过。
- AC-7（回归）：35/35 通过。
- AC-8（分层合规）：静态 grep 验证 Service 调 `repo.get_by_id_for_update`、无裸 `with_for_update`、`db.commit()` 在 Service（详见 [static-verification.md](./static-verification.md)）。

## 遗留事项（不阻塞）

1. `check_in` / `complete` 端点目前仅 `booking:manage` 权限校验，未做"教师只能对自己排期下的预约签到/完成"的归属校验——属另一 Feature 范围（F2.2 已在 review 中提出写操作归属校验债务项）。本 Feature 仅解决并发安全，不扩大范围。
2. `complete_booking` 当前未触发课时扣减/积分发放（仅状态流转），故"双完成"的下游副作用当前仅限状态冗余；未来若 `complete` 接入扣次，本 Feature 的行锁已是必要前置保障。
3. 测试并发用例依赖 live_server 真实 Uvicorn 进程复现 PG 行锁竞争；若未来测试基础设施切回 ASGITransport in-process，需重新评估并发测试可信度（当前架构无需调整）。

## 结论

**READY_FOR_ACCEPTANCE**
