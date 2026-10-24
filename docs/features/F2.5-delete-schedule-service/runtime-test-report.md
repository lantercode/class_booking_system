# F2.5 — 运行时测试报告

> 日期：2026-09-28
> 环境：本地开发机，FastAPI 测试服务器（127.0.0.1:8765，conftest 自动拉起的真实 Uvicorn 进程，独立线程 + 独立事件循环），PostgreSQL（Docker 共享开发库，预置种子租户 dance-school），Redis 可用。

## 1. 测试入口

```bash
# 主测试（F2.5）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_delete_schedule_service.py -v

# 回归（AC-7）
cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest \
  tests/integration/test_cancel_schedule_rollback.py \
  tests/integration/test_checkin_complete_lock.py \
  tests/integration/test_booking_ownership.py \
  tests/integration/test_auth_api.py -v
```

## 2. 结果摘要

| 套件 | 结果 |
|------|------|
| `test_delete_schedule_service.py`（F2.5 新增） | **9 passed**（1.66s，首轮即全绿） |
| `test_cancel_schedule_rollback.py`（回归） | **12 passed** |
| `test_checkin_complete_lock.py`（回归） | **9 passed** |
| `test_booking_ownership.py`（回归） | **10 passed** |
| `test_auth_api.py`（回归） | **25 passed** |
| **合计** | **65 passed, 4 warnings**（回归合计 13.14s） |

warnings 均为既有第三方库 deprecation（passlib `crypt`、uvicorn/websockets legacy、FastAPI `example`），与本 Feature 无关。无 failure / error / 重试。

## 3. 用例明细（test_delete_schedule_service.py，9/9 通过）

### 3.1 Service 直调路径（TestDeleteScheduleService，5/5）

| 用例 | 覆盖 AC | 验证点 | 结果 |
|------|---------|--------|------|
| `test_delete_cancelled_schedule_ok_cascades_bookings` | AC-1 | 1 CANCELLED schedule(booked_count=0) + 1 CANCELLED booking；直调 `delete_schedule` → 返回值严格等于 `{"schedule_id": id}`；新 session 双表断言：schedule 不存在、booking 不存在（硬删 + 级联） | PASSED |
| `test_delete_nonexistent_schedule_raises_not_found` | AC-2 | schedule_id=999999999 → raise `NotFoundException`，str 含"不存在" | PASSED |
| `test_delete_normal_schedule_with_bookings_raises_business_no_change` | AC-3 | 1 NORMAL schedule(booked_count=1) + 1 BOOKED booking → raise `BusinessException`，`code==400`，msg 含"仍有学员预约"+"先取消排期后再删除"；双表断言 schedule / booking 均仍存在（规则先于 DELETE，无写入） | PASSED |
| `test_delete_normal_schedule_without_bookings_ok` | 补充 | NORMAL 但 booked_count=0、无 booking 行 → 放行；返回 dict 正确；schedule 已硬删 | PASSED |
| `test_delete_finished_schedule_ok_cascades_bookings` | 补充 | FINISHED schedule + COMPLETED booking → 放行（拦截条件仅 NORMAL）；schedule 与历史 booking 均被硬删（`delete_by_schedule_id` 无状态过滤） | PASSED |

### 3.2 HTTP 端点路径（TestDeleteScheduleHTTP，4/4）

| 用例 | 覆盖 AC | 验证点 | 结果 |
|------|---------|--------|------|
| `test_http_delete_cancelled_schedule_ok` | AC-4 | super_admin token；`DELETE /schedules/{id}` → 200；`code==0`；`msg=="排期删除成功"`（严格相等）；body 无 Traceback；新 session 双表断言均不存在 | PASSED |
| `test_http_delete_schedule_forbidden_for_student` | AC-5 | seed student（仅 `booking:view`）→ 403；断言 schedule 仍存在（装饰器在 Service 之前拦截，零写入） | PASSED |
| `test_http_delete_nonexistent_returns_business_error` | AC-6 | `DELETE /schedules/999999999` → 404；`code==404`；msg 含"不存在"；body 无 Traceback | PASSED |
| `test_http_delete_normal_with_bookings_returns_400` | 补充 | NORMAL+booked_count=1 → 400；`code==400`；msg 双片段；body 无 Traceback；双表无变化 | PASSED |

