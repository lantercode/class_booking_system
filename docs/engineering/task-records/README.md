# 任务遥测记录（Task Records）

> 启用日期：2026-10-21（S0 试点，经人工批准）
> 定位：**只记录工程过程数据，不改变任何规则、流程或验收标准。**

## 1. 为什么要有这个目录

审计报告（`docs/engineering/ai-coding-efficiency-audit.md`）确认：仓库内没有任何任务耗时、Agent 调用或返工记录，导致"模型等待 / 工具执行 / 规划 / 返工"的结构无法测量，所有优化都只能靠推测。

本目录用于建立**最小可用的基线数据**，让后续的分级流程与并行方案可以被证伪或证实。

## 2. 适用任务

| 任务类型 | 是否记录 | 记录深度 |
|---------|---------|---------|
| L1 微改（≤1 文件，无业务规则变更） | 是 | 只填基本信息 + 关键 7 字段 |
| L2 小修（≤3 文件，单模块） | 是 | 基本信息 + 阶段耗时 + 验证 |
| L3 单域特性 | 是 | 完整模板 |
| L4 跨域/高风险 | 是 | 完整模板 |
| 纯问答、一次性查询、无文件变更 | 否 | — |

## 3. 命名与位置

```
docs/engineering/task-records/
  ├─ README.md                  ← 本文件
  ├─ TEMPLATE.md               ← 模板
  └─ <YYYYMMDD>-<task_id>-<slug>.md
```

示例：`20261021-F6.3-card-deduction.md`、`20261021-L1-fix-import.md`

- 每个任务**一份**，任务结束时补全；中途可增量写入。
- Feature 任务的原始产物仍放在 `docs/features/<ID>/`，本记录**不替代**验收文档。

## 4. 字段定义

| 字段 | 含义 | 采集方式 |
|------|------|---------|
| `risk_level` | L1–L4 | 任务开始时声明，只升不降 |
| `start_at` / `end_at` | 任务起止时间（含等待用户确认的时间，单独标注） | 手工记录 |
| `wall_clock` | 端到端墙钟时长 | `end_at - start_at` |
| `stage_time` | 各阶段耗时 | 每阶段开始/结束各记一次 |
| `tool_calls` | 该阶段工具调用次数 | 手工计数 |
| `invoked_agents` | 实际调用的 Agent | 手工记录 |
| `not_invoked_reason` | 未调用某域 Agent 的原因 | 一句话 |
| `docs_read` | 读取的文档与节 | 记录 `path#Lx-Ly` |
| `files_expected` / `files_actual` | 计划文件 vs 实际改动 | `git diff --stat` |
| `rework` | 返工阶段、原因、次数 | 出现即记 |
| `verification` | static / unit / integration / runtime / human | 每项写 PASS/FAIL/NOT RUN |
| `outcome` | PASS / FAIL / BLOCKED | 以人工验收为准 |

## 5. 可用的采集命令

```bash
# 文件改动量与范围
git diff --stat
git diff --numstat

# 文档读取量
wc -l <file>

# 命令耗时（macOS / Linux）
/usr/bin/time -p <command>
```

> 不要求精确到毫秒；分钟级即可支撑阶段性判断。

## 6. 数据边界（硬约束）

- **禁止**写入：密钥、Token、数据库口令、用户手机号等 PII、模型内部推理、原始私有代码片段。
- 只记录路径、时间、计数、结论，不记录敏感内容。
- 本目录数据**不参与**任何自动门控，也不能作为"任务已通过"的证据；验收仍以 `review` + 人工确认为准。

## 7. 指标汇总（后续实验使用）

| 指标 | 计算方式 |
|------|---------|
| Lead Time | `wall_clock` |
| Stage Time | `stage_time` 求和/分项 |
| Rework Rate | `sum(rework.count) / 任务数` |
| First-pass Acceptance | 首次人工验收 PASS 的任务占比 |
| Doc Ratio | 产出 md 行数 / `git diff --numstat` 代码行数 |
| Agent Efficiency | 有实质产出的 Agent 调用 / 总调用 |
| Context Load | `docs_read` 行数合计 |

## 8. 与实验的关系

按已批准的实验设计：样本原为 **F6.3–F6.6**（前 2 个基线，后 2 个试点）。实际执行中 F6.5/F6.6 也按基线完成（见 `ai-coding-efficiency-experiment-1.md` §1 分组偏差声明）；经 2026-10-22 人工批准，**补做试点组：F6.7/F6.8**（启用 M1/M2/M3/M5/M6，执行口径见实验报告 §7）。所有任务均使用本模板记录；试点组额外填写模板第 9 节，并遵守子 Agent 回传要求（模板头部）。
