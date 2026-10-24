# F1.4 — Static Verification

> 阶段：STATIC VERIFICATION
> 日期：2026-09-27

## 1. 范围守卫（minimal-change-guard）

### 1.1 白名单

```
infra/docker/docker-compose.prod.yml
apps/api/src/app/core/config.py
apps/api/src/app/deps/auth.py
.env.example
.env.prod.example（新建）
docs/features/F1.4-redis-password-auth/（新建交付物）
```

### 1.2 范围复核结论

- 5 个目标文件均在 `git status` 中（4 修改 + 1 新建）
- 工作区存在大量 F1.1/F1.2/F1.3/F1.5/F3.x 等预存未提交改动；本 Feature 的 diff 经逐文件审查，仅在白名单文件内产生增量，未触碰其他文件
- `git diff --check`（4 个修改文件）→ 无空白错误
- dev `docker-compose.yml` `git diff --stat` 为空 → 未修改

### 1.3 逐文件 diff 审查

- **docker-compose.prod.yml**：仅 3 处增量（redis `command` 一行、healthcheck `test` 一行、api `REDIS_URL` 一行）
- **config.py**：仅新增注释一行 + `REDIS_PASSWORD: str = ""` 一行（diff 中 `APP_DEBUG`/`PERMISSION_CHECK_BYPASS` 差异为 F1.3/F1.1 预存改动）
- **deps/auth.py**：新增 `import logging` + 模块级 `logger`；`get_redis_client` 内 3 处 print 替换为 logger；移除仅为 print 服务的重复 `ping()`（diff 中黑名单逻辑、函数位置差异为 F1.2 预存改动）
- **.env.example**：仅新增 `REDIS_PASSWORD=` 两行（注释 + 空值）（diff 中 `PERMISSION_CHECK_BYPASS` 块为预存改动）
- **.env.prod.example**：新建模板，全部占位符，无真实机密

## 2. 编译验证

| 文件 | py_compile |
|------|-----------|
| `apps/api/src/app/core/config.py` | OK |
| `apps/api/src/app/deps/auth.py` | OK |

## 3. YAML 语法验证

| 文件 | `yaml.safe_load` | `docker compose config` |
|------|------------------|-------------------------|
| `infra/docker/docker-compose.prod.yml` | OK | OK（变量缺失时输出 warning，非静默失败） |
| `infra/docker/docker-compose.yml`（dev，未修改） | OK | — |

## 4. 渲染验证（变量插值）

以 `REDIS_PASSWORD=super_secret_pwd_123`（测试值）渲染 prod compose：

```yaml
redis:
  command: [redis-server, --requirepass, super_secret_pwd_123]
  healthcheck:
    test: [CMD, redis-cli, -a, super_secret_pwd_123, --no-auth-warning, ping]
api:
  environment:
    REDIS_URL: redis://:super_secret_pwd_123@redis:6379/0
```

三处 `${REDIS_PASSWORD}` 插值全部正确。

## 5. 敏感信息扫描

| 检查项 | 结果 |
|--------|------|
| `deps/auth.py` 残留 `print` | 无（仅剩注释中提到 REDIS_URL，无输出语句） |
| 全仓库 `REDIS_PASSWORD` 出现位置 | 仅 compose 插值引用、`.env.example` 空值、`.env.prod.example` 占位符、`config.py` 默认空 — 无真实密码 |
| 其他 Redis 相关 print（main.py / auth/service.py） | 存在但不含 URL/密码，非泄露面，不在本 Feature scope |
| `.env.prod` 真实机密文件 | 已被 `.gitignore` L27 覆盖，不会入库 |

## 6. 连接点唯一性核查

全 `apps/api/src` 扫描 `from_url` / `Redis(` / `redis.asyncio` / `REDIS_URL`：仅 `deps/auth.py:26` 一处创建连接，其余（security.py 黑名单、rbac/checker.py 缓存）均通过依赖注入复用该客户端 → URL 带密码即全链路带密码，无绕过路径。

## 7. 静态结论

| AC | 判定 |
|----|------|
| AC-1.1 compose `requirepass` | PASS |
| AC-2.1 api `REDIS_URL` 带密码 | PASS |
| AC-2.2 `REDIS_PASSWORD` 字段 | PASS |
| AC-3.1 ~ AC-3.3 模板与硬编码 | PASS |
| AC-4.1 ~ AC-4.3 日志不泄露 | PASS |
| AC-5.1 dev compose 未修改 | PASS |
| AC-6.1 变更范围 ⊆ 白名单 | PASS |
| AC-6.2 py_compile | PASS |
| AC-6.3 yaml 语法 | PASS |
