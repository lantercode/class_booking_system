# F3.3 — Review

## Scope Review

- 后端新增 2 个 PUT 端点 + schemas + Service 方法 + 18 测试；
- 前端新建 tenant.ts + barrel export + stub 改真实联调页；
- 未触碰 DB schema（settings JSONB 已存在）、tenant_middleware、ORM 租户事件；
- 未影响 student-web / teacher-web / miniapp。

## Architecture Review

| 规则 | 结论 |
|------|------|
| Router 只做参数提取+Pydantic+Service 调用 | ✅ 无业务判断 |
| Service 持事务 | ✅ update_settings/update_info 均 commit |
| tenant_id 从 JWT 取 | ✅ current_user.get("tenant_id")，不从请求体 |
| @require_roles 显式声明 | ✅ admin, super_admin |
| 端点无尾斜杠 | ✅ redirect_slashes=False |
| 前端只通过 HTTP API 访问后端 | ✅ tenantApi 走 apiClient |
| baseURL 相对路径 | ✅ /api/v1 |
| 前端不在本地定义后端 DTO | ✅ 从 @dance-saas/api-client 引用 |
| 请求体不含 tenant_id/user_id | ✅ |
| 输出安全（不回显 traceback） | ✅ test_no_traceback 验证 |

## Code Review

- 浅合并用 `exclude_unset=True` + `{**current, **data}`：保证未传键不被默认值覆盖，语义正确；
- JSONB 变更用赋值新 dict（而非 in-place update）：确保 SQLAlchemy 检测到变更；
- info 字段白名单限制可写范围：防止越权写 status/plan/slug；
- 前端 dirty 检测用初始快照：精确到字段级，与后端 exclude_unset 语义对齐。

## Regression Review

- 后端 18/18 + test_rbac_enforcement tenant 相关无回归；
- 前端 vue-tsc 0 error + build 成功。

## Risks

| 风险 | 等级 | 缓解 |
|------|------|------|
| 前端清空字段发 '' 而非 null | 低 | 后端 str|None 接受空字符串；如需 null 语义需后端调整 |
| 前端未做端到端真实联调 | 低 | 401 由 api-client 统一 refresh 重放；编译通过保证类型正确 |
| response_model=dict 而非强类型 | 低 | 全项目惯例，登记为独立技术债 |

## New Tech Debt

- D-F3.3-1：response_model 全项目统一迁移为 StandardResponse[Schema]（独立技术债，不在本 Feature 范围）。

## Recommendation

**READY_FOR_ACCEPTANCE**
