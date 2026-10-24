# 项目交付基线 — 当前系统真实状态

> 审计日期：2026-09-24
> 审计性质：只读代码 + 文档交叉验证，不相信文档中的"已完成"声明
> 审计域：架构 / 前端 / 后端 / 数据库 / AI·MCP

---

## 1. 项目定位

舞蹈机构约课 SaaS，多租户，Monorepo（pnpm）。

| 组件 | 路径 | 技术栈 | 状态 |
|------|------|--------|------|
| 后端 API | `apps/api` | FastAPI + SQLAlchemy 2.0 Async + asyncpg + PostgreSQL 15 + Redis 7 + APScheduler + FastMCP | 核心流程可用，存在安全/异常/管理后台缺陷 |
| 管理端 | `apps/admin-web` | Vue3 + Vite + Element Plus + Pinia | 13 页，核心管理可用，tenant 页为静态 |
| 学员端 | `apps/student-web` | Vue3 + Vite + Element Plus + Pinia | 7 页，预约主流程可用，四态普遍缺失 |
| 教师端 | `apps/teacher-web` | Vue3 + Vite + Element Plus + Pinia | 7 页，排期/学生管理可用 |
| 小程序 | `apps/miniapp` | uni-app + Vue3 + TS（mp-weixin，npm） | 22 页，**3 页加载即崩溃**，无类型检查防线 |
| 共享包 | `packages/api-client`、`packages/api-types`、`config`、`utils` | axios 封装 / OpenAPI 生成类型 | web 三端共享，miniapp 独立请求层 |

---

## 2. 后端模块真实状态

main.py 注册 13 个模块；另有 5 个目录仅有 models.py 骨架（未注册）。

### 2.1 已注册且业务闭环的模块

| 模块 | 闭环状态 | 关键证据 |
|------|---------|---------|
| auth | ✅ 注册/登录/登出/刷新/微信 | `auth/service.py`，双 Token，refresh 端点 |
| user | ✅ CRUD + 密码 + 角色 | `user/router.py` + `user/service.py` |
| role | ✅ 角色 CRUD + 权限分配 | `role/router.py` |
| course | ✅ 课程/类型/分类 CRUD | `course/router.py`（注意：`/courses` 被加入 SKIP_TENANT_PATHS） |
| classroom | ✅ CRUD + 维护状态 | `classroom/router.py` |
| schedule | ✅ 单条/批量创建、冲突检测、取消（含预约+课时回退） | `schedule/service.py` + scheduler |
| booking | ✅ 创建（容量+扣次同事务）、取消（FOR UPDATE+回补）、签到、完成 | `booking/service.py` |
| membership | ✅ 产品 CRUD+回收站、发卡/激活/冻结/解冻/延期/作废、流水、定时任务 | `membership/service.py` + scheduler |
| ai | ✅ chat/history/intents（规则引擎级，无 LLM） | `modules/ai/router.py` + `ai/agent/` |

### 2.2 已注册但有缺陷的模块

| 模块 | 缺陷 |
|------|------|
| admin | **用户管理全部是 Mock**（`admin/service.py:55-212` 返回假数据，create/update/delete 不操作 DB；assign-roles/batch-delete 仅清缓存） |
| teacher | 仅有列表 + me，无教师视角的学员/预约管理专属接口 |
| tenant | 只有 GET，无 PUT；前端 tenant 页为静态硬编码 |

### 2.3 仅有 models.py 骨架（未注册）

| 模块 | 现状 |
|------|------|
| `notification/` | 仅 models.py；会员卡到期提醒只写 `logger.info`，无短信/微信/小程序订阅消息 |
| `order/` | 仅 models.py，无任何业务逻辑；会员卡发放无订单关联 |
| `payment/` | 有 models.py + service.py 框架，无 router，无支付渠道接入 |
| `student/` | 仅 models.py；学员管理实际走 user 模块（按 platform_role 区分） |
| `upload/` | 仅 models.py；上传走 `common/upload/image` |

---

## 3. 核心业务流程完成度

### 3.1 已闭环

