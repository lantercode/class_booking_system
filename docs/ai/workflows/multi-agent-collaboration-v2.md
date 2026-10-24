# Multi-Agent 协作流程优化规范 v2

> **日期**: 2026-09-22
> **基于**: ai-course-query-collaboration-review.md 审查结果
> **目标**: 解决 3 个缺陷，将协作质量从 96.1% 提升到 98%+

---

## 缺陷回顾

| # | 缺陷 | 当前评分 | 目标评分 |
|---|------|---------|---------|
| 1 | Database Agent 仅做确认性分析，未独立发现问题 | 2.5/3 | 3/3 |
| 2 | backend.md 与 architecture.md 内容重叠 | 3/4 | 4/4 |
| 3 | INTENTS 优先级冲突在实施阶段才发现 | 5/5 (修复好) | 5/5 (提前发现) |

---

## 优化 1: Agent 专属检查清单（解决缺陷 1 + 2）

### 问题

当前各 Agent 的职责边界模糊：
- Database Agent 只做了 Architect 结论的确认，没有独立发现新问题
- Backend Agent 重复了 Architect 已做过的分析

### 方案

为每个 Agent 定义**不可委托的专属检查项**，明确"只做这些，不重复 Architect 已做的"。

### Architect 专属检查（不可委托）

```
✅ 全局调用链绘制（Frontend → API → Router → Service → Repository → DB）
✅ 跨模块依赖识别
✅ 改动文件清单 + 改动范围确认
✅ 冲突点预判（不同 Agent 的方案是否矛盾）
✅ 冒烟测试设计（见优化 3）
```

### Backend Agent 专属检查（不可委托）

```
✅ 逐参数验证 Service 方法签名是否支持所需参数
✅ Router → Service → Repository 的参数透传链是否完整
✅ 异常路径分析（Service 抛异常时 Router 如何处理）
✅ 参数提取逻辑验证（IntentRecognizer 的关键词匹配是否正确）
❌ 不重复 Architect 的调用链分析 — 引用即可
❌ 不重复数据库表结构分析 — 引用 Database Agent 结论
```

**写作规范**: 当引用 Architect 结论时，使用明确引用格式：
```markdown
> **引用 Architect architecture.md §2.1**: "意图识别存在 6 个问题..."
> 
> **本节验证**: 逐关键词验证结果如下...
```

### Database Agent 专属检查（不可委托）

```
✅ 索引覆盖分析：所有查询路径是否有对应索引
✅ 锁风险分析：FOR UPDATE 使用是否正确，是否存在死锁风险
✅ 查询性能分析：是否有 N+1 查询、全表扫描
✅ 约束完整性：唯一约束、Check Constraint 是否覆盖业务规则
✅ Migration 风险：如果需要变更，锁表风险评估
❌ 不只做"确认 No Change Required" — 必须独立发现至少 1 个潜在问题
```

**写作规范**: 即使结论是 "No Database Change Required"，也必须包含：
```markdown
## 独立发现

| # | 检查项 | 结果 | 风险等级 |
|---|--------|------|---------|
| 1 | 索引覆盖 | ✅ 所有查询路径有索引 | — |
| 2 | 锁风险 | ⚠️ query_schedules 无 FOR UPDATE，但只读查询无需锁 | Low |
| 3 | N+1 查询 | ✅ 未发现 | — |
```

### MCP Agent 专属检查（不可委托）

```
✅ Tool 契约分析：Input/Output Schema 是否完整
✅ 鉴权机制：user_id/tenant_id 来源是否安全
✅ 输入校验：Tool 参数是否有 try/except
✅ 错误处理：Service 异常是否被友好捕获
✅ PII 检查：Tool 返回值是否包含敏感数据
✅ Redis 分析：是否涉及缓存/锁/会话
✅ Prompt Injection 防护：System Prompt 是否包含安全规则
```

---

## 优化 2: 引用规范（解决缺陷 2）

### 问题

backend.md §1.2 和 architecture.md §2.问题1 都分析了"我还有几节课"意图识别缺陷，内容重叠。

