# F3.3 — Implementation Plan

## Root Cause

admin-web `views/tenant/index.vue` 是硬编码 stub 页面（所有字段写死、无 API 调用、无保存按钮逻辑）。后端 tenant 模块只有两个 GET 端点，缺少写操作能力。管理员无法修改机构配置。

## Affected Files

### 后端（4 文件）

| 文件 | 操作 |
|------|------|
| `modules/tenant/schemas.py` | 新建：TenantSettingsUpdate / TenantInfoUpdate / TenantSettingsResponse / TenantInfoResponse |
| `modules/tenant/service.py` | 新增 update_settings / update_info |
| `modules/tenant/router.py` | 新增 PUT /settings、PUT /info |
| `tests/integration/test_tenant_update.py` | 新建：18 用例 |

### 前端（3 文件）

| 文件 | 操作 |
|------|------|
| `packages/api-client/src/tenant.ts` | 新建：4 接口 + tenantApi |
| `packages/api-client/src/index.ts` | barrel export |
| `apps/admin-web/src/views/tenant/index.vue` | stub → 真实联调 |

## Exact Fix

### 后端

- **schemas**：TenantSettingsUpdate（booking_cancel_minutes: int=90, 1-480; booking_advance_days: int=14, 1-90）；TenantInfoUpdate（name: str 必填; logo_url/contact_phone/contact_email: str|None）
- **Service**：update_settings 用 `model_dump(exclude_unset=True)` → `{**current, **data}` 浅合并 → `tenant.settings = merged`（新 dict 触发 SQLAlchemy JSONB 变更检测）→ commit → 返回与 get_settings 同构 dict；update_info 用字段白名单更新非 None 值
- **Router**：PUT /settings 与 PUT /info，@require_roles("admin", "super_admin")，tenant_id 取自 current_user.get("tenant_id")，无尾斜杠

### 前端

- **tenant.ts**：沿用 courses.ts 的默认导入 + 具名导出风格；4 方法 getSettings/updateSettings/getInfo/updateInfo
- **tenant/index.vue**：onMounted 并行 GET → 回填表单；两 el-card 各带独立保存按钮；dirty 检测用初始快照做字段级比较；PUT payload 只含变更字段（exclude_unset 语义）；可空字段 null → '' 归一化；v-loading + el-result 错误态 + 重试

## Verification Plan

1. 后端：`pytest tests/integration/test_tenant_update.py`（18/18）；
2. 前端：`npx vue-tsc --noEmit`（0 error）+ `pnpm run build`（成功）；
3. 回归：test_rbac_enforcement tenant 相关通过；
4. py_compile 4 个后端文件。

## UNKNOWN

- 前端未做端到端真实联调（dev server），运行时若 401 由 api-client 统一 refresh 重放；
- response_model 用 dict 而非 StandardResponse[Schema]（全项目惯例，登记为独立技术债）。
