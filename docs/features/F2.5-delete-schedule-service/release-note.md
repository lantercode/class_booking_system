# F2.5 — Release Note

## delete_schedule 下沉到 Service（2026-09-28）

### 重构变更（内部技术债偿还，无用户可感知行为变化）

- `DELETE /api/v1/schedules/{schedule_id}`（硬删除排期）的业务逻辑与数据访问由 Router 层下沉至 `ScheduleService.delete_schedule(db, schedule_id)`：
  - 新增 Service 方法统一承载：存在性校验（404"排期不存在"）、业务规则（待上课 NORMAL 且 `booked_count > 0` → 400"该排期仍有学员预约，请先取消排期后再删除"）、关联 booking 级联硬删、排期硬删（两步同一事务，由 Repository 统一 commit / 异常 rollback）。
  - Router 端点瘦身为薄层：参数提取 + 依赖注入 + 调用 Service + 返回信封；移除仅此处使用的 `ScheduleStatus` import。
- 消除三类分层违规：Router 直调本模块 Repository、业务规则写在 Router、Router 直调他模块（booking）Repository。单删路径与既有 `batch_delete_schedules` Service 路径同构。

### 兼容性

- API 契约零变化：路径 `DELETE /api/v1/schedules/{schedule_id}`、HTTP 方法、权限点 `schedule:delete`、`response_model=dict`、成功信封 `{code:0, msg:"排期删除成功", data:null}`、错误信封（400 / 404 文案与状态码）、401 / 403 行为全部不变。
- 删除的数据语义不变：仍为先删该排期下任意状态 booking、再硬删 schedule 的同事务操作。
- 无需 `pnpm gen:types`；前端 4 端影响评估：
  - admin-web：消费该端点，契约不变 → **不涉及**
  - teacher-web：角色权限与契约不变 → **不涉及**
  - student-web：学员无 `schedule:delete`（403），不消费 → **不涉及**
  - miniapp：同上 → **不涉及**
- MCP / AI：无 `delete_schedule` Tool，不受影响。

### 运维与数据

- 无数据库结构变更，无需 migration（删除走主键与 `idx_bookings_schedule` 既有索引）。
- 无配置 / 环境变量 / Redis key 变更。
- 无新增依赖。

### 测试

- 新增 `tests/integration/test_delete_schedule_service.py`：9/9 通过（Service 直调 5 + HTTP 端到端 4；覆盖级联硬删 DB 断言、404、NORMAL+预约 400 且 DB 无变更、student 403、FINISHED 历史 booking 级联等）。
- 回归 56/56 通过：F2.4 cancel_schedule 回滚 12、F2.3 签到/完成行锁 9、F2.2 预约归属 10、认证 25。合计 65 passed。

### 已知遗留（后续处理）

- **D-F2.5-1**：schedule Service 三处（`cancel_schedule` / `batch_delete_schedules` / `delete_schedule`）直调 `BookingRepository`。建议后续由 booking 模块提供 Service 入口收口跨模块调用，并统一函数内 import 风格。
- 排期删除为物理硬删且级联清除任意状态历史 booking（迁移前既有行为，本次原样保留）；是否需要删除前归档 / 软删，建议另立 Feature 评估。
