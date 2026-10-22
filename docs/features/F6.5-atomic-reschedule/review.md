# F6.5 最终 Review

> 日期：2026-10-22
> 评审方式：project-architect 独立只读评审（不复用实施 Agent 结论）+ 主 Agent 实跑复核 + 范围核对
> 结论：**READY_FOR_ACCEPTANCE**；人工验收已通过；D-6 经 T6.5.11 修复后复审通过

## 1. 评审范围

- 代码：`booking`（models/repository/service/schemas/router）、`schedule`（repository/service）、`membership/service`
- 迁移：`f6a5b4c3d2e1_add_booking_reschedules.py`
- 测试：`test_booking_reschedule.py`（31）、`test_booking_reschedule_concurrency.py`（9，含 D-6 两条）
- 文档：`requirement.md`、`acceptance.md`、`implementation-plan.md`、`implementation-report.md`、`runtime-test-report.md`

## 2. 架构与分层

| 项 | 结论 |
|----|------|
| Router 职责 | PASS：仅参数/依赖/调用/响应，模式与状态判断在 Service |
| 事务边界 | PASS：`reschedule_booking` 单次 `commit()`；写入阶段异常先 `rollback()` |
| 跨模块调用 | PASS：booking 只调 `ScheduleService` / `membership_card_service`，不触达其 Repository |
| Repository | PASS：`BookingRescheduleRepository` 继承 `TenantAwareRepository`；JOIN 查询显式租户谓词 |
| 锁序 | PASS：advisory → booking → schedule(id ASC) → card(id ASC)；与 create/cancel/finalize 同序 |
| 迁移 | PASS：upgrade/downgrade 往返、`alembic check` 无漂移、租户外键与 `TenantMixin` 一致 |
| 契约 | PASS（含约定说明）：`response_model=dict` 与 booking 模块其余端点一致；OpenAPI/types 仅生成 |

## 3. 代码审查发现

| ID | 级别 | 描述 | 处置 |
|----|------|------|------|
| F1 | P1 | `schedule/service.py` 的排期取消全程未锁 booking 行，与改期并发可能重复回补、新约逃逸、改期落入已取消排期（D-6） | **已修复（T6.5.11）**：改为 `booking(id ASC) FOR UPDATE` → `schedule FOR UPDATE` → 持锁后重收集并过滤 BOOKED；D-6 两条并发用例 PASS，连续 10 轮稳定 |
| F2 | P2 | 写入前校验异常不显式 `rollback()`，依赖会话生命周期兜底 | 已修正实施报告表述；无写入，无数据风险 |
| F3 | P2 | 目标排期校验与 `create_booking` 规则重复，存在漂移风险 | 接受（本次不抽公共校验，避免扩大范围）；记入技术债观察项 |
| F4 | P2 | 目标卡为无锁快照，锁卡后未重验；PENDING 期卡并发激活存在窄窗口误判 400 | 已知风险，扣次阶段会加锁重检；登记观察 |
| F5 | P2 | `get_latest_by_old_booking` 无匹配索引，审计表增长后按租户扫描 | 数据量当前可忽略；数据治理任务再补索引 |
| F6 | P2 | D-10 用例语义（同 booking 并发重放）与 acceptance（不同 booking 同 key）不完全一致；两个 409 约束分支无覆盖 | 已在 `runtime-test-report.md` 改为「部分 PASS」并标注 |
| F7 | P2 | plan §7.4 要求重放比对旧卡，实现有意不比 | 已在 `implementation-report.md` §4 记录偏差与理由 |
| F8 | — | `response_model=dict` 导致 OpenAPI 响应宽松 | 与模块既有 8 个端点一致，非本次回归；长期契约治理另议 |

无 P0。

## 4. 回归与独立复核

| 项 | 结果 |
|----|------|
| 功能定向 | 31 passed（主 Agent 实跑） |
| 并发定向 | 9 passed（D-6 两条连续 10 轮稳定） |
| 定向回归 | 93 passed（分两批：归属 10 单独执行，其余 83 含 RBAC 17） |
| RBAC | 17 passed |
| 租户隔离 | 3 passed / 2 failed（既有 `attached to a different loop`，与本 Feature 无关） |
| 静态 | `py_compile` + `ruff` 全绿；迁移往返通过 |

## 5. 验收对照

- **可判定 PASS**：B-1~B-4、B-6~B-10、B-12、B-13、B-16~B-20；C-1~C-8；D-1~D-6、D-8、D-10（部分）；E-1~E-4、E-6。
- **NOT VERIFIED（需人工或后续补验）**：B-5、B-11 其余分支、B-14 冻结/过期/类型不适配、B-15、C-9、D-7/D-9、全量 pytest、多实例。
- **已解决的产品决策**：D-6 已通过 T6.5.11 修复并实测；B-5 旧 PENDING 卡失去锚点，人工验收已接受（保留为 D-F6.5-2 观察项）。

## 6. Risks / UNKNOWN

| 编号 | 内容 | 建议 |
|------|------|------|
| D-F6.5-1 | 排期取消 vs 改期：可能重复回补 / 新约逃逸 / 落入已取消排期 | **已关闭**：T6.5.11 取消锁硬化完成，D-6 两条用例 PASS |
| D-F6.5-2 | 期卡 PENDING 锚点漂移（U5） | 接受；审计表保留新旧排期 |
| D-F6.5-3 | 审计表无业务 FK，排期/预约硬删后可能孤儿 | 数据治理任务处理 |
| D-F6.5-4 | 排期规则重复实现（F3） | 后续抽取公共校验 |
| D-F6.5-5 | D-10 语义缺口与 409 分支未覆盖（F6） | 补 1 条跨 booking 同 key 用例 |

## 7. Recommendation

**READY_FOR_ACCEPTANCE → 人工验收通过（2026-10-22）**。

1. 真实学员：次卡同卡/异卡改期、期卡 ACTIVE/PENDING 改期、纯改派、无卡改期 —— 已覆盖。
2. 失败路径：目标已满/已取消/时间重叠/取消窗口/非本人/跨租户 —— 已覆盖。
3. 幂等：同 `Idempotency-Key` 重放与同键不同参数 409 —— 已覆盖。
4. B-15、B-11 其余分支、B-14 冻结/过期/课程类型不适配 —— 人工判定逻辑正确，保留为未单测项。
5. D-6 —— 已由 T6.5.11 修复，不再作为上线阻塞项；技术债 D-F6.5-1 关闭。

可进入 Stage 12 Close，更新 Backlog 为 DONE。
