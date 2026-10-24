# F3.3 — User Flow

## Flow 1：管理员加载租户设置页（Happy Path）

1. 管理员登录 admin-web，导航到"机构设置"。
2. 页面 onMounted 并行调 `GET /tenant/settings` + `GET /tenant/info`。
3. 后端从 JWT 取 tenant_id → Service 查 Tenant → 返回配置 dict。
4. 前端回填表单：机构名称、slug（只读）、logo_url、联系电话、联系邮箱、取消规则（booking_cancel_minutes）、可提前预约天数（booking_advance_days）。
5. 页面显示成功态。

## Flow 2：管理员修改预约配置并保存

1. 管理员修改"取消规则"从 90 → 120 分钟。
2. 点击"保存配置"按钮。
3. 前端 dirty 检测：只发送 `{booking_cancel_minutes: 120}`（exclude_unset 语义）。
4. 后端 PUT /settings → Service 浅合并 settings dict → commit → 返回更新后配置。
5. 前端 ElMessage.success("配置已更新")，用后端返回值更新本地状态。

## Flow 3：管理员修改机构信息并保存

1. 管理员修改机构名称与联系电话。
2. 点击"保存机构信息"按钮。
3. 前端 dirty 检测：发送 `{name: "新名称", contact_phone: "新电话"}`。
4. 后端 PUT /info → Service 更新非 None 字段 → commit → 返回更新后 info。
5. 前端 ElMessage.success。

## Flow 4：无变更时保存

1. 管理员未修改任何字段，点击保存。
2. 前端 dirty 检测：payload 为空对象。
3. 前端 ElMessage.info("没有需要保存的变更")，不调 API。

## Flow 5：学员尝试访问（Authorization 拒绝）

1. 学员角色调 PUT /settings 或 PUT /info。
2. 后端 @require_roles("admin", "super_admin") → 403。
3. 前端显示后端返回的 msg。

## Error States

| 场景 | HTTP | 用户可见 |
|------|------|---------|
| 加载失败 | GET 500/401 | 页面 el-result 错误态 + 重试按钮 |
| 未登录 | 401 | api-client 自动 refresh 重放，失败跳登录 |
| 非法入参 | 422 | ElMessage.error 显示后端 msg |
| 权限不足 | 403 | ElMessage.error |
