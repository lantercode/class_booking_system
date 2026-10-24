# F3.3 — Acceptance Criteria

| ID | 验收标准 | 验证方式 | 结果 |
|----|---------|---------|------|
| AC-1 | PUT /api/v1/tenant/settings 端点存在且 admin/super_admin 可调 | test_admin_update_settings_success + test_super_admin_can_update_settings | PASS |
| AC-2 | PUT /api/v1/tenant/info 端点存在且 admin/super_admin 可调 | test_super_admin_update_info_success + test_admin_can_update_info | PASS |
| AC-3 | settings 浅合并：只传 cancel_minutes 时 advance_days 不被覆盖 | test_settings_merge_semantics | PASS |
| AC-4 | info 部分更新：只传 name 时 logo_url 不被覆盖为 None | test_info_partial_update_preserves_other_fields | PASS |
| AC-5 | 入参校验：cancel_minutes=0/500、advance_days=0、字符串 → 422 | test_invalid_*（4 用例） | PASS |
| AC-6 | info 缺必填 name → 422 | test_info_missing_name_returns_422 | PASS |
| AC-7 | 学员角色 PUT → 403 | test_student_cannot_update_settings/info | PASS |
| AC-8 | 未认证 PUT → 401 | test_unauthenticated_settings/info | PASS |
| AC-9 | 端点无尾斜杠（redirect_slashes=False） | test_*_trailing_slash_404 | PASS |
| AC-10 | 前端 packages/api-client/src/tenant.ts 提供 4 方法 | grep tenantApi + vue-tsc 编译 | PASS |
| AC-11 | admin-web tenant 页从 stub 改为真实联调 | vue-tsc 0 error + build 成功 | PASS |
| AC-12 | 前端 baseURL 为相对路径 /api/v1 | grep 确认无硬编码绝对 URL | PASS |
| AC-13 | 请求体不含 tenant_id / user_id | 契约审查 + grep | PASS |
| AC-14 | 回归：test_rbac_enforcement tenant 相关通过 | pytest test_rbac_enforcement | PASS |
| AC-15 | 前端类型从 @dance-saas/api-client 引用，不在本地重定义 DTO | grep import | PASS |