- **学员主流程**：注册 → 登录 → 浏览课程 → 查看排期 → 预约（容量+扣次同事务）→ 签到 → 完成 → 取消（FOR UPDATE + 回补）
- **会员卡生命周期**：发卡（并发锁+幂等键）→ 激活 → 扣次/回补（FOR UPDATE+幂等）→ 冻结/解冻 → 延期 → 作废 → 自动过期/激活/解冻（定时任务）
- **RBAC 框架**：权限/角色/缓存机制齐全（但 bypass 全开，见 Gap）

### 3.2 未闭环 / 缺失

- **支付**：无支付渠道接入
- **订单**：无订单业务逻辑
- **通知**：无实际推送渠道
- **学员档案**：无独立 API（走 user 模块）
- **AI**：规则引擎级（关键词匹配），无 LLM；RAG retriever 返回硬编码数据；多轮预约流程断裂

---

## 4. 安全基线现状

| 项 | 状态 | 证据 |
|----|------|------|
| RBAC 权限校验 | 🔴 `PERMISSION_CHECK_BYPASS=True`，所有装饰器直接放行 | `core/rbac/checker.py:39` |
| 任意身份伪造 | 🔴 `GET /common/test-token` 无需认证即可伪造 user_id=1, tenant_id=10 | `modules/common/router.py:89-104` |
| JWT access 黑名单 | 🔴 `get_current_user` 不校验黑名单，登出后 access token 2h 内仍可用 | `deps/auth.py:11-31` |
| 通用异常处理 | 🔴 仅注册 DanceSaasException + IntegrityError，未捕获 Exception；`debug=True` 泄露 traceback | `main.py:163-164`, `config.py:35` |
| 生产 Redis 密码 | 🔴 `docker-compose.prod.yml` 无 `requirepass` | `infra/docker/docker-compose.prod.yml:18-28` |
| 限流 | 🟡 `rate_limiter.py` 已实现但未在 main.py 注册 | `main.py:179-183` |
| JWT_SECRET | 🟡 默认值 `"change_me"`，生产若未覆盖则 Token 可伪造 | `core/config.py:43` |
| 多租户隔离 | 🟡 三层隔离存在，但 `/api/v1/courses` 跳过租户中间件；定时任务无租户上下文 | `tenant_middleware.py:36` |

---

## 5. 前端真实状态

### 5.1 构建与类型

| 端 | vue-tsc | vite build | 备注 |
|----|---------|------------|------|
| admin-web | ✅ 通过 | ✅ 通过 | chunk > 500kB 警告 |
| student-web | ✅ 通过 | ✅ 通过 | 同上 |
| teacher-web | ✅ 通过 | ✅ 通过 | 同上 |
| miniapp | ❌ 无脚本，手动跑报 30+ 错误 | ✅ `uni build` 通过（不做类型检查） | **TS 错误流入生产** |

### 5.2 API 契约对齐

- **web 三端**（api-client）：所有声明的 API 方法均对应后端真实路由，无幽灵端点（历史 membership delete/batchDelete 事故已修复）
- **miniapp**：`authApi.sendSms`、`authApi.bindAccount` 指向不存在的后端端点（死代码，未被调用）

### 5.3 运行时崩溃（P0）

miniapp 有 3 个页面加载即崩溃：
- `pages/teacher/schedule/index.vue:190` — `extractList` 未导入
- `pages/teacher/students/index.vue:134,153` — `extractList` 未导入
- `pages/student/schedule/index.vue:570` — `tenantApi` 未导入

### 5.4 四态覆盖

普遍缺失 loading / error 态：student-web 的 courses/schedule/my-bookings、teacher-web 的 courses/schedule、admin-web 的 dashboard 均存在 catch 为空或仅 console.error 的情况。

---

## 6. 数据库基线

### 6.1 Schema

24 张业务表，27 个 Alembic 迁移文件（含 3 个 merge head）。核心交易表（bookings / membership_cards / membership_card_transactions / course_schedules）有外键、Check、索引。

### 6.2 关键约束缺口

| 缺失 | 风险 |
|------|------|
| `bookings.membership_card_id` 无外键 | 预约可引用不存在的会员卡 |
| `orders.membership_card_id` 无外键 | 订单可引用不存在的会员卡 |
| 所有 status 字段无 Check 约束 | 可写入非法状态值 |
| `operator_id` / `cancelled_by` 等操作人字段无外键 | 操作人删除后历史记录无法追溯 |

### 6.3 并发安全

