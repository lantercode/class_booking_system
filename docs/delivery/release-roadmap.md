# 产品交付路线图（Release Roadmap）

> 生成日期：2026-09-24
> 基于真实审计结果制定，非机械沿用旧 T01-T20
> 路线图按依赖关系排序，每个 Phase 有明确的准入与准出标准

---

## 路线总览

```
Phase 1: 核心业务可交付（P0 修复）
    ↓
Phase 2: 体验与 UI（P1 前端修复 + 四态补全）
    ↓
Phase 3: 安全与稳定性（P1 后端修复 + 数据库一致性）
    ↓
Phase 4: 测试与回归（CI 完善 + 集成测试 + 并发测试）
    ↓
Phase 5: 生产环境（部署 + 备份 + 监控）
    ↓
Phase 6: AI Agent / MCP（AI 预约流程 + Tool 安全）
    ↓
Phase 7: 后续迭代（支付 / 通知 / 通知推送 / 优化）
```

---

## Phase 1：核心业务可交付

**目标**：修复所有 P0，使核心流程安全可用、不崩溃

**准入条件**：审计完成、P0 清单确认

**准出条件**：全部 P0 修复 + 回归测试通过

| 任务 | 关联 Feature | 负责 Agent |
|------|-------------|-----------|
| RBAC bypass 置 False + 补全装饰器 | F1.1 | backend-engineer |
| 删除/保护 test-token、test-exception | F1.1 | backend-engineer |
| JWT access_token 黑名单校验 | F1.2 ✅ DONE | backend-engineer |
| 通用 Exception 处理器 + debug=False | F1.3 ✅ DONE | backend-engineer |
| 生产 Redis 密码 | F1.4 | backend-engineer |
| 定时任务租户隔离 | F1.5 | backend-engineer |
| admin 用户管理真实化 | F2.1 | backend-engineer |
| miniapp 3 页面崩溃修复 | F3.1 ✅ DONE | frontend-engineer |
| AI 多轮预约解析修复 | F5.1 | mcp-engineer |

**验收标准**：
- 学员无法访问 admin 接口（403）
- 登出后旧 token 立即失效（401）
- 触发异常返回标准化 500，无 traceback
- miniapp 教师排期/学员、学员排期页面正常加载
- AI 能完成一次完整预约对话
- 定时任务不跨租户操作

---

## Phase 2：体验与 UI

**目标**：修复 P1 前端问题，补全四态，达到交付级 UI

**准入条件**：Phase 1 准出

**准出条件**：所有页面四态齐全、无 TS 错误流入生产

| 任务 | 关联 Feature | 负责 Agent |
|------|-------------|-----------|
| miniapp 类型检查门禁 + 修复 30+ TS 错误 | F3.2 | frontend-engineer |
| admin tenant 页对接真实接口 | F3.3 | frontend-engineer + backend-engineer |
| 前端四态补全（loading/empty/error） | F3.4 | frontend-engineer |
| AiAssistant storage 键修复 | P2-14 | frontend-engineer |
| miniapp 租户 fallback 修复 | P2-13 | frontend-engineer |
| 401 双端检测机制统一 | P2-15 | frontend-engineer |
| AI 输入 maxlength 校验 | P3-7 | frontend-engineer |

**验收标准**：
- `npm run build:mp-weixin` 前 vue-tsc 通过
- 所有列表页有 loading/empty/error 态
- admin tenant 页可保存真实配置
- AI 对话 sessionId 正确关联用户

---

## Phase 3：安全与稳定性

**目标**：修复 P1 后端业务缺陷 + 数据库一致性，消除数据风险

**准入条件**：Phase 2 准出

**准出条件**：无数据泄露、无死锁风险、事务原子性完整

| 任务 | 关联 Feature | 负责 Agent |
|------|-------------|-----------|
| 预约数据归属与泄露修复 | F2.2 | backend-engineer |
| 签到/完成加行锁 | F2.3 | backend-engineer + database-engineer |
| cancel_schedule 回补失败回滚 | F2.4 | backend-engineer + database-engineer |
| delete_schedule 下沉 Service | F2.5 | backend-engineer |
| RateLimiter 注册 | P1-11 | backend-engineer |
| clear_role_permissions_cache 实现 | P1-10 | backend-engineer |
| membership HTTPException 统一 | P1-8 | backend-engineer |
| bookings.membership_card_id 外键 | F4.1 | database-engineer + backend-engineer |
| orders.membership_card_id 外键+索引 | F4.2 | database-engineer |
| 解冻批量操作锁排序 | F4.3 | backend-engineer + database-engineer |
| status 字段 Check 约束 | F4.4 | database-engineer |
| 排期创建并发安全 | F4.5 | backend-engineer + database-engineer |
| Tool 授权校验 | F5.2 | mcp-engineer |
| AI 异常处理不泄露 | F5.3 ✅ DONE | mcp-engineer |

