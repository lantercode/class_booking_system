# F3.2 — Review

> 日期：2026-09-29 ｜ 审查人：frontend-engineer（自审 + `.trae/rules` 规则清单）

## Scope

- 变更严格限于 Feature 定义，F3.2 实际触达 7 文件：
  1. `apps/miniapp/package.json`（scripts 门禁 + type-check）；
  2. `apps/miniapp/src/api/index.ts`（类型定义 + 泛型修复 + 8 方法泛型实参）；
  3. `apps/miniapp/src/components/AiAssistant.vue`（emit 签名 + map 推导）；
  4. `student/booking-confirm/index.vue`（?? 0 + const 收窄）；
  5. `student/bookings/index.vue`（?? 0）；
  6. `student/courses/detail.vue`（?? 0）；
  7. `student/schedule/index.vue`（联合补全 + ?? 0）。
- `student/courses/index.vue`、`teacher/profile/index.vue`、`teacher/schedule/form.vue` 的 9 个错误由 API 层类型修复，页面文件零改动。
- 后端 / admin-web / student-web / teacher-web / MCP / DB / migration / Redis / 配置：**0 改动**。
- 工作区前序未提交改动（F3.1 的 membership / teacher schedule / students / icon-map 等）经 diff 逐 hunk 核对未被触碰；未执行任何 git commit / stash / reset / 破坏性操作。
- 未新增依赖、未改 tsconfig（strict 保持）、未新增 @ts-ignore。

## Architecture（对照 `.trae/rules`）

- **系统边界（architecture.md）**：miniapp 仍只经 `src/api/index.ts` 单一 HTTP 层访问后端，本次仅在该层补类型，未新增第三套请求实现；无任何前端直连 DB/Redis、无复制后端业务规则做最终校验（类型仅描述响应形状）。
- **契约（contracts.md）**：7 个 interface 全部依据后端真实返回（tenant service / ai router / schedule schemas / booking service）逐字段核对，未凭空发明字段；无 OpenAPI 变化、无 `packages/api-types` 产物修改（小程序用自有 `src/api/index.ts`，属契约允许的两套客户端之一）。
- **类型即文档**：API 数据边界集中建模后，页面消费 `res.data` 由 unknown 变为精确类型，门禁同时防止"消费不存在的后端字段"（如未来后端删字段，前端编译期即暴露）。

## Code

- 根因修复优先于压制：27 个错误中 20+ 个通过"数据边界补正确类型"一次性消除，无 `as any`、无空泛 `any` 默认（`request<T>` 不给 T 加 `= any` 默认，避免静默弱化全部调用点）。
- `bookingApi.list` 的泛型实参用 `PaginatedData<any>` 而非全面建模 booking 实体：与本 Feature"修门禁、不做全量 DTO 工程"的范围匹配，且复用 F3.1 既有类型；后续若要强化可平滑替换为 `PaginatedData<Booking>`。
- 唯一断言（PATCH）限定单行、带注释、断言目标与第三方 d.ts 逐字一致，且保留了对后端契约必需的 PATCH 动词。
- 运行时等价性：`?? 0`（仅 undefined 边界不同，正常设备值一致）、联合补全（switch 分支不变）、emit 签名（运行时派发早已存在）、const cardId（同值同时机读取）——无业务分支变化。
- vue-tsc 27 → 0 一次性通过；无返工循环。

## Security

- 类型修改不触及身份头注入（Authorization / x-tenant-slug）、401 刷新重放链路；`request<T>` 递归泛型修复仅改变静态类型，重放运行时逻辑逐行未动。
- 无 Token / 密钥 / URL 硬编码变化（BASE_URL 逻辑未动）；无错误信息回显面扩大。
- 无新增网络入口、无依赖安装，供应链面零变化。

## Verification

- 静态：`npx vue-tsc --noEmit` 退出码 0；@ts-ignore / @ts-nocheck grep 0 匹配；新增 as any 0；tsconfig / 依赖零变化（证据见 static-verification.md）。
- 运行时：RT-1 正向真实构建成功并产出 dist；RT-2 探针反向退出码 2 且 uni build 执行计数 0；RT-3 还原 0 error；RT-4 type-check 正常（证据见 runtime-test-report.md）。
- 回归：F3.1 的 extractList / tenantApi import 与 5 个消费页面全量编译通过；F3.1 修复的页面在检查范围内无新错误。

## Acceptance

- AC-1 ~ AC-8 全部满足（逐条证据见 acceptance.md 与两份验证报告）。

## 遗留事项（不阻塞验收）

1. **D-F3.2-1**：`teacherApi.getStats()` 当前端点为 `/auth/me`，运行时返回用户对象，并非 `{courses,schedules,students}` 统计；页面靠模板 `|| 0` 兜底。这是**先于本 Feature 存在的业务/接口错配**，本次仅按消费结构补类型。建议后端提供真实教师统计端点（或前端改接正确端点）后收紧 `TeacherStats`，另立 Feature，需 backend-engineer 参与。
2. **D-F3.2-2**：CI 流水线是否已执行 `npm run build:mp-weixin`（或 `npm run type-check`）未在本次范围内核查；门禁脚本与退出码已就绪（0/2），建议 DevOps 在 CI 配置接入该命令，使门禁在服务端也强制执行。
3. **D-F3.2-3**：`build:h5` 与 `dev:*` 未挂门禁（AC 范围仅 mp-weixin 出包；dev 需热更新速度）。如团队希望 H5 出包与本地 watch 也受类型约束，可后续追加；watch 场景建议改用 IDE / vite 插件提示而非阻断。
4. **D-F3.2-4**：`student/schedule/index.vue` 中 reasonType 为 `pending` / `frozen` 时 switch 走 default 显示"可预约"，为既有 UI 行为（本次仅让类型联合追上代码事实）。是否应为未激活 / 冻结卡展示专属按钮文案，建议产品确认后另立小 Feature。
5. **D-F3.2-5**：`bookingApi.list` 元素仍为 any，未做 Booking 实体全量建模；待小程序整体类型化推进时统一补 `Booking` / `MembershipCard` 等实体 interface。

## 结论

**READY_FOR_ACCEPTANCE**
