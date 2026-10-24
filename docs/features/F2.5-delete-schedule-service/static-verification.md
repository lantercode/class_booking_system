# F2.5 — 静态验证报告

> 日期：2026-09-28

## 1. py_compile

实际执行：

```bash
$ cd apps/api && PYTHONPATH=src .venv/bin/python -m py_compile \
    src/app/modules/schedule/service.py \
    src/app/modules/schedule/router.py \
    tests/integration/test_delete_schedule_service.py \
  && echo "COMPILE_OK_ALL"
COMPILE_OK_ALL
```

三个文件全部编译通过，无语法错误。

## 2. Router 分层违规清零（AC-8 核心证据）

实际执行：

```bash
$ grep -nE "BookingRepository|\.repo\.|get_by_id|hard_delete|delete_by_schedule_id" \
    apps/api/src/app/modules/schedule/router.py
# → No matches found
```

重构前 router.py 中 4 类违规符号（`BookingRepository` / `schedule_service.repo.*` / `get_by_id` / `hard_delete` / `delete_by_schedule_id`）在重构后 **0 匹配**。

再核查业务异常与状态枚举也已从 router 移除：

```bash
$ grep -nE "BookingRepository|repo\.|ScheduleStatus|NotFoundException|BusinessException" \
    apps/api/src/app/modules/schedule/router.py
# → No matches found
```

重构后端点全貌（router.py L197-212）：

```python
@router.delete(
    "/{schedule_id}",
    response_model=dict,
    summary="删除排期",
    description="硬删除排期（需 schedule:delete 权限）",
)
@require_permissions("schedule:delete")
async def delete_schedule(
    schedule_id: int = Path(..., description="排期ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """删除排期"""
    await schedule_service.delete_schedule(db, schedule_id)
    return success(msg="排期删除成功")
```

- Router 仅做：Path 参数声明 / 依赖注入（db、current_user）/ 调 Service / 返回信封——完全符合 layering.md 对 Router 层的允许项。
- 装饰器、路径、HTTP 方法、response_model、summary、description、Docstring、成功 msg 全部保留。

> 说明：`batch_delete_schedules` 端点中的 `schedule_ids = data.get(...)` 是请求体字段提取（Router 允许项），对 Service 的调用为 `await schedule_service.batch_delete_schedules(...)`，不命中上述任何违规模式；本 Feature 不改批删路径。

## 3. Service 落点核查（grep）

```bash
$ grep -nE "async def delete_schedule|delete_by_schedule_id|hard_delete=True|该排期仍有学员预约|排期不存在" \
    apps/api/src/app/modules/schedule/service.py
```

关键行（含同文件其他方法的同名既有调用，一并列出以证明同构）：

| 行 | 内容 | 归属 | 结论 |
|----|------|------|------|
| L332 | `async def delete_schedule(self, db, schedule_id) -> dict[str, Any]` | F2.5 新增 | ✅ 签名与契约一致 |
| L349 | `raise NotFoundException("排期不存在")` | F2.5 新增 | ✅ 存在性校验在 Service |
| L353 | `raise BusinessException("该排期仍有学员预约，请先取消排期后再删除", code=400)` | F2.5 新增 | ✅ 业务规则在 Service，文案 / code 与重构前逐字一致 |
| L359 | `await booking_repo.delete_by_schedule_id(db, schedule_id)` | F2.5 新增 | ✅ 复用既有 Repository 方法（不裸 SQL） |
| L361 | `await self.repo.delete(db, schedule_id, hard_delete=True)` | F2.5 新增 | ✅ 硬删 + auto_commit 统一提交 |
| L407 / L409 | 同名调用（`delete_by_schedule_id` / `repo.delete(hard_delete=True)`） | 既有 `batch_delete_schedules` | ✅ 单删与批删同构的对照证据 |

## 4. 分层合规检查

