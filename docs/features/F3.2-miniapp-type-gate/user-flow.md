# F3.2 — miniapp 类型检查门禁 · 用户流程

> 视角：miniapp 开发者（前端工程师）在本地或 CI 执行微信小程序构建。
> 本 Feature 的"用户"是开发者；核心交互对象是 npm scripts 与 shell `&&` 短路语义。

---

## 流程 1：类型干净 → 正常出包（正向）

1. 开发者在 `apps/miniapp` 执行 `npm run build:mp-weixin`。
2. npm 解析脚本：`vue-tsc --noEmit && uni build -p mp-weixin`。
3. **第一阶段 vue-tsc**：对 `src/**`（含 `.vue` SFC 的 `<script setup lang="ts">`、模板表达式）做全量类型检查，不产出文件（`--noEmit`）。
   - 0 error → 进程退出码 0。
4. **第二阶段 uni build**（因 `&&` 前序成功才执行）：uni-app 编译 mp-weixin，输出 `dist/build/mp-weixin/`（app.js / app.json / pages/ / components/ 等），打印 `DONE Build complete.`。
5. 开发者打开微信开发者工具导入 `dist/build/mp-weixin` 运行。

> `npm run build:mp-weixin:dev` 同构：`vue-tsc --noEmit && uni build -p mp-weixin --mode development`，开发模式包同样受门禁保护。
> 另有便捷脚本 `npm run type-check`（仅检查不出包），供编码过程中单独使用。

## 流程 2：存在类型错误 → 构建中止（反向，门禁核心价值）

1. 开发者引入一个类型错误（例：`const x: number = "not-a-number"`；或页面把 `string` 传给要求 `number` 的 prop；或消费后端响应上不存在的字段）。
2. 执行 `npm run build:mp-weixin`。
3. 第一阶段 vue-tsc 输出形如：
   ```
   src/xxx.vue(12,3): error TS2322: Type 'string' is not assignable to type 'number'.
   ```
   vue-tsc 退出码为 **2**（非 0）。
4. shell `&&` 短路：**第二阶段 `uni build` 完全不执行**（日志不出现"正在编译中"，`dist/` 不更新），npm 脚本整体退出码非 0。
5. CI 中表现为红灯；本地产物不会被错误包覆盖。
6. 开发者按错误定位修复 → 重新执行 → 回到流程 1。

## 流程 3：门禁开启前的存量错误是如何被清零的（一次性治理）

门禁要能开启，前提是存量 27 个错误先清零。修复遵循"把类型补在数据边界"的原则，开发者后续写代码即自动获得保护：

```
后端契约（已核查）
  └─ src/api/index.ts  request<T>() 泛型 + 业务接口类型
       ├─ tenantApi.getSettings()      → ApiResponse<TenantSettings>
       ├─ tenantApi.getInfo()          → ApiResponse<TenantInfo>
       ├─ bookingApi.list()            → ApiResponse<PaginatedData<any>>
       ├─ scheduleApi.get(id)          → ApiResponse<ScheduleDetail>
       ├─ teacherApi.list()            → ApiResponse<TeacherListItem[]>
       ├─ teacherApi.getStats()        → ApiResponse<TeacherStats>
       └─ aiChatApi.chat()/getHistory()→ ApiResponse<AiChatResult> / <AiChatMessage[]>
            └─ 页面 res.data.xxx 全部编译期可查
```

- 平台可空值（`statusBarHeight?: number`）：使用点 `?? 0` 给 UI 语义安全默认值（4 个页面）。
- 组件契约：`AiAssistant` 的 `defineEmits` 补齐实际会派发的 `"message-sent"`。
- 领域状态联合：`CardValidationResult.reasonType` 补齐代码实际返回的 `"pending"` / `"frozen"`（会员卡未激活 / 冻结）。
- null/undefined 语义：booking-confirm 在发请求前把 `selectedCardId: Ref<number|null>` 固化为局部 `const cardId`，经 truthy 收窄后传给 `membership_card_id?: number`，不改变任何运行时分支。
- 第三方类型缺陷：PATCH 仅在 `uni.request` 调用边界做**单行带注释断言**（见流程 4）。

## 流程 4：PATCH 的类型断言边界（唯一一处精准断言）

- 事实：`request()` 的 method 联合必须包含 `"PATCH"`（后端 4 组更新接口契约）；@dcloudio/types 的 `RequestOptions.method` 联合漏 PATCH。
- 处理：
  - API 层对内使用业务语义联合 `type HttpMethod = "GET"|"POST"|"PATCH"|"PUT"|"DELETE"`；
  - 仅在 `uni.request({ method })` 边界断言为与第三方声明一致的 `UniCompatibleRequestMethod`，并附注释说明原因与运行时透传事实；
  - 断言是局部单行，不产生全局逃逸：其余代码看到的 method 仍是精确联合。

## 流程 5：门禁与开发服务器的关系（不受影响）

- `npm run dev:mp-weixin`（`uni -p mp-weixin`，watch 热更新）**不挂门禁**：开发期追求快速反馈，类型问题由 IDE / 手动 `npm run type-check` 暴露；门禁只卡在"出包"动作，不影响日常调试体验。
- `npm run build:h5` 本 Feature 不挂门禁（AC 范围为 mp-weixin；见 review 遗留事项）。

## 门禁判定真值表

| vue-tsc 结果 | `&&` 后 uni build | npm 退出码 | dist 产物 | 含义 |
|-------------|-------------------|-----------|-----------|------|
| 0 error（退出码 0） | 执行 | 0 | 更新 | 可发布 |
| 有 error（退出码 2） | 不执行 | 非 0 | 不更新 | 阻断发布，需先修类型 |
