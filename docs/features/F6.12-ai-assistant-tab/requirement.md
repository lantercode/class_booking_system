# F6.12 需求：学员端 AI 助手升级为一级 Tab 页

> 来源：F6.0 原型 v5 产品需求《将学员小程序端 AI 助手改为一级 Tab 页面》（`docs/features/F6.0-membership-card-prototype/prototype-visual-diff.md` §六、`ui-visual-spec.md` §2.3 备注「真实端后续需同步改造」）。
> 日期：2026-10-24。风险等级 **L2**（单域纯前端：仅 miniapp；**No DB change（已核对）**、不新增后端端点）。

## 1. 背景与现状差距

| 项 | 原型口径（唯一设计依据） | 真实端现状 |
|----|------------------------|-----------|
| 底部导航 | 4 个同级 Tab：首页 / 排期 / **AI 助手** / 我的（`prototype/index.html:1390` `TAB_DEFS`；AI 为第 3 个一级 Tab，激活色 `#8b7355`） | `HomeTabBar.vue` 3 Tab（首页/排期/我的） |
| AI 入口形态 | 独立完整聊天整页 P-M10（非悬浮窗/弹窗/抽屉） | `components/AiAssistant.vue` 悬浮 FAB（`.ai-fab`，`AiAssistant.vue:6-11`）+ 650rpx×800rpx 弹窗 |
| 聊天能力 | 原型为模拟对话（如实标注未接入） | **已真实接入** `POST /api/v1/ai/chat`（`aiChatApi`），真实页面必须沿用真实接口，不得降级为模拟 |

## 2. 已冻结契约

| # | 端点 | 状态 | 说明 |
|---|------|------|------|
| K1 | `POST /api/v1/ai/chat` | ✅ 已有 | 一次性 JSON 响应（非流式、无 tool trace），`data = {response, session_id, timestamp, has_pending_state, latency_ms}`；**R6 Capability Gate：禁止假流式** |
| K2 | `GET/DELETE /api/v1/ai/history`、`GET /api/v1/ai/intents` | ✅ 已有 | 现有 AiAssistant 已消费的能力保持不变 |

> 无任何后端改动；身份由 Token/Header 注入，前端不在消息体传 user_id/tenant_id（`ai/ai-architecture.md`）。

## 3. Scope

### 3.1 In Scope

- `apps/miniapp/src/components/HomeTabBar.vue`：扩为 4 Tab，AI 助手插入「排期」与「我的」之间（第 3 位），复用真实 `ai-robot` 图标，激活色/指示条/字号样式与现有 3 Tab 完全一致；路由指向新页 `/pages/student/ai-assistant/index`。
- `apps/miniapp/src/pages/student/ai-assistant/index.vue`（新建）：占满整屏的独立聊天页（页面注册 `pages.json`），香槟金主题，结构沿用原型 P-M10（顶部标题+会话状态、对话区滚动、快捷问题、消息气泡、loading、错误态、底部固定输入区）；**对话逻辑复用真实 `aiChatApi`**，输入长度限制与后端一致（≤500 字符）。
- `apps/miniapp/src/components/AiAssistant.vue`：支持「页面模式」（或拆出可复用聊天面板组件），学员端 4 个 Tab 页移除 FAB 引用；**教师端各页 FAB 保持不变（教师端不在本次改造范围）**。
- 学员端 Tab 页（courses/schedule/profile）移除 `<AiAssistant>` 悬浮入口，bookings 等 pushed 页同步移除；TabBar 显示范围与现有约定一致（仅 4 个 Tab 页挂载）。

### 3.2 Out of Scope

- 后端任何改动（含 SSE/流式——R6 Gate 未解除，禁止假流式）。
- 教师端导航与 AI 入口改造。
- 原型中的「模拟对话」数据与「未接入真实 AI」标注（真实端必须接真实接口，页面标题/副标题不得照抄原型「模拟对话」字样）。
- AI 消息历史持久化增强、未读、多会话管理。

## 4. 验收要点

1. 学员端底部 4 Tab，AI 助手为第 3 个，激活色 `#8b7355`；切换用 `uni.redirectTo` 与现有一致。
2. AI 页为整页聊天，非悬浮窗；对话走真实 `/api/v1/ai/chat`；错误态/加载态齐全。
3. 学员端所有页面不再出现 AI 悬浮 FAB；教师端 FAB 不受影响。
4. `vue-tsc` + `build:mp-weixin` 通过；四态与输入长度校验通过。

## 5. Required Agents

frontend-engineer（主，L2 自查替代 architect Review）。
