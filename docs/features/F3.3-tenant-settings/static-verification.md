# F3.3 — Static Verification

## 1. 后端编译检查

```bash
PYTHONPATH=src .venv/bin/python -c \
 "import py_compile; \
  py_compile.compile('src/app/modules/tenant/schemas.py', doraise=True); \
  py_compile.compile('src/app/modules/tenant/service.py', doraise=True); \
  py_compile.compile('src/app/modules/tenant/router.py', doraise=True)"
# COMPILE_OK
```

## 2. 前端类型检查

```bash
cd apps/admin-web && npx vue-tsc --noEmit
# 0 error
```

## 3. 前端构建

```bash
cd apps/admin-web && pnpm run build
# vue-tsc -b && vite build → ✓ built in 3.59s
```

## 4. 契约合规检查

```bash
# baseURL 为相对路径
grep -rn "http://\|https://" packages/api-client/src/tenant.ts
# 0 匹配（baseURL 在 index.ts 为 /api/v1）

# 请求体不含 tenant_id / user_id
grep -n "tenant_id\|user_id" packages/api-client/src/tenant.ts
# 0 匹配

# 前端不在本地重定义后端 DTO
grep -n "interface\|type " apps/admin-web/src/views/tenant/index.vue
# 0 匹配（类型全部从 @dance-saas/api-client 引用）
```

## 5. 分层合规检查

- Router 层：只做参数提取 + Pydantic 校验 + Service 调用，无业务判断；
- Service 层：持事务边界，浅合并 / 字段白名单逻辑在此；
- tenant_id 从 current_user.get("tenant_id") 取，不从请求体取；
- @require_roles("admin", "super_admin") 装饰两个 PUT 端点。

## 6. 端点无尾斜杠

```bash
grep -n "PUT.*settings\|PUT.*info" src/app/modules/tenant/router.py
# /settings 与 /info 均无尾斜杠（redirect_slashes=False）
```