| 操作 | 防护 | 评估 |
|------|------|------|
| 预约名额抢占 | `FOR UPDATE SKIP LOCKED` + capacity CHECK | ✅ 安全 |
| 会员卡扣次/回补 | `FOR UPDATE` + 余额 CHECK + 幂等键唯一约束 | ✅ 安全 |
| 取消预约 | `FOR UPDATE` 串行化 + 锁顺序一致 | ✅ 安全 |
| 发卡冲突检查 | `FOR UPDATE` 锁学员所有有效卡 | ✅ 安全 |
| 排期时间冲突 | `FOR UPDATE SKIP LOCKED`（仅锁已有行） | 🔴 TOCTOU 竞态，并发可插入冲突排期 |
| 解冻批量冲突卡 | 未排序加锁 | 🔴 死锁风险 |
| 签到/完成 | 无行锁 | 🟡 并发状态竞态 |

---

## 7. AI / MCP 基线

### 7.1 架构

- AI 链路：`HTTP /ai/chat → AgentRuntime → mcp_server.py 函数 → Service`
- **关键偏差**：Runtime 直接 import 调用 `mcp_server.py` 中的 Tool 函数，**不经过 MCP 协议**；FastMCP 仅作函数注册表
- `ai/tools/` 目录存在 9 个未使用的 stub，与 `mcp_server.py` 构成两套并存

### 7.2 可信链路（达标）

- `user_id` / `tenant_id` 均从 JWT 经 `get_current_user` 注入 AgentRuntime，不接受 LLM/前端传入
- 所有 Tool 均走 Service 层，无直连 DB

### 7.3 关键缺陷

- **多轮预约流程断裂**：`runtime.py:482` 的 `_parse_schedules` 期望 `- ID:5 | 日期 | 时间 | 教师 | 剩余:N` 格式，但 `mcp_server.py:161` 的 `query_schedules` 实际输出 `- 09/22 19:00-20:00 瑜伽 教师：...（排期ID: 123）`，解析器永远返回空列表
- 写操作 Tool 无 RBAC 授权校验
- `_handle_business_error` 异常映射表为死代码（英文 key vs 中文消息），兜底分支回显原始异常信息

---

## 8. 部署与运维

| 项 | 状态 |
|----|------|
| Docker 开发/生产 compose | ✅ |
| API Dockerfile | ✅ |
| Nginx HTTPS 反代 + SPA | ✅ |
| CI：ruff + mypy(continue-on-error) + unit tests | ⚠️ 不跑 integration |
| CD：SSH 部署 + alembic + health check | ⚠️ `--no-frozen-lockfile`，无回滚 |
| 数据库备份 | ❌ 无 |
| 监控/告警/集中日志 | ❌ 无 |
| 证书自动续期 | ❌ 无（硬编码路径） |

---

## 9. 文档与代码一致性差异

| 文档声明 | 代码实际 |
|---------|---------|
| `docs/architecture.md:347` 称 teacher-web 不存在 | `apps/teacher-web/` 实际存在且完整 |
| `docs/architecture.md:348` 称 packages/ 不存在 | `packages/` 存在（4 个包） |
| `CLAUDE.md:20` 称 packages 有 shared-ui | 实际无 shared-ui 包 |
| `docs/membership/audit-report-v1.md` P0-1（resolved_count=0） | 已修复，但文档未更新 |
| README 称 CI 跑"自动构建、测试、部署" | CI 仅跑 unit 测试，integration 不跑 |

---

## 10. 总结判定

**当前状态：不可直接上线交付。**

核心交易链路（预约/扣次/取消）的并发安全设计合格，但存在以下阻断性差距：

1. **安全防线全面失守**：RBAC bypass + 任意身份伪造 + access token 不失效 + 异常泄露 + Redis 无密码
2. **管理后台不可用**：admin 用户管理全是 Mock
3. **小程序核心页面崩溃**：教师排期/学员、学员排期页面加载即崩溃
4. **AI 预约流程断裂**：多轮预约无法完成
5. **后台定时任务无租户隔离**：多租户模式下跨租户数据风险
6. **支付/订单/通知三大域未闭环**
7. **运维基础设施缺失**：无备份/监控/告警/回滚

需修复全部 P0 及大部分 P1 后方可达到交付基线。
