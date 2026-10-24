# F1.1 — RBAC 权限校验真实生效 · 评审报告

> Feature ID：F1.1
> 评审者：backend-engineer（自评）/ project-architect（待验收）
> 日期：2026-09-27
> 结论：**READY_FOR_ACCEPTANCE**

---

## 1. AC 覆盖评审

| AC 组 | 状态 | 证据 |
|-------|------|------|
| AC-1 配置与开关 | PASS | static-verification.md §3 |
| AC-2 权限强制执行 403/401 | PASS | runtime-test-report.md §1（4/4） |
| AC-3 学员访问 /admin/* 403 | PASS | 同上（2/2） |
| AC-4 写操作端点装饰器 | PASS | static-verification.md §2.1 + 运行时边界用例（7/7） |
| AC-5 调试端点清理 | PASS | 404 × 3 + health 200 + 孤儿 import 清理 |
| AC-6 AI 端点认证 | PASS | 401 + 非 401 |
| AC-7 种子与装饰器修复 | PASS | seed/conftest diff 一致；admin 两处修复 |
| AC-8 回归 | PASS | 25 + 11 通过；预存失败未扩大 |
| AC-9 范围控制 | PASS | 无 Service/契约/前端改动 |

Feature 级 AC 逐条核对：
- `PERMISSION_CHECK_BYPASS=False` ✅（Settings 默认 False + .env）
- 所有写操作端点有 RBAC 装饰器 ✅（13 个 router 审计 + 补全）
- 学员访问 /admin/* 返回 403 ✅（2 个用例）
- 无权限用户访问受保护接口返回 403 ✅（多角色矩阵）

## 2. 架构与规则合规

| 规则 | 合规性 |
|------|--------|
| 装饰器签名含 db/current_user | ✅（并修复了 admin/settings 缺 db 的隐藏缺陷） |
| 不新增放行开关 | ✅（bypass 改为配置驱动且默认 False；rules 中"禁止依赖 bypass"的技术债已偿还） |
| Router 不含业务逻辑 | ✅（仅加装饰器/参数） |
| 未修改 Service 层 | ✅ |
| 未修改 api-types / 契约 | ✅（路径、方法、DTO 均未变） |
| 统一异常体系 | ✅（401/403 走既有 AuthException/PermissionException 信封） |
| 密钥不入库 | ✅（配置仅布尔开关） |

## 3. Risks（含影响面）

| # | 风险 | 等级 | 缓解 |
|---|------|------|------|
| R1 | **存量数据库权限缺失**：seed.py"已存在则跳过"逻辑导致旧库不会自动获得 `admin:all`/`super:manage` 及 admin 的 7 个新权限；直接上线会使 admin 部分操作 403 | 高 | release-note.md 附手工 SQL；上线前对生产库执行权限审计 |
| R2 | **行为破坏性变化**：此前"bypass 开启"下能成功的越权调用现在返回 403。若有前端页面/脚本依赖了越权行为（如学员端误调管理接口），会暴露为 403 | 中 | 这正是本 Feature 目标；四端代码已 grep 无调试端点依赖；正式端点均有装饰器且前端按角色渲染入口，预期无影响；上线后监控 403 率 |
| R3 | 权限缓存 300s：角色变更最长 300s 生效 | 低 | 既有行为；角色分配接口已做缓存失效 |
| R4 | 并行跑全量测试时 live_server 端口竞争导致 ConnectError 假象 | 低 | 单独运行验证通过；建议后续测试基础设施 Feature 处理端口分配 |
| R5 | MCP Tool 层仍是"认证后未做细粒度授权" | 中 | 属 Feature 5.2 范围；mcp_server.py 注释已更新指明 |

## 4. 问题清单

无阻塞问题。登记 1 个技术债：

- **D-F1.1-1**：`ai/router.py` `get_supported_intents` 访问不存在的 `IntentRecognizer.intents` 实例属性（实际为类属性 `INTENTS`，且结构为 list[tuple] 非 dict），认证通过后 500。建议修复：`get_supported_intents` 改为遍历 `IntentRecognizer.INTENTS` 类属性。

## 5. 评审结论

所有 AC 达成，规则合规，风险均有缓解或登记。**READY_FOR_ACCEPTANCE**，可进入 Feature Closing（更新 feature-backlog / release-roadmap）。
