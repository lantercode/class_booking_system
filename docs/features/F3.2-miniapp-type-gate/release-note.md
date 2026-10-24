# F3.2 — Release Note

## miniapp 类型检查门禁上线（2026-09-29）

### 工程化变更（开发者 / CI 可感知，终端用户无感知）

- 微信小程序构建链路前置强制类型检查：
  - `npm run build:mp-weixin`：`uni build -p mp-weixin` → **`vue-tsc --noEmit && uni build -p mp-weixin`**
  - `npm run build:mp-weixin:dev`：同样前置 `vue-tsc --noEmit`
  - 新增 `npm run type-check`：仅类型检查不出包，供编码期使用
- 门禁行为：存在任何 TS 错误时 vue-tsc 退出码非 0，`&&` 短路使 uni build 不执行、`dist/` 不更新、整体构建失败；类型干净时正常出包。TS 错误自此无法流入 mp-weixin 生产包。

### 存量类型问题治理（27 → 0）

- `src/api/index.ts`：
  - 新增 7 个对齐后端契约的 interface：`TenantSettings`、`TenantInfo`、`AiChatMessage`、`AiChatResult`、`ScheduleDetail`、`TeacherListItem`、`TeacherStats`；复用 F3.1 既有 `PaginatedData<T>`（type-only import）。
  - 8 个 API 方法补精确响应泛型（booking 列表、schedule 详情、teacher 列表/统计、AI chat/history、tenant settings/info）——页面消费 `res.data` 由 `unknown` 变为精确类型，编译期可查字段。
  - 修复请求封装：`new Promise<ApiResponse<T>>` 泛型标注 + 401 重放递归调用显式透传 `<T>`，消除重放响应类型丢失。
  - method 联合保留后端契约所需的 `PATCH`；对 @dcloudio/types 漏声明 PATCH 的第三方类型缺陷，仅在 uni.request 调用边界做单行带注释断言，运行时行为零变化。
- `AiAssistant.vue`：`defineEmits` 补声明实际派发的 `"message-sent"`（payload：userMessage/aiResponse）；历史消息映射去除 any 注解。
- 4 个页面（booking-confirm / bookings / courses-detail / schedule）的 `statusBarHeight` 加 `?? 0` 安全默认值。
- `student/schedule/index.vue`：会员卡校验原因联合补齐代码实际返回的 `"pending"`（未激活）/ `"frozen"`（已冻结）。
- `student/booking-confirm/index.vue`：确认预约前以局部 const 收窄会员卡 ID（`number | null` → `number`），消除 null 入参。

### 兼容性

- 无后端 / OpenAPI / DB / Redis / 环境变量变更；无新依赖；无 tsconfig 放松。
- 所有修复均为类型层，运行时逻辑 / UI / 文案 / 样式零变化；网络请求 method、URL、header、401 刷新重放链路逐行未动。
- 四端影响评估：
  - miniapp：构建流程变化（新增门禁），运行包行为等价 → 已验证
  - admin-web / student-web / teacher-web：不消费 miniapp 代码与类型 → **不涉及**
  - 后端 / MCP：**不涉及**
- 不使用 `@ts-ignore` / `@ts-nocheck` / 大面积 `as any`（全仓 grep 为 0；唯一 `as` 为 PATCH 边界精准断言并附注释）。

### 验证

- `npx vue-tsc --noEmit`：基线 27 error → **0 error**（退出码 0）。
- 正向：`npm run build:mp-weixin` → `DONE Build complete.`，`dist/build/mp-weixin/` 完整产出。
- 反向：注入临时类型错误 → 构建退出码 2，uni build 被短路不执行（日志无"正在编译中"）；移除后恢复 0 error。
- 回归：F3.1 补全的 `extractList` / `tenantApi` import 及 5 个相关页面全量编译通过。

### 已知遗留（后续处理，不阻塞本次发布）

- **D-F3.2-1**：`teacherApi.getStats()` 现指向 `/auth/me`（先于本 Feature 存在的接口错配），页面以 `|| 0` 兜底；需后端补真实统计端点后另立 Feature 收紧。
- **D-F3.2-2**：CI 是否调用新门禁脚本待 DevOps 接入（退出码 0/2 语义已就绪）。
- **D-F3.2-3**：`build:h5` 与 dev watch 未挂门禁，按后续需要追加。
- **D-F3.2-4**：未激活 / 冻结会员卡在排课页的按钮文案走既有 default 分支，待产品确认是否优化。
- **D-F3.2-5**：booking 列表元素暂为 any，实体级全量类型化随小程序类型建设推进。