| 规则（.trae/rules） | 检查 | 结果 |
|------|------|------|
| Router 不做业务判断 / 不操作 ORM（layering.md） | grep 第 2 节 0 匹配；端点体仅 2 行 | ✅ |
| 标准调用链 Router → Service → Repository → DB | router → `schedule_service.delete_schedule` → `self.repo.*` / `BookingRepository.delete_by_schedule_id` | ✅ |
| Repository 承载数据访问、不做业务决策 | 未改 repository；规则判断全部位于 Service | ✅ |
| 租户隔离（tenant-isolation.md） | `ScheduleRepository` 继承 TenantAwareRepository（get_by_id 自动注入租户条件）；`delete_by_schedule_id` 内按 `get_tenant_id()` 追加租户过滤；Service 不接收请求体 tenant_id | ✅ |
| RBAC（authorization.md） | `@require_permissions("schedule:delete")` 原样保留；student 403 由运行时用例验证 | ✅ |
| 认证（authentication.md） | `current_user: dict = Depends(get_current_user)` 原样保留 | ✅ |
| 统一信封 / 不泄露（contracts.md） | 成功 / 400 / 404 响应结构与文案不变；HTTP 用例断言响应无 "Traceback" | ✅ |
| AI 边界（ai/*.md） | 不涉及 MCP；无 `delete_schedule` Tool；未新增网络入口 | ✅ |
| 跨模块边界 | schedule Service 内调用 booking Repository 与 `cancel_schedule` / `batch_delete_schedules` 现状同构（历史模式）；未扩散新的跨模块破例；"收口为 booking Service 方法"已登记技术债 | ⚠️→📝 既有模式，记账 |

## 5. Diff 审查（改动面白名单）

本 Feature 实际触碰（与 `git diff` 逐段核对）：

| 文件 | 本 Feature 实际变化 | 审查结论 |
|------|------|---------|
| `apps/api/src/app/modules/schedule/service.py` | 仅**新增** `delete_schedule` 方法（git diff 中为连续 `+` 块，34 行含 docstring / 注释）；未修改任何既有行 | 追加式改动，行为为新入口 |
| `apps/api/src/app/modules/schedule/router.py` | 2 处：删除顶部 `ScheduleStatus` import；删除端点函数体替换为 1 行 Service 调用（`21 +-,` 统计即此两处） | 契约零变化 |
| `apps/api/tests/integration/test_delete_schedule_service.py` | 新建 9 用例 | 仅测试 |

工作区另有 `schedule/repository.py`、`schedule/scheduler.py` 以及 service.py 中 `cancel_schedule` 区域的 diff，经核对均为**前序 Feature（F2.4 等）未提交的既有改动**，本 Feature 未触碰（实施前后未对这些文件发起编辑）。未执行 `git add` / `commit` / `stash` 等任何可能影响他人改动的操作。

booking 模块 / models / schemas / OpenAPI / 前端 4 端 / MCP / migration **均未改动**。

## 6. 契约一致性

| 契约项 | 重构前 | 重构后 | 一致 |
|--------|--------|--------|------|
| 路径 / 方法 | `DELETE /schedules/{schedule_id}` | 不变 | ✅ |
| 权限 | `schedule:delete` | 不变 | ✅ |
| response_model | `dict` | 不变 | ✅ |
| 成功响应 | `{code:0, msg:"排期删除成功", data:null}` | 不变（router 同一行 `success(...)`） | ✅ |
| 400 | `{code:400, msg:"该排期仍有学员预约，请先取消排期后再删除"}` | 异常类 / code / 文案逐字一致 | ✅ |
| 404 | `{code:404, msg:"排期不存在"}` | 一致 | ✅ |
| 403 / 401 | RBAC / 认证装饰器既有行为 | 装饰器未动 | ✅ |
| 删除语义 | 先全量删 booking（任意状态）→ 硬删 schedule，同事务 | 同一 Repository 方法、同一顺序、同一 session | ✅ |

→ 无需重新生成 `packages/api-types`；admin-web / teacher-web / student-web / miniapp 四端均无影响。
