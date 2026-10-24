# F1.1 — RBAC 权限校验真实生效 · Release Note

> Feature ID：F1.1
> 发布日期：2026-09-27
> 类型：安全修复（含行为破坏性变化）

---

## 1. 概述

关闭 RBAC 全局放行开关（`PERMISSION_CHECK_BYPASS` 硬编码 True），补全 13 个端点的权限/角色装饰器，删除 3 个无认证调试端点（其中 `GET /common/test-token` 可无认证生成任意用户 JWT，属严重认证绕过漏洞）。自此所有受保护端点执行真实权限校验。

## 2. 安全修复

- **严重**：删除 `GET /api/v1/common/test-token`（无认证可生成 admin JWT）、`/test-exception`、`/test-auth`。
- **高**：`PERMISSION_CHECK_BYPASS` 由硬编码 `True` 改为配置驱动、默认 `False`；4 处权限校验短路全部移除。
- **高**：13 个端点补齐授权（详见 implementation-report.md §2）。

## 3. 行为变化（破坏性，前端需注意）

| 场景 | 变更前 | 变更后 |
|------|--------|--------|
| 越权调用受保护接口 | 200（bypass 放行） | **403** |
| 无 token 调 `GET /ai/intents` | 200 | **401** |
| 无 token/任意角色调调试端点 | 200 | **404** |
| 教师调 booking 创建 | 200 | **403**（学员专属） |
| 未授权角色上传图片 | 200 | **403** |

前端四端无需代码改动（401/403 处理已在 API 客户端层实现），但若有任何页面依赖了越权调用，将以 403 形式暴露。

## 4. 部署注意事项（重要）

### 4.1 配置

`.env` 新增：

```bash
PERMISSION_CHECK_BYPASS=false   # 生产必须 false；仅本地调试可临时 true
```

### 4.2 存量数据库权限补齐（必须执行）

`seed.py` 的"权限已存在则跳过"逻辑不会给旧库补新权限。**升级存量环境后必须手工执行**（或在维护窗口清库重 seed）：

```sql
-- 1) 新增两个权限码（module=admin；表名/字段以实际 schema 为准）
INSERT INTO permissions (code, name, module, description, created_at, updated_at)
VALUES
  ('admin:all', '管理端全部权限', 'admin', '管理端通配权限', NOW(), NOW()),
  ('super:manage', '超管管理权限', 'admin', '超级管理员通配权限', NOW(), NOW())
ON CONFLICT (code) DO NOTHING;

-- 2) admin 角色补 7 个权限（将 <admin_role_id> 替换为实际 admin 角色 ID）
INSERT INTO role_permissions (role_id, permission_id, created_at)
SELECT <admin_role_id>, p.id, NOW()
FROM permissions p
WHERE p.code IN (
  'course:delete','user:delete','user:reset_password',
  'classroom:delete','role:create','role:update','role:delete'
)
AND NOT EXISTS (
  SELECT 1 FROM role_permissions rp
  WHERE rp.role_id = <admin_role_id> AND rp.permission_id = p.id
);

-- 3) 使权限缓存失效（或等待 300s TTL 自然过期）
--    redis-cli --scan --pattern "perms:*" | xargs redis-cli DEL
```

执行前请先在预发环境验证 admin 的删课 / 重置密码 / 角色管理等操作返回 200。

### 4.3 环境检查清单

- [ ] `PERMISSION_CHECK_BYPASS=false`（生产）
- [ ] 存量库权限 SQL 已执行并验证
- [ ] Redis 可达（权限缓存 + token 黑名单依赖）
- [ ] 上线后监控 403 错误率突增（识别依赖越权行为的隐藏调用方）

## 5. Changed Files

代码 14 个文件改动 + 1 个新建测试（详见 implementation-report.md §2）。文档：`docs/features/F1.1-rbac-enforcement/`（9 份）。

## 6. Tests

- `tests/integration/test_rbac_enforcement.py`（新增）：**17/17 PASS**
- `tests/integration/test_auth_api.py`：**25/25 PASS**（单独运行）
- `tests/integration/test_rbac_real_redis.py` + `tests/test_agent_runtime.py`：**11/11 PASS**

## 7. Known Issues / 技术债

| ID | 描述 | 处置 |
|----|------|------|
| D-F1.1-1 | `GET /ai/intents` 认证通过后 500（`IntentRecognizer.intents` 属性不存在，应为类属性 `INTENTS`） | 后续 Feature 修复 `ai/router.py:get_supported_intents` |
| — | test_tenant_isolation（3）/ test_mcp_server（4）预存失败 | 与 F1.1 无关，另行处理 |
| — | 多测试文件并行运行时 live_server 端口竞争致 ConnectError | 测试基础设施改进项 |
| — | seed.py 与 conftest.py 权限列表双写 | 建议收敛为单一数据源 |

## 8. 回滚方案

代码回滚即恢复原状；若仅临时需要放行调试，可将环境变量 `PERMISSION_CHECK_BYPASS=true`（**仅限本地，禁止生产**）。调试端点已删除不可恢复（属安全目标）。
