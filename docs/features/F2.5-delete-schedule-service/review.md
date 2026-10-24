# F2.5 — Review

> 日期：2026-09-28 ｜ 审查人：backend-engineer（自审 + `.trae/rules` 规则清单）

## Scope

- 变更严格限于 Feature 定义：
  1. `schedule/service.py` **仅追加** `delete_schedule` 一个方法（L332-364），未改任何既有方法；
  2. `schedule/router.py` 两处定点改动（移除唯一使用点的 `ScheduleStatus` 顶部 import；删除端点函数体替换为 1 行 Service 调用）；
  3. 新增测试 `test_delete_schedule_service.py`（9 用例）。
- booking 模块 / schedule repository / models / schemas / `batch_delete_schedules` / 前端 / MCP / DB 结构 / migration **均未改动**。
- 工作区存在前序 Feature（F2.4 等）未提交改动（repository.py / scheduler.py / service.py cancel 区域），已通过 diff 逐段核对确认未被本 Feature 触碰；未执行任何 git commit / stash / reset。
- 未引入新依赖、无配置变更。

## Architecture

- **核心目标达成**：Router → Service → Repository 调用链恢复。重构后 router.py grep `BookingRepository|.repo.|get_by_id|hard_delete|delete_by_schedule_id|ScheduleStatus|NotFoundException|BusinessException` **0 匹配**（AC-8）。
- Router 只剩 layering.md 允许的四项职责：Path 参数声明 / 依赖注入 / 调 Service / 返回信封。
- Service 承载业务规则（存在性、NORMAL+booked_count 拦截）与事务边界；数据访问全部经既有 Repository 方法（`self.repo.get_by_id` / `BookingRepository.delete_by_schedule_id` / `self.repo.delete`），无裸 SQL、无 `db.execute(delete(...))` 直写。
- 单删路径与同 Service `batch_delete_schedules` 同构（同校验、同删除顺序、同 auto_commit 提交点）。
- 已知历史模式（非本 Feature 引入）：schedule Service 直调 `BookingRepository`，严格按 layering「跨模块只调对方 Service」应由 booking 模块提供 Service 入口收口；与 `cancel_schedule` / `batch_delete_schedules` 三处现状一致，登记为技术债 D-F2.5-1，未在本小范围重构中扩大改动面。

## Code

- 逻辑迁移逐字等价：条件表达式 `schedule.status == ScheduleStatus.NORMAL.value and schedule.booked_count > 0`、错误文案"该排期仍有学员预约，请先取消排期后再删除"、`code=400`、"排期不存在"、`hard_delete=True` 全部保持；删除顺序（booking → schedule）与提交时机（`repo.delete` 内 auto_commit）不变。
- 函数内 import `BookingRepository` 与同文件两既有方法风格一致；未新增顶部 import（异常类 / 枚举在 service 顶部均已存在）。
- docstring 说明业务规则与事务语义（统一 commit、异常 rollback）；关键步骤保留中文注释。
- 返回 `{"schedule_id": schedule_id}` 与 Service 其他写方法返回 dict 的风格统一；router 成功 msg 仍为"排期删除成功"（严格相等测试锁定）。

## Security

- 认证：`Depends(get_current_user)` 保留。
- 授权：`@require_permissions("schedule:delete")` 保留；student 删除 → 403 有运行时用例验证，且 schedule 未被删除（证明装饰器拦截先于业务）。
- 租户隔离：读取经 TenantAwareRepository ORM 事件自动注入；`delete_by_schedule_id` 按 ContextVar 追加 tenant 条件；Service 不接收、不信任任何调用方传入的 tenant_id；跨租户 schedule_id 与真不存在统一返回 404"排期不存在"，不泄露存在性。
- 输出安全：错误经全局异常处理器返回统一信封；全部 HTTP 用例断言响应不含 "Traceback"；无 SQL / 主机名 / 堆栈回显。

## Transaction / Concurrency

- booking DELETE（不 commit）+ schedule 硬删位于同一 AsyncSession、同一事务，由 `TenantAwareRepository.delete(auto_commit=True)` 一次 commit；schedule 删除若失败（含 RESTRICT 外键残留），其 except 中 `db.rollback()` 连同年 booking DELETE 一并回滚，不存在半删除状态。
- 拦截分支（400）先于任何写语句执行，失败路径无写入、无需回滚业务数据。
- 无新增并发原语；无新增 `with_for_update`（删除操作本身不需要，且既有行为如此，重构不改变面）。

## Regression

- 新增 9/9 通过；回归 56/56 通过（F2.4 12 + F2.3 9 + F2.2 10 + auth 25）。
- OpenAPI 契约（路径 / 方法 / 权限 / response_model / 成功与错误信封）零变化 → 前端 4 端（admin / student / teacher / miniapp）与 api-types 均无影响，无需 `pnpm gen:types`。

## Acceptance

- AC-1 ~ AC-6：对应 9 个运行时用例全部 PASSED（见 [runtime-test-report.md](./runtime-test-report.md) 第 3~4 节）。
- AC-7：回归 56/56 PASSED。
- AC-8：py_compile 通过 + router 违规符号 grep 0 匹配（见 [static-verification.md](./static-verification.md)）。

## 遗留事项（不阻塞）

1. **D-F2.5-1**：schedule Service（`cancel_schedule` / `batch_delete_schedules` / 新增 `delete_schedule`）直接调用 `BookingRepository`。严格按分层规则，跨模块应调用 booking 模块的 Service 方法。建议后续小 Feature 在 booking Service 增加 `delete_by_schedule(db, schedule_id)` 入口并统一替换三处，同时评估函数内 import 是否可上提。
2. 删除排期为物理硬删且级联清除任意状态 booking（含 CANCELLED / COMPLETED 历史记录），不可恢复——这是**迁移前既有行为**，本 Feature 原样保留；是否需要"删除前归档 / 软删"属产品决策，建议另立 Feature 评估。

## 结论

**READY_FOR_ACCEPTANCE**
