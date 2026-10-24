# F6.4 代码评审（Review）

> 日期：2026-10-22
> 评审方式：主 Agent 实跑验证 + 代码审查 + 范围核对
> 结论：**READY_FOR_ACCEPTANCE（后端范围）**

## 1. 独立验证记录

| 项 | 方式 | 结果 |
|----|------|------|
| F6.4 定向 | 主 Agent 执行 11 次（首次 + 10 轮稳定性） | 8 passed × 11 |
| F6.3 回归 | 主 Agent 执行 | 41 passed |
| 通用回归 | 主 Agent 执行 | 118 passed |
| 语法 / Lint | `py_compile` + `ruff` | PASS |
| 范围 | mtime 清单 | 无越界 |

## 2. 发现与风险

| ID | 级别 | 描述 | 建议 |
|----|------|------|------|
| R1 | 中 | advisory lock 使用 `(int4, int4)` 双键，ID 超过 2^31 将溢出 | 当前量级安全；若未来引入雪花 ID 需改单键 bigint 哈希 |
| R2 | 中 | 锁只串行化**预约创建**；取消/完成链路不取该锁，理论上无环但未经 D-2 实测 | 合并后补取消并发用例 |
| R3 | 低 | 文案时间固定 `Asia/Shanghai` | 多区域部署时改为租户配置 |
| R4 | 低 | 全量 `pytest` 未执行 | 合并前补跑 |
| R5 | 低 | C-3 仅 Repository 层验证 | 需双租户 HTTP 环境时补 API 级用例 |

## 3. 设计一致性

- O1 直接拒绝、O2 不豁免同课程、O3 纳入 CHECKED_IN、O4 排除终态、O5 文案带课程名与时间段 → 全部一致。
- 与 D9 解耦：卡校验在前、时间冲突在后，互不覆盖。
- 分层：Service 校验、Repository 查询与锁，Router 未改。
- 租户：JOIN 查询显式叠加 `Booking.tenant_id`（有注释说明），未绕过 `TenantAwareRepository`。

## 4. 结论

- 功能、边界、终态、并发（D-1）在后端范围内达到验收要求。
- 不判定为「整体完成」：D-2、全量测试、API 级跨租户、生产多实例仍为 NOT VERIFIED。