**验收标准**：
- 学员 A 无法查看学员 B 的预约
- 并发签到不产生状态竞态
- 取消排期时回补失败则整体回滚
- bookings/orders 外键约束生效
- 解冻批量操作无死锁
- AI Tool 错误不回显内部异常

---

## Phase 4：测试与回归

**目标**：CI 完整覆盖，集成测试与并发测试通过

**准入条件**：Phase 3 准出

**准出条件**：CI 全绿、并发场景无数据不一致

| 任务 | 负责 Agent |
|------|-----------|
| CI 增加 integration 测试 | backend-engineer |
| mypy 改为阻塞 | backend-engineer |
| 前端四端类型检查加入 CI | frontend-engineer |
| 预约并发测试（抢名额、取消） | backend-engineer + database-engineer |
| 会员卡扣次并发测试 | backend-engineer + database-engineer |
| 多租户隔离测试 | backend-engineer |
| RBAC 越权测试 | backend-engineer |
| AI 预约端到端测试 | mcp-engineer |
| 清理 ai/tools/ 残留 | mcp-engineer |

**验收标准**：
- CI 运行 unit + integration 全部通过
- 并发抢名额不超卖
- 并发取消不重复回补
- 跨租户访问返回空或 403

---

## Phase 5：生产环境

**目标**：可重复部署、有备份、有监控

**准入条件**：Phase 4 准出

**准出条件**：生产环境一键部署、每日备份、核心指标可观测

| 任务 | 负责 Agent |
|------|-----------|
| 数据库每日备份脚本 + 调度 | backend-engineer |
| CD `--frozen-lockfile` + 回滚机制 | backend-engineer |
| Nginx 证书自动续期（certbot） | backend-engineer |
| 监控告警（Prometheus + Grafana 或云服务） | backend-engineer |
| 集中日志（Loki 或云日志） | backend-engineer |
| 生产环境变量审计（JWT_SECRET 等无默认值） | backend-engineer |
| 部署文档更新 | project-architect |

**验收标准**：
- 生产数据库每日自动备份，可恢复
- CD 部署版本可追溯，可回滚
- HTTPS 证书自动续期
- 核心指标（响应时间、错误率、预约量）有面板和告警

---

## Phase 6：AI Agent / MCP

**目标**：AI 助手真正可用，安全可靠

**准入条件**：Phase 5 准出（AI 依赖稳定后端）

**准出条件**：AI 能完成核心查询与预约，安全合规

| 任务 | 负责 Agent |
|------|-----------|
| AI 预约流程端到端验证 | mcp-engineer |
| AI 多轮对话体验优化 | mcp-engineer |
| RAG 真实接入（替换硬编码 retriever） | mcp-engineer |
| AI 审计日志（Tool 调用记录） | mcp-engineer |
| AI UI 流式/工具状态（如后端支持 SSE） | mcp-engineer + frontend-engineer |
| AI 安全测试（Prompt Injection、PII） | mcp-engineer |

**验收标准**：
- AI 能完成查询课程/排期/余额/预约/取消全流程
- RAG 返回真实知识库内容
- Prompt Injection 测试不绕过安全规则
- AI 对话不泄露敏感信息

---

## Phase 7：后续迭代

**目标**：业务域补全与持续优化

**准入条件**：Phase 6 准出

| 任务 | 负责 Agent |
|------|-----------|
| 支付渠道接入（微信支付/支付宝） | backend-engineer + database-engineer |
| 订单模块业务逻辑 | backend-engineer |
| 通知系统（微信订阅消息/短信） | backend-engineer |
| 学员档案独立 API | backend-engineer |
| 前端 element-plus 按需分包 | frontend-engineer |
| 前端自动化测试（vitest/uni-automator） | frontend-engineer |
| 定时任务频率生产化 | backend-engineer |
| 迁移命名规范化 | database-engineer |

---

## 里程碑与依赖

```
Phase 1 (P0) ──→ Phase 2 (UI) ──→ Phase 3 (安全+数据) ──→ Phase 4 (测试)
                                                              ↓
Phase 7 (迭代) ←── Phase 6 (AI) ←── Phase 5 (生产) ←────────┘
```

**关键依赖**：
- Phase 3 的外键修复依赖 Phase 1 的 admin 真实化（避免 Mock 数据干扰）
- Phase 4 的并发测试依赖 Phase 3 的行锁修复
- Phase 6 的 AI 依赖 Phase 5 的稳定后端
- Phase 7 的支付依赖 order/payment 模块从零搭建

---

## 各 Phase 退出标准汇总

| Phase | 退出标准 |
|-------|---------|
| Phase 1 | 0 个 P0 未修复；核心流程不崩溃；安全防线基本到位 |
| Phase 2 | 前端四态齐全；无 TS 错误流入生产 |
| Phase 3 | 0 个 P1 未修复；无数据泄露；无死锁 |
| Phase 4 | CI 全绿；并发测试无数据不一致 |
| Phase 5 | 可重复部署；有备份；有监控 |
| Phase 6 | AI 核心流程可用；安全合规 |
| Phase 7 | 业务域补全；持续优化 |
