# F6.4 运行时测试报告

> 日期：2026-10-22
> 环境：macOS · Python 3.12（`apps/api/.venv`）· 本地 PostgreSQL 15 · 本地 Redis
> 结论：**F6.4 定向 8 条 × 10 轮稳定通过；F6.3 定向 41 + 回归 118 通过**。全量套件、D-2 取消并发、多实例调度 **NOT VERIFIED**。

## 1. 执行命令与结果

```bash
cd apps/api
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_time_overlap.py -q
```

| 轮次 | 结果 |
|------|------|
| 首次 | 8 passed / 2.58s |
| 稳定性 1–10 | 8 passed ×10（2.42s – 2.95s） |

回归：

| 集合 | 结果 |
|------|------|
| F6.3 定向（8 文件） | 41 passed / 8.86s |
| 通用回归（11 文件） | 118 passed / 12.93s |

## 2. 验收标准（B/C/D/E）对照

### B. 运行时功能

| AC | 用例 | 结果 |
|----|------|------|
| B-1 重叠拒绝且无副作用 | `test_overlap_rejected_with_course_and_window` | PASS |
| B-2 边界相接放行 | `test_boundary_touching_allowed` | PASS |
| B-3 CHECKED_IN 参与 | `test_checked_in_blocks_overlap` | PASS |
| B-4 CANCELLED / COMPLETED / NO_SHOW 不参与 | `test_terminal_statuses_do_not_block`（参数化 3 条） | PASS |
| B-5 非重叠正常预约 | `test_boundary_touching_allowed` 第二段 / 并发用例胜出方 | PASS |
| B-6 文案含课程名与时间段 | 断言 `冲突`、`拉丁舞基础`、`10:` | PASS |

### C. 权限与租户

| AC | 用例 | 结果 |
|----|------|------|
| C-1 未登录 401 | 依赖既有 `@require_roles("student")` + `get_current_user`，本次未新增用例 | PASS（既有机制，未新增验证） |
| C-2 非学员 403 | 同上 | PASS（既有机制） |
| C-3 跨租户隔离 | `test_cross_tenant_isolation`（Repository 层，第二租户真实插入） | **部分 PASS**：同租户可命中、异租户查询为空；未走 HTTP 双租户链路 |
| C-4 身份不来自请求体 | 代码审查：`student_id = current_user.get("user_id")` | PASS（审查） |

### D. 并发与幂等

| AC | 用例 | 结果 |
|----|------|------|
| D-1 并发重叠预约至多一个成功 | `test_concurrent_overlapping_bookings_only_one_succeeds`（10 轮均 [201,400]，预约总数 1） | PASS |
| D-2 并发取消 vs 预约无死锁 | 未构造用例 | **NOT VERIFIED** |
| D-3 重复提交同排期 | 既有 `find_active_booking` + 部分唯一索引，回归集覆盖 | PASS（间接） |

### E. 回归

| AC | 结果 |
|----|------|
| E-1 同排期/容量/时间窗口 | 118 回归集 PASS |
| E-2 D9 卡有效期与扣次回补 | F6.3 定向 41 PASS |
| E-3 签到完成锁/取消回滚/RBAC/调度隔离 | 118 PASS |

## 3. NOT VERIFIED（不得视为 PASS）

| 项 | 原因 |
|----|------|
| 全量 `pytest` | 未执行 |
| D-2 取消与预约并发 | 未构造用例 |
| C-1/C-2 新增用例 | 复用既有 RBAC 机制，本次未新增 |
| 多实例 APScheduler / advisory lock 生产行为 | 单实例本地环境 |
| 四端联调 | 无契约变更，未启动前端 |
