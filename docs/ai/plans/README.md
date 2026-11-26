# 待开发任务计划总览

> 用途：把当前散落的需求整理成可执行计划，供排期与验收使用。
> 说明：只给依赖关系与执行顺序，不给时间估算。

## 1. 任务分组

| 编号 | 计划 | 文档 | 依赖 |
|---|---|---|---|
| P1 | AI Agent 能力增强 | [01-ai-agent-p2.md](./01-ai-agent-p2.md) | 无（Phase 1 已上线） |
| P2 | 语音输入 | [02-voice-input.md](./02-voice-input.md) | 需先确认火山 ASR 接口细节 |
| P3 | 调度与实时推送 | [03-scheduling-realtime.md](./03-scheduling-realtime.md) | 无（可与 P1 并行） |
| P4 | 稳定性与数据治理 | [04-stability-backlog.md](./04-stability-backlog.md) | 无 |

设计方案见：

- [voice-input-plan.md](../agent/voice-input-plan.md)
- [scheduling-and-realtime-plan.md](../architecture/scheduling-and-realtime-plan.md)

## 2. 建议执行顺序

```
第一轮（收口，风险最低）—— 已完成 2026-11-21
  P4-1 数据清理（wechat_accounts 重复）   ✅ 生产巡检 0 行
  P4-2 集成测试 flake                     ✅ 已修复
  P4-3 小程序 AI 会话清空按钮             ✅ 已存在
  P4-4 Dockerfile 启动命令优化            ✅ 已生产验证
  P4-5 租户隔离用例                       ✅ 已修复并纳入 CI（顺带修复租户过滤缓存缺陷）
  P4-6 文档收口                           ✅ 已完成

第二轮（AI 可讲可演示）
  P1-1 可观测性指标聚合            ✅ 2026-11-23
  P1-2 AgentLoop 多轮与重试        ✅ 2026-11-23
  P1-3 上下文裁剪参数化            ✅ 2026-11-23

第三轮（业务亮点）
  P1-4 会员续费预警 Agent          ✅ 2026-11-23
  P1-5 写操作 Agent（预约/取消）   ✅ 2026-11-23

第四轮（架构升级，风险较高）
  P3-0 状态纯派生
  P3-1 job_queue + worker
  P3-2 延迟任务替换扫描
  P3-5 实时推送

第五轮（新交互）
  P2 语音输入（A→B→C→D）
```

## 3. 依赖与冲突

| 关系 | 说明 |
|---|---|
| P1-5 写操作 Agent ← P1-2 | 多轮循环稳定后再开放写操作 |
| P2 语音输入 ← P1-1 | 语音链路需要可观测指标，先建指标再看数据 |
| P3-2 延迟任务 ← P3-1 | 先有可靠队列，再替换扫描 |
| P3-5 推送 ← P3-0 | 状态派生正确后，推送才有意义 |
| P1 与 P3 无冲突 | 分别改 `ai/` 与 `tasks/`，可并行 |

## 4. 统一完成定义（DoD）

每个任务须满足：

1. `ruff check .` 通过；
2. `pytest tests/unit` 全绿；
3. `mypy_baseline_check.sh` 不高于基线；
4. 有可执行的验证命令或验收步骤，写在计划条目内；
5. 不新增绕过 Service / Repository 的路径；
6. 改动可独立回滚（开关或配置项）。

## 5. 全局风险

| 风险 | 影响 | 应对 |
|---|---|---|
| 生产直改数据 | 不可逆 | 先备份表，再改，SQL 留档 |
| 任务双执行 | 重复扣次/退款 | 幂等键 + 灰度开关 |
| 新增出网依赖 | 部署后功能静默降级 | 上线前容器内验证连通性 |
| 文档未提交 | 方案丢失 | 本轮结束后统一提交 |

## 6. 文档状态

| 文件 | 状态 |
|---|---|
| `docs/ai/agent/voice-input-plan.md` | 已入库 |
| `docs/ai/architecture/scheduling-and-realtime-plan.md` | 已入库 |
| `docs/ai/plans/*`（本目录） | 已入库（P4 执行状态见 04 文档） |
