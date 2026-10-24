# F1.2 — Static Verification

> 阶段：STATIC VERIFICATION
> 日期：2026-09-26

## 1. 范围守卫（minimal-change-guard）

### 1.1 白名单

```
apps/api/src/app/core/security.py
apps/api/src/app/modules/auth/service.py
apps/api/src/app/modules/auth/router.py
apps/api/src/app/deps/auth.py
apps/api/tests/integration/test_auth_api.py
```

### 1.2 verify-scope.sh 结果

脚本输出 FAIL，原因：工作区存在 63 项 Pre-Change Guard 已记录的**历史改动**（ai/、rbac/、membership/、miniapp 等），这些不在 F1.2 白名单内。

**精确复核结论**：
- ✅ 5 个白名单文件全部在 `git diff --name-only` 中
- ✅ 5 个白名单文件之外，F1.2 相关目录（auth/、deps/auth、core/security）无其他文件被修改
- ✅ 工作区其他改动与 Pre-Change 基线（`/tmp/f12-pre-git-status.txt`）完全一致——`comm` 比对 MATCH
- ✅ `git diff --check`：无空白错误

**判定**：verify-scope.sh 的 FAIL 是工作区历史污染导致的假阳性，非 F1.2 越界。按"实际修改文件 ⊆ 白名单"的核心判据，**范围守卫 PASS**。

### 1.3 numstat（5 白名单文件）

```
44  3   apps/api/src/app/core/security.py
75  0   apps/api/src/app/deps/auth.py           (含 get_redis_client 上移的重排)
11  8   apps/api/src/app/modules/auth/router.py
20  21  apps/api/src/app/modules/auth/service.py
275 0   apps/api/tests/integration/test_auth_api.py
```

### 1.4 逐文件 diff 审查

- **security.py**：仅黑名单函数签名扩展 + 新工具函数，无其他改动
- **service.py**：仅 logout 方法签名与内部逻辑，其余方法未动
- **router.py**：仅 logout handler 提取 access_token，其他端点未动
- **deps/auth.py**：get_redis_client 上移 + 两个认证依赖注入 redis，无其他逻辑
- **test_auth_api.py**：新增 TestAccessTokenBlacklist + 修复 4 处预存断言，无业务代码

## 2. 编译验证

| 文件 | py_compile |
|------|-----------|
| core/security.py | ✅ OK |
| modules/auth/service.py | ✅ OK |
| modules/auth/router.py | ✅ OK |
| deps/auth.py | ✅ OK |
| tests/integration/test_auth_api.py | ✅ OK |

## 3. 契约验证（AC-5.2）

- 无新端点、无删除端点
- logout 请求体不变（`refresh_token` 仍可选）
- logout 响应体不变（统一信封 `{code:0,msg:"登出成功"}`）
- access_token 仍从 Authorization 头提取（非请求体新增字段）

## 4. 静态结论

| AC | 判定 |
|----|------|
| AC-5.1 变更范围 ⊆ 白名单 | ✅ PASS |
| AC-5.2 无契约变更 | ✅ PASS |
| AC-5.3 py_compile | ✅ PASS |
| AC-5.4 预存改动未被覆盖 | ✅ PASS（基线比对 MATCH） |