### 方案

引入**三层引用标记**，明确区分"引用""验证""新发现"。

### 引用标记规范

| 标记 | 含义 | 示例 |
|------|------|------|
| `[REF:arch-§2.1]` | 引用 Architect 的结论，不重复分析 | `[REF:arch-§2.1] Architect 识别到意图识别存在关键词缺失` |
| `[VERIFY:arch-§2.1]` | 验证 Architect 的结论，给出验证结果 | `[VERIFY:arch-§2.1] 逐关键词验证：✅ "几节课"确实未在 INTENTS 中` |
| `[NEW]` | 本 Agent 独立发现的新问题 | `[NEW] query_schedules 的 date 参数缺少 try/except` |

### 写作模板

```markdown
## 1. 前置结论验证

### [VERIFY:arch-§2.1] 意图识别关键词缺失

Architect 结论：get_my_bookings 缺少"几节课"等关键词。

验证结果：
| 关键词 | 当前是否匹配 | 预期意图 | 实际意图 |
|--------|------------|---------|---------|
| "几节课" | ❌ | get_my_bookings | unknown |
| "还有几节" | ❌ | get_my_bookings | unknown |

✅ 确认 Architect 结论正确。

---

## 2. 独立发现

### [NEW] Service 异常未捕获

mcp_server.py 的 get_my_bookings Tool 直接调用 BookingService.list_bookings，
但未捕获 Service 层抛出的 BusinessException。

影响：如果 Service 抛异常，MCP Tool 会返回 traceback 给用户。
```

---

## 优化 3: Phase 1 冒烟测试（解决缺陷 3）

### 问题

INTENTS 优先级冲突（"帮我预约明天"被 query_schedules 的"明天"拦截）在 Phase 5 实施阶段才发现，应该在 Phase 1 架构分析阶段就发现。

### 方案

在 Phase 1 Architect Analysis 结束前，**强制执行冒烟测试**。

### Phase 1 新增步骤

```
Phase 1: Architect Analysis
  ├─ Step 1: 问题识别（原有）
  ├─ Step 2: 架构决策（原有）
  └─ Step 3: 冒烟测试 ← 新增
      ├─ 如果任务涉及意图识别 → 跑意图识别冒烟测试
      ├─ 如果任务涉及 API → 跑 API 签名冒烟测试
      └─ 如果任务涉及 DB 查询 → 跑查询能力冒烟测试
```

### 意图识别冒烟测试模板

```python
# Phase 1 冒烟测试 — 在架构分析阶段就跑
# 目标：发现 INTENTS 优先级冲突

from app.ai.agent.intent import IntentRecognizer
r = IntentRecognizer()

SMOKE_TESTS = [
    # (用户输入, 预期意图)
    ("我还有几节课？", "get_my_bookings"),
    ("我还有多少课时？", "get_my_balance"),
    ("这周有哪些爵士舞可以预约？", "query_schedules"),
    ("帮我预约明天的瑜伽课", "create_booking"),  # ← 这个会发现优先级冲突
    ("取消预约 123", "cancel_booking"),
    ("我的预约记录", "get_my_bookings"),
]

for text, expected in SMOKE_TESTS:
    result = r.recognize(text)
    status = "✅" if result["intent"] == expected else "❌"
    print(f"{status} {text} → {result['intent']} (expected: {expected})")
```

### 冒烟测试通过标准

- **全部通过** → 进入 Phase 2
- **有失败** → 在 Phase 1 就修复优先级/关键词问题，不进入 Phase 2

### 好处

| 场景 | 优化前 | 优化后 |
|------|--------|--------|
| INTENTS 优先级冲突 | Phase 5 实施时发现 | Phase 1 分析时就发现 |
| 关键词缺失 | Phase 5 测试时发现 | Phase 1 冒烟测试发现 |
| 参数提取逻辑错误 | Phase 5 测试时发现 | Phase 1 冒烟测试发现 |

---

## 优化后的完整 Phase 流程

