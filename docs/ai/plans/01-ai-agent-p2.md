# P1｜AI Agent 能力增强计划

> 前置：Phase 1 已上线（单租户灰度，只读 4 工具）。
> 原则：不新增绕过 `execute_tool` 的路径；不把业务规则写进 Prompt；身份只来自 `ToolContext`。

## P1-1 可观测性指标聚合

**状态**：已完成（2026-11-23）。脚本 `apps/api/scripts/ai_trace_stats.py`，单测 `apps/api/tests/unit/test_ai_trace_stats.py`（4 例）。

**目标**：把已有 `ai_chat_trace` 日志变成可量化、可展示的数据。

**现状**：`runtime.py` 每次对话输出一行 `ai_chat_trace`，含 `mode`、`llm_calls`、`fallback_reason`、`latency_ms`、`step_ms`、`provider`。

**任务**

| # | 内容 | 文件 |
|---|---|---|
| 1 | 新增脚本：从容器 stdout 解析 trace，输出 mode 分布、回退率、P50/P95、工具调用次数、Token 估算 | `apps/api/scripts/ai_trace_stats.py`（新增） |
| 2 | 支持按时间窗、租户、模式过滤 | 同上 |
| 3 | 输出 Markdown 表格，便于贴入报告或面试材料 | 同上 |

**验收**

```bash
docker logs --since 24h dance-api 2>&1 | grep ai_chat_trace > /tmp/trace.log
.venv/bin/python scripts/ai_trace_stats.py /tmp/trace.log
```

输出包含：总请求数、`llm` / `llm_fallback` 占比、P95 延迟、平均工具调用次数。

**风险**：日志格式变更会导致解析失败——脚本需对缺字段容错，缺失时跳过并计数。

---

## P1-2 AgentLoop 多轮与失败重试

**状态**：已完成（2026-11-23）。`AI_LLM_MAX_TOOL_LOOPS` 默认 4；`ai/agent/loop.py` 增加只读工具瞬时故障（超时/5xx）重试 1 次、截断与总量上限沿用；单测 `tests/unit/test_ai_llm_loop.py`。

**目标**：支持「先查课程 → 再查该课程排期」的两步链路，同时保证不失控。

**现状**：`AI_LLM_MAX_TOOL_LOOPS=2`（模型调用次数上限），只读工具失败即结束。

**任务**

| # | 内容 | 文件 |
|---|---|---|
| 1 | `AI_LLM_MAX_TOOL_LOOPS` 默认 2 → 4，保留配置可调 | `core/config.py` |
| 2 | 只读工具对「超时 / 5xx」重试 1 次；参数错误、权限错误**不重试** | `ai/agent/loop.py` |
| 3 | 单次工具结果超长时截断（按字符数），并标注 `truncated` | `ai/agent/loop.py` |
| 4 | 工具总调用数上限保持 ≤5，超出立即收敛并返回兜底文案 | `ai/agent/loop.py` |
| 5 | 补充测试：多轮成功、重试成功、重试耗尽、超步数收敛 | `tests/unit/test_ai_llm_loop.py` |

**验收**

- 提问「这周有什么课，第二节还有位置吗」能触发 2 次工具调用并正确回答；
- 人为让 Provider 首次超时，第二次成功，最终回答正常；
- 超过 4 轮时返回兜底文案，不抛异常。

**风险**：轮次提升会放大延迟与成本。上线前用真实 prompt 复测 P95，超过 12 秒则回退为 2。

---

## P1-3 上下文裁剪参数化

**状态**：已完成（2026-11-23）。新增 `AI_LLM_HISTORY_LIMIT` / `AI_LLM_HISTORY_MAX_CHARS`；`build_llm_messages` 双限裁剪且 system 完整保留；单测 `tests/unit/test_ai_llm_prompts.py`（5 例）。

**目标**：把「历史固定 6 条」变成可配置，并按预算裁剪。

**任务**

