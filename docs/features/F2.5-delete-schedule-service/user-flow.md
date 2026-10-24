# F2.5 — delete_schedule 下沉到 Service · 用户流程

> 视角：管理员（持 `schedule:delete` 权限）通过 HTTP API 硬删除排期。
> 认证链路：端点要求 `Authorization: Bearer <token>` + `x-tenant-slug` 头。`current_user` 由 `Depends(get_current_user)` 注入；`@require_permissions("schedule:delete")` 校验权限。
> 本 Feature 为纯分层重构：以下业务流程在重构前后**完全一致**，仅代码所在层从 Router 移到 Service。

---

## 流程 1：删除已取消（或无预约）排期成功

1. 管理员调 `DELETE /schedules/{schedule_id}`，无请求体。
2. Router（重构后薄层）：Path 参数 `schedule_id: int` 经 FastAPI 校验；`get_current_user` 注入身份；`@require_permissions("schedule:delete")` 校验通过；调 `await schedule_service.delete_schedule(db, schedule_id)`。
3. Service `delete_schedule`：
   - `schedule = await self.repo.get_by_id(db, schedule_id)`（`TenantAwareRepository` + ORM 事件自动注入 `WHERE tenant_id=当前租户`；不存在 / 跨租户 → None → 404"排期不存在"，不泄露存在性）。
   - 业务规则：`if schedule.status == ScheduleStatus.NORMAL.value and schedule.booked_count > 0:` → 400"该排期仍有学员预约，请先取消排期后再删除"。即仅**待上课且仍有预约**的排期被拦截；CANCELLED / FINISHED / NORMAL 但 booked_count=0 均放行。
   - `booking_repo = BookingRepository()`；`await booking_repo.delete_by_schedule_id(db, schedule_id)`：硬删该排期下**任意状态**的全部 booking（`DELETE FROM bookings WHERE schedule_id=:id [AND tenant_id=:tid]`），执行但不 commit。先删 booking 是因为 `bookings.schedule_id` 外键 `ON DELETE RESTRICT`。
   - `await self.repo.delete(db, schedule_id, hard_delete=True)`：硬删 schedule（主键 DELETE），`auto_commit=True` 在同一 AsyncSession 上 `commit()`——上一步 booking 删除与本步 schedule 删除在同一事务一次性提交。
   - `logger.info` 记录；返回 `{"schedule_id": schedule_id}`。
4. Router：`return success(msg="排期删除成功")` → 信封 `{code:0, msg:"排期删除成功", data:null}`。

## 流程 2：待上课排期仍有预约 → 业务错误（单请求，无写入）

1. 管理员调 `DELETE /schedules/{schedule_id}`，目标排期 status=NORMAL、booked_count=1（存在 BOOKED booking）。
2. Router → Service。
3. Service：`get_by_id` 命中；规则判断 `NORMAL and booked_count > 0` 成立 → raise `BusinessException("该排期仍有学员预约，请先取消排期后再删除", code=400)`。
4. 此分支发生在任何 DELETE 语句之前 → 无写入、无 commit；AsyncSession 由 FastAPI 依赖清理时被动 rollback。
5. 全局异常处理器 → `400 {code:400, msg:"该排期仍有学员预约，请先取消排期后再删除", data:null}`（无 Traceback）。
6. 用户须先调 `POST /schedules/{id}/cancel`（F2.4：取消排期并处理学员预约 / 回补课时），待排期 CANCELLED 后再删除。

## 流程 3：排期不存在 / 跨租户

1. 管理员调 `DELETE /schedules/999999999`（或传入其他租户的 schedule_id）。
2. Service：`get_by_id` 经租户过滤返回 None → raise `NotFoundException("排期不存在")`。
3. 全局异常处理器 → `404 {code:404, msg:"排期不存在", data:null}`。对跨租户请求与真不存在返回相同文案，不泄露资源存在性。

## 流程 4：鉴权失败

- 未认证（无 / 坏 Token）→ 401（由 `get_current_user` 统一处理）。
- 已认证但角色无 `schedule:delete`（如 student 仅持 `booking:view`）→ RBAC 装饰器在进入端点函数体前拦截 → 403；Service 不被调用，DB 无任何动作。

## 流程 5：删除顺序与事务（为什么先删 booking）

```
bookings.schedule_id  ──FK ON DELETE RESTRICT──▶  course_schedules.id
```

- 若先硬删 schedule：PG 因 RESTRICT 外键拒绝（该排期仍有任意 booking 行，包括 CANCELLED / COMPLETED 历史行）→ 删除失败。
- 因此固定顺序：`delete_by_schedule_id`（先清空 booking）→ `repo.delete(hard_delete=True)`（再删 schedule）→ 统一 commit。
- 任一步失败：`TenantAwareRepository.delete` 的 except 执行 `db.rollback()` 并 re-raise → 两步删除全部回滚，不会出现"booking 没了但 schedule 还在"或反之的中间态。

## 流程 6：重构后的调用链（对照 layering.md）

```
HTTP DELETE /schedules/{id}                 [认证 + @require_permissions("schedule:delete")]
  → schedule.router.delete_schedule         [薄层：Path 校验 / 注入 / 调 Service / 返回信封]
    → schedule.service.delete_schedule       [业务规则 + 事务边界]
      → schedule.repo.get_by_id              [读，含租户过滤]
      → booking.repo.delete_by_schedule_id   [删关联 booking，不 commit]
      → schedule.repo.delete(hard_delete=True) [删 schedule + 统一 commit/rollback]
    → 返回 {"schedule_id": id}
  → success(msg="排期删除成功")
```

- Router 不再出现 `repo.*`、`BookingRepository`、异常类业务判断。
- 单删路径与同 Service 的 `batch_delete_schedules` 使用相同的校验分支与删除顺序。
- 历史模式说明：schedule Service 内直调 `BookingRepository` 与 `batch_delete_schedules` / `cancel_schedule` 现状同构（函数内 import）；严格按"跨模块只调对方 Service"的规则，后续可由 booking 模块补一个 `delete_by_schedule` Service 入口统一收口，登记为技术债，不在本 Feature 范围。
