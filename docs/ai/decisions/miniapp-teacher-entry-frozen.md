# 决策记录：小程序教师端入口冻结

- **日期**：2026-11-07
- **状态**：已生效（短期方案）
- **决策**：小程序当前只服务学员端；`apps/miniapp/src/pages/teacher/*` 与 `Auth` 的 teacher 分支**保留但冻结**，所有可登录账号（含教师+学员双角色）统一进入 `/pages/student/courses/index`；纯教师账号因后端拒绝无 `student` 角色登录而无法进入。
- **明确禁止**：不得把 `pages/teacher/*` 当作死代码删除；恢复教师端时按「`roles` 数组分流 + 补 `role` 字段 + 注册 `pages/teacher/dashboard/index` + 身份切换入口」推进。
- **依据**：`apps/miniapp/src/utils/auth.ts`、`apps/miniapp/src/utils/wechat.ts`、`apps/api/src/app/modules/auth/service.py`、`apps/miniapp/src/pages.json`。