## 4. 逐 AC 结论

| AC | 结论 | 证据 |
|----|------|------|
| AC-1 删除已取消排期成功 + booking 级联硬删 | ✅ | `test_delete_cancelled_schedule_ok_cascades_bookings`（返回值 + 双表 `_exists is False`） |
| AC-2 不存在 → NotFoundException | ✅ | `test_delete_nonexistent_schedule_raises_not_found`；HTTP 侧由 AC-6 端到端复验 |
| AC-3 NORMAL+booked_count>0 → 400 + DB 无变更 | ✅ | `test_delete_normal_schedule_with_bookings_raises_business_no_change`；HTTP 侧补充用例复验 |
| AC-4 HTTP admin 200 + 信封 | ✅ | `test_http_delete_cancelled_schedule_ok`（200/code/msg/无 Traceback/双表） |
| AC-5 student 403 | ✅ | `test_http_delete_schedule_forbidden_for_student`（403 + schedule 仍存在） |
| AC-6 HTTP 不存在 → 404 业务信封 | ✅ | `test_http_delete_nonexistent_returns_business_error` |
| AC-7 回归 | ✅ | 56/56：cancel 12 + checkin 9 + ownership 10 + auth 25 |
| AC-8 分层合规 | ✅ | 静态 grep 0 匹配 + py_compile，详见 [static-verification.md](./static-verification.md) |

## 5. 事务与隔离说明

- **同事务原子性**：Service 直调成功用例中，`delete_by_schedule_id`（execute 不 commit）与 `repo.delete(hard_delete=True)`（内部 commit）共享测试用例的同一 AsyncSession；断言使用**新 session**读取，确认两步删除均已提交。
- **失败无写入**：AC-3 的 BusinessException 发生在任何 DELETE 语句之前；HTTP 400 用例同样在服务进程请求 session 内未触发 commit，双表新 session 复查无变化。
- **租户链路双路径**：Service 直调用例在 session 内显式 `set_tenant_id(tenant_id)`（与 F2.4 同模式）；HTTP 用例经 tenant middleware → ContextVar → ORM 事件 / `delete_by_schedule_id` 的租户过滤，跨进程在 PG 层读到的是已提交数据。
- **事件循环隔离**：`delete_data`（session 级）在 session loop 内创建并 dispose engine、只回传纯数据 dict；`local_db`（function 级）每用例独立 engine 绑定当前 loop；HTTP 经 live_server 独立 loop。9/9 无跨 loop 错误。

## 6. 回归结论

- 56 个回归用例全部通过：
  - F2.4 取消排期回滚（12/12）：下沉改动未触碰 `cancel_schedule`，取消事务模型不受影响；
  - F2.3 签到/完成行锁（9/9）；
  - F2.2 预约归属 / 跨租户访问（10/10，含 `test_service_level_student_path_like_mcp`）；
  - 认证 / JWT 双 token / 黑名单 / refresh（25/25）。
- 本 Feature 对运行时行为是"代码位移"：端点状态码、信封、错误文案、DB 终态完全不变，回归零行为风险。

## 7. 迭代记录

| 轮次 | 问题 | 修复 |
|------|------|------|
| 第 1 轮 | — | **9/9 通过**（无返工；fixture 与 helper 设计阶段即沿用 F2.4 已验证模式，每用例独立 schedule 规避唯一约束，清理顺序按 FK RESTRICT 定为 booking → schedule） |

## 8. 性能与资源

- F2.5 全套 9 用例 1.66s（fixture 仅建 1 共享 course；每用例 1~2 行直接落库 + 删除）。
- 删除路径为主键 DELETE（schedule 走主键、booking 走 `idx_bookings_schedule(tenant_id, schedule_id, status)` 索引），无全表扫描；无新增锁语句。
