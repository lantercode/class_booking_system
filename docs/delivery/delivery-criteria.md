# 交付标准（Delivery Criteria）

> 生成日期：2026-09-24
> 包含：Definition of Ready / Definition of Done / 最终交付标准

---

## 一、Definition of Ready（DoR）

一个 Feature 在进入开发前必须满足以下全部条件：

### 1.1 需求明确

- [ ] 有明确的用户故事（As a..., I want..., so that...）
- [ ] 有明确的业务目标（Goal）
- [ ] 有明确的问题背景（为什么做）

### 1.2 Scope 明确

- [ ] In Scope 明确列出
- [ ] Out of Scope 明确列出
- [ ] 不依赖未定义的前置能力

### 1.3 UI / 原型明确（如涉及前端）

- [ ] 有页面线框图或原型
- [ ] 有交互说明（loading / empty / error 态）
- [ ] 有设计规范引用（Element Plus 组件、小程序组件）

### 1.4 API 契约明确（如涉及后端）

- [ ] 请求方法、路径、请求体、响应结构已定义
- [ ] 错误码与错误消息已定义
- [ ] 鉴权与权限要求已定义
- [ ] 后端 OpenAPI 已更新或计划同批更新

### 1.5 验收标准明确

- [ ] Acceptance Criteria 可测试、可验证
- [ ] 包含正常流程与异常流程
- [ ] 包含安全与权限验证

### 1.6 依赖明确

- [ ] 前置 Feature 已列出且状态明确
- [ ] 跨 Agent 依赖已识别（frontend/backend/database/mcp）
- [ ] 外部依赖（第三方服务、密钥）已确认

---

## 二、Definition of Done（DoD）

一个 Feature 只有满足以下全部条件才能标记完成：

### 2.1 Frontend 完成（如涉及）

- [ ] 所有页面/组件开发完成
- [ ] Loading / Empty / Error 四态齐全
- [ ] API 对接完成，无 mock 残留（正式入口不引用 mock）
- [ ] `vue-tsc` 类型检查通过
- [ ] 目标端构建通过（web: `vite build` / miniapp: `uni build`）
- [ ] 响应式/移动端体验验证（如涉及）

### 2.2 Backend 完成（如涉及）

- [ ] Router / Service / Repository 分层正确
- [ ] Pydantic 入参校验完整（无 `data: dict` 裸接收）
- [ ] 业务异常统一抛出 `DanceSaasException`（非 HTTPException）
- [ ] 事务边界正确（多写同事务、统一 commit）
- [ ] 并发安全（必要时行锁）
- [ ] `ruff check` 通过
- [ ] `mypy` 无新增类型错误

### 2.3 Database 完成（如涉及）

- [ ] 模型变更已生成 Alembic 迁移
- [ ] 迁移文件已 review（无破坏性操作或有回滚方案）
- [ ] 外键、唯一约束、Check 约束完整
- [ ] 索引覆盖高频查询路径
- [ ] `alembic upgrade head` 成功

### 2.4 MCP / AI 完成（如涉及）

- [ ] Tool 走 Service 层，不直连 DB
- [ ] 四关校验：Authentication → Authorization → Tenant Validation → Input Validation
- [ ] 写操作幂等
- [ ] 异常不回显内部信息
- [ ] PII 脱敏

### 2.5 测试通过

- [ ] 后端单元测试通过
- [ ] 集成测试通过（如涉及核心流程）
- [ ] 并发测试通过（如涉及写操作）
- [ ] 前端构建通过
- [ ] 无新增 lint 错误

### 2.6 核心异常流程验证

- [ ] 未认证访问返回 401
- [ ] 无权限访问返回 403
- [ ] 参数校验失败返回 422
- [ ] 业务异常返回标准化错误
- [ ] 并发场景无数据不一致

### 2.7 Security 检查

- [ ] 无硬编码密钥
- [ ] 无 SQL 注入风险（全部参数化查询）
- [ ] 无越权访问
- [ ] 无敏感信息泄露（日志/响应）
- [ ] 限流生效（如涉及）

### 2.8 Review 完成

- [ ] 代码已通过至少 1 名 reviewer 审查
- [ ] 无遗留 TODO / FIXME（除非有明确后续计划）
- [ ] 无调试代码残留（print / console.log / logger.info 调试语句）

### 2.9 文档完成

- [ ] API 文档（OpenAPI）已更新
- [ ] 相关 `.trae/rules/` 规则已更新（如涉及新约束）
- [ ] 交付文档（如涉及架构变更）已更新

---

## 三、最终交付标准（上线准入）

项目达到以下全部条件方可上线：

### 3.1 功能完整性

- [ ] 核心业务流程端到端可用：注册 → 登录 → 约课 → 取消 → 签到 → 完成
- [ ] 会员卡全生命周期可用：发卡 → 扣次 → 冻结 → 解冻 → 过期 → 作废
- [ ] 管理后台用户/角色/权限管理真实可用
- [ ] 教师端排期/学员管理可用
- [ ] 小程序无运行时崩溃页面

### 3.2 安全合规

- [ ] RBAC 权限校验真实生效（bypass=False）
- [ ] JWT access_token 登出后立即失效
- [ ] 生产 Redis 有密码
- [ ] 通用异常处理器不泄露 traceback
- [ ] 无 test-token 等调试接口暴露
- [ ] 限流生效
- [ ] 所有写操作 Tool 有授权校验
- [ ] AI 异常不回显内部信息

### 3.3 数据一致性

- [ ] bookings.membership_card_id 有外键
- [ ] orders.membership_card_id 有外键
- [ ] 核心 status 字段有 Check 约束
- [ ] 预约/扣次/取消并发安全
- [ ] 排期创建无时间冲突竞态
- [ ] 解冻批量操作无死锁

### 3.4 多租户隔离

- [ ] 定时任务按租户循环
- [ ] 无跨租户数据泄露
- [ ] 禁用租户用户无法访问业务接口

### 3.5 测试覆盖

- [ ] CI 运行 unit + integration 测试
- [ ] 并发测试通过（预约、扣次、取消）
- [ ] 多租户隔离测试通过
- [ ] RBAC 越权测试通过
- [ ] 前端四端构建通过
- [ ] miniapp 类型检查门禁生效

### 3.6 运维就绪

- [ ] 生产数据库每日自动备份
- [ ] CD 部署版本可追溯、可回滚
- [ ] HTTPS 证书自动续期
- [ ] 核心指标有监控面板
- [ ] 异常有告警
- [ ] 生产环境变量无默认弱密钥

### 3.7 前端交付

- [ ] 所有页面四态（loading/empty/error/success）齐全
- [ ] 无 TS 错误流入生产
- [ ] API 契约全部对齐后端真实路由
- [ ] 401 refresh 链路双端一致

---

## 四、规则归属

| 内容 | 归属 |
|------|------|
| 项目规则（Router→Service→Repository、租户隔离、事务等） | `.trae/rules/` |
| Agent 工作方式与职责 | Agent Prompt（TRAE 智能体配置） |
| Multi-Agent 协作流程（Phase 0-8、引用标记、Handoff、Reconciliation） | `docs/ai/workflows/` |
| 交付标准（本文档） | `docs/delivery/delivery-criteria.md` |
| Feature Backlog | `docs/delivery/feature-backlog.md` |
| 发布路线 | `docs/delivery/release-roadmap.md` |

---

## 五、变更管理

- 本标准由 project-architect 维护
- 任何 DoR/DoD 条款的增删需经项目负责人确认
- 已完成 Feature 的 DoD 验收记录归档至 `docs/delivery/` 对应交付文档