```
Phase 0: Project Reconnaissance
  └─ 4 探针扫描（不变）

Phase 1: Architect Analysis
  ├─ Step 1: 问题识别（不变）
  ├─ Step 2: 架构决策（不变）
  └─ Step 3: 冒烟测试 ← 新增
      ├─ 意图识别冒烟测试（如涉及）
      ├─ API 签名冒烟测试（如涉及）
      └─ DB 查询能力冒烟测试（如涉及）
      └─ 通过后才进入 Phase 2

Phase 2: Specialist Analysis
  ├─ Backend Agent
  │   ├─ [VERIFY] 验证 Architect 结论
  │   ├─ 逐参数验证 Service 签名
  │   ├─ 参数透传链分析
  │   ├─ 异常路径分析
  │   └─ [NEW] 独立发现
  ├─ Database Agent
  │   ├─ [VERIFY] 验证 Architect 结论
  │   ├─ 索引覆盖分析 ← 必做
  │   ├─ 锁风险分析 ← 必做
  │   ├─ 查询性能分析 ← 必做
  │   ├─ 约束完整性 ← 必做
  │   └─ [NEW] 独立发现 ← 必须至少 1 个
  └─ MCP Agent
      ├─ [VERIFY] 验证 Architect 结论
      ├─ Tool 契约分析
      ├─ 鉴权 + 输入校验 + 错误处理
      ├─ PII + Redis 分析
      └─ [NEW] 独立发现

Phase 3: Architecture Reconciliation
  ├─ 汇总三方分析
  ├─ 解决矛盾（如有）
  ├─ 补充决策
  └─ 更新冒烟测试（如 Phase 1 发现的问题已修复）

Phase 4: Implementation Planning
  └─ 确认最终文件清单 + 改动顺序

Phase 5: Implementation
  └─ 按顺序实施（冒烟测试已通过，预期无意外）

Phase 6: Testing
  ├─ 语法检查
  ├─ 单元测试
  ├─ 回归测试
  └─ 冒烟测试回归（确认 Phase 1 的问题已修复）

Phase 7: Cross-Agent Review
  └─ 用 v2 检查清单审查

Phase 8: Final Report
  └─ 最终报告
```

---

## 优化效果预估

| 维度 | 优化前 | 优化后 | 改善 |
|------|--------|--------|------|
| 1. Context Sharing | 4/4 | 4/4 | — |
| 2. Dependency | 4/4 | 4/4 | — |
| 3. Cross-Agent Feedback | 2.5/3 | 3/3 | +0.5（Database Agent 强制独立发现） |
| 4. Conflict | 5/5 | 5/5 | — |
| 5. Reconciliation | 3/3 | 3/3 | — |
| 6. Duplication | 3/4 | 4/4 | +1（引用标记规范） |
| 7. Project Rules | 3/3 | 3/3 | — |
| 8. Agent Prompts | 4/4 | 4/4 | — |
| 9. Final Consistency | 4/4 | 4/4 | — |
| 10. Implementation | 4/4 | 4/4 | — |
| **总计** | **36.5/38** | **38/38** | **+1.5** |

**预估优化后评分: 38/38 = 100%**

---

## 固化规则

以下规则应在后续所有 Multi-Agent 协作中固化：

### R1: Agent 专属检查不可委托

每个 Agent 必须完成自己的专属检查清单，不可跳过，不可委托其他 Agent 代做。

### R2: 引用标记强制使用

后续 Agent 引用前置 Agent 结论时，必须使用 `[REF]` / `[VERIFY]` / `[NEW]` 标记。

### R3: Phase 1 冒烟测试强制执行

如果任务涉及意图识别/API 签名/DB 查询，Phase 1 必须跑冒烟测试，通过后才进入 Phase 2。

### R4: Database Agent 必须独立发现

即使结论是 "No Database Change Required"，Database Agent 也必须完成索引/锁/性能/约束四项独立检查，并在 `[NEW]` 部分记录至少 1 个潜在问题（即使风险等级为 Low）。