| # | 内容 | 文件 |
|---|---|---|
| 1 | 新增 `AI_LLM_HISTORY_LIMIT`（默认 6）、`AI_LLM_HISTORY_MAX_CHARS`（默认 2000） | `core/config.py` |
| 2 | `build_llm_messages` 按条数与字符预算双限裁剪，优先保留最近消息 | `ai/agent/prompts.py` |
| 3 | 裁剪后保证 system prompt 完整保留 | 同上 |
| 4 | 单测：超限裁剪、边界值、system 不丢 | `tests/unit/test_ai_llm_prompts.py` |

**验收**：构造 20 条历史，断言最终 messages 条数与字符数均在预算内，且首条为 system。

---

## P1-4 会员续费预警 Agent

**状态**：已完成（2026-11-23）。`membership_card_service.list_renewal_alerts`、只读 Tool `query_expiring_cards`、`ai/agent/renewal.py`（Provider 单次调用 + 模板兜底）、`notifications` 站内消息表与接口、每日幂等任务 `send_renewal_alerts`（`AI_RENEWAL_ALERT_*` 默认关闭）。

**目标**：识别即将到期或课时不足的学员，生成提醒话术并触达。

**边界**：**业务判定用代码，不用模型**；模型只负责把结构化结果写成一句自然语言。

**任务**

| # | 内容 | 文件 |
|---|---|---|
| 1 | 新增只读查询：按租户查「N 天内到期」与「剩余课时 ≤ 阈值」的卡（Service 已有能力优先复用） | `modules/membership/service.py`（仅新增只读方法） |
| 2 | 新增只读 Tool `query_expiring_cards`（admin/teacher 角色可见） | `ai/mcp_server.py` |
| 3 | 预警话术生成：复用 Provider，单次调用，超时即用模板兜底 | `ai/agent/`（新增轻量函数） |
| 4 | 触达：站内消息；微信订阅消息作为后续项 | `modules/`（按现有通知能力） |
| 5 | 幂等：同一学员同一卡同一周期只提醒一次 | 幂等键 |

**验收**：给定 3 张临期卡，生成 3 条提醒且不重复；模型超时情况下仍发出模板提醒。

**风险**：群发打扰。上线前设置每日上限与白名单租户。

---

## P1-5 写操作 Agent（预约 / 取消）

**状态**：已完成（2026-11-23）。`AI_LLM_WRITE_TOOLS`（默认关闭，需同时关闭 `AI_LLM_READONLY_ONLY`）；对话轮内只产出「拟执行」确认卡片，`POST /api/v1/ai/actions/confirm` 校验防篡改令牌 → Redis 幂等 → 统一 Tool 入口执行 → 写 `audit_logs`；一次回复最多一个写操作。

**目标**：在只读稳定后开放写操作，且安全边界不降级。

**前置**：P1-2 完成；生产验证至少一周无异常。

**任务**

| # | 内容 | 文件 |
|---|---|---|
| 1 | 工具保留在 `TOOL_SPECS`，但默认不进入模型可见集合（`AI_LLM_WRITE_TOOLS=false`） | `core/config.py`、`ai/agent/tool_schema.py` |
| 2 | 两阶段确认：模型只能发起「拟执行」，返回确认卡片数据；用户点击后走原有 HTTP 接口执行 | `ai/agent/runtime.py`、小程序 |
| 3 | 幂等键：`user_id + schedule_id + action`，同一请求内重复调用只执行一次 | `ai/agent/loop.py` |
| 4 | 审计：记录 who / what / when / 结果 / 确认来源 | 新表或现有日志表 |
| 5 | 禁止模型在一次回复中连续执行多个写操作 | `ai/agent/loop.py` |

**验收**

- 模型请求预约 → 前端出现确认卡片 → 用户点击才真正下单；
- 重复请求不产生两条预约；
- 未确认时数据库无变化。

**风险**：模型误判触发确认卡片，属于打扰而非事故；但确认链路必须真实存在，不能只靠提示词。

---

## 完成定义

1. `ruff check .`、`pytest tests/unit`、`mypy_baseline_check.sh` 全通过；
2. 每项有可复现的验收命令；
3. 新增配置项同步写入 `.env.example` / `.env.prod.example` / `docker-compose.prod.yml`；
4. 默认关闭或安全默认值，可单独回滚。
