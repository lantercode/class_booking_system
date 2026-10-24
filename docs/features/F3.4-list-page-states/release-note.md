# F3.4 — Release Note

## 概述

完成「列表页四态补全」Feature，三端共 12 个列表页全部具备 loading / empty / error / success 四态，统一前端用户体验。

## 变更范围

- **admin-web**：6 个列表页（membership、courses、card-types、classrooms、roles、dashboard）补 error / loading / empty 态；
- **student-web**：3 个列表页（courses、schedule、my-bookings）补 error / loading / empty 态；
- **teacher-web**：3 个列表页（courses、students、schedule）补 error / loading / empty 态。

## 四态标准

- **loading**：`v-loading="loading"` 或 `el-skeleton` 视觉加载；
- **empty**：`el-empty` 或 `el-table empty-text="暂无数据"`；
- **error**：`el-result icon="error"` + 重试按钮 + `ElMessage.error(后端 msg)`；
- **success**：原有列表渲染逻辑（未改动）。

## 错误处理统一

所有 catch 块统一从后端统一信封 `{code, msg, data}` 取 msg：

```ts
catch (e: any) {
  loadError.value = e?.response?.data?.msg || '加载 X 列表失败'
  ElMessage.error(loadError.value)
  list.value = []
}
```

## 验证结果

- 三端 `vue-tsc --noEmit`：0 error；
- 三端 `pnpm run build`：admin 3.54s / student 3.08s / teacher 3.52s 全部成功；
- grep 四态覆盖证据：16 个被改列表页（含 F3.3 tenant）全部命中 v-loading / el-empty | empty-text / el-result icon="error" | loadError。

## 不在范围

- miniapp 端（uni-app）；
- 后端 API / DB / MCP；
- 新增依赖；
- 既有 unused function 警告（登记为 D-F3.4-1 / D-F3.4-2 技术债）。

## 兼容性

- 纯前端改动，不破坏向后兼容；
- 已有四态页面（admin/tenant、admin/schedules、admin/teachers、admin/students、admin/users）未改动；
- API 调用方式、筛选/分页/排序/表单提交逻辑全部保留。

## 技术债

- D-F3.4-1：admin-web/courses/index.vue 等存在 unused function 警告（既有代码，本 Feature 仅补四态未清理）；
- D-F3.4-2：admin-web/dashboard 的 unused var 类型警告（同上）。

## 关联文档

- 需求：[requirement.md](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.4-list-page-states/requirement.md)
- 用户流程：[user-flow.md](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.4-list-page-states/user-flow.md)
- 验收标准：[acceptance.md](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.4-list-page-states/acceptance.md)
- 实施计划：[implementation-plan.md](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.4-list-page-states/implementation-plan.md)
- 实施报告：[implementation-report.md](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.4-list-page-states/implementation-report.md)
- 静态验证：[static-verification.md](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.4-list-page-states/static-verification.md)
- 运行时测试：[runtime-test-report.md](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.4-list-page-states/runtime-test-report.md)
- Review：[review.md](file:///Users/lixiang/Desktop/class_booking_system/docs/features/F3.4-list-page-states/review.md)

## Backlog 状态

`docs/delivery/feature-backlog.md` F3.4 条目已更新为 ✅ DONE (2026-09-29)。
