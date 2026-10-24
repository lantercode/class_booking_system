# F3.3 — Implementation Report

## 后端实施

### schemas.py（新建）

4 个 Pydantic 模型：
- TenantSettingsUpdate：booking_cancel_minutes（Field(90, ge=1, le=480)）、booking_advance_days（Field(14, ge=1, le=90)）
- TenantInfoUpdate：name（str 必填）、logo_url/contact_phone/contact_email（str|None）
- TenantSettingsResponse / TenantInfoResponse：与 GET 返回一致

### service.py（新增方法）

**update_settings**：
1. 查 tenant → `current = tenant.settings or {}` → `merged = {**current, **data}`（data 为 exclude_unset 后的 dict）
2. `tenant.settings = merged`（赋值新 dict 确保 JSONB 变更检测）
3. commit → 返回 `{booking_cancel_minutes: merged.get(..., default), booking_advance_days: ...}`

**update_info**：
1. 查 tenant → 遍历 `_UPDATABLE_INFO_FIELDS`（name/logo_url/contact_phone/contact_email），只更新 data 中非 None 值
2. commit → 返回与 get_tenant_info 同构 dict

### router.py（新增端点）

- `PUT /settings`：@require_roles("admin", "super_admin")，入参 TenantSettingsUpdate，调 service.update_settings
- `PUT /info`：同角色，入参 TenantInfoUpdate，调 service.update_info
- 既有 GET /settings、GET /info 不变

## 前端实施

### packages/api-client/src/tenant.ts（新建）

4 接口（TenantSettings / TenantInfo / TenantSettingsUpdate / TenantInfoUpdate）+ tenantApi（getSettings/updateSettings/getInfo/updateInfo）。沿用 courses.ts 的 `import apiClient from './index'` + 具名导出风格。

### packages/api-client/src/index.ts

补 `export { tenantApi } from './tenant'` 与类型 re-export。

### apps/admin-web/src/views/tenant/index.vue（stub 改造）

- 去掉硬编码值（"奕欣舞蹈"、"010-12345678" 等）；
- onMounted 并行 GET settings + GET info → 回填表单；
- 拆为两 el-card（机构信息 / 预约配置），各带独立保存按钮；
- dirty 检测：初始快照做字段级比较，PUT payload 只含变更字段（exclude_unset 语义）；
- 可空字段 null → '' 归一化显示与比较；
- 四态覆盖：v-loading 加载态、el-result 错误态 + 重试、成功 ElMessage.success、无变更 ElMessage.info；
- 去掉营业时间、联系地址字段（后端 settings 不含），max→booking_advance_days、cancel→booking_cancel_minutes；
- slug 改为只读展示（不可修改）。
