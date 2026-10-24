---
alwaysApply: false
globs: "apps/api/**/*.py"
---

# 事务与并发一致性

## 事务边界

1. 同一业务流程中的多个写操作（例：创建预约 = 名额递增 + INSERT booking + 会员卡扣次 + 流水）必须共享同一个 `AsyncSession`，最后**统一 `commit()`，失败整体回滚**。
2. `Repository.create()` 默认 `auto_commit=True`；在多写事务中**必须显式传 `auto_commit=False`**，否则该 INSERT 提前提交，破坏原子性。
3. **禁止**用 `try/except` 吞掉下游 Service / Repository 的写异常后继续 `commit()`（曾导致"预约已取消但课时未恢复"的不一致）。下游写失败必须让异常传播以触发回滚。
4. 事务边界归 Service 层控制；Repository 不自行决定提交（除显式单写便捷方法外）。

## 并发控制（行锁）

- **抢名额类**（读多写少、允许失败者跳过）：`SELECT ... FOR UPDATE SKIP LOCKED`，如排期 `booked_count` 递增。
- **取消/作废类**（必须串行化且防重复提交）：操作开始先对目标行 `SELECT ... FOR UPDATE`，**拿到锁后重新检查 status**，状态已变更则跳过，防止并发取消导致 `booked_count` 多减。
- 冻结/解冻/作废/延期/激活等会员卡写操作，必须通过带 `FOR UPDATE` 的取卡方法加载卡片，不得用无锁读取后直接改状态。
- 发卡等"先查重后写入"场景，冲突检查前先对学员有效卡集合加锁，避免并发发卡绕过冲突检查。

## 锁顺序

- 多表加锁按固定顺序：**booking → schedule → membership card**，不得反向加锁，防止死锁。
- 循环批量处理冲突卡时，逐卡加锁、逐卡异常隔离（单卡失败记录到失败列表），但主流程写操作仍在同一事务内按既定策略提交或回滚。

## 幂等

- 发放会员卡等关键写操作支持 `idempotency_key`，重复请求返回既有结果而不是重复写入。
- 写类 MCP Tool（create_booking / cancel_booking 等）同样必须幂等，见 `ai/mcp.md`。
