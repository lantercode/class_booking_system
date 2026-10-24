# F1.4 — Runtime Test Report

> Feature ID：F1.4
> 验证日期：2026-09-27
> 验证范围：acceptance.md AC-1 ~ AC-6
> 验证环境：macOS / Python 3.12.13 / pytest 9.0.3 / Docker Compose v2
> 验证方式：pytest 集成回归 + Settings 直调 + redis-py URL 解析直调 + compose 渲染

---

## 环境准备

| 组件 | 状态 |
|------|------|
| Python 3.12.13 + pytest（apps/api/.venv） | 就绪 |
| 本地 dev Redis（无密码） | 就绪（集成测试依赖） |
| Docker Compose CLI | 就绪（渲染验证用） |
| 生产环境 | 不可用（AC-1.2/AC-1.3 走替代验证 + 人工验收） |

---

## AC-1 生产 Redis 强制密码认证（主验收）

| 用例 | 结果 |
|------|------|
| AC-1.1 compose 含 `command: redis-server --requirepass ${REDIS_PASSWORD}` | **PASS**（代码审查 + 渲染验证） |
| AC-1.2 无密码 `redis-cli ping` → NOAUTH | **BLOCKED→替代验证 PASS**：本地无 prod 环境；`docker compose config` 渲染确认 `command` 插值正确，`requirepass` 为 Redis 官方指令，行为确定；留待部署窗口人工确认 |
| AC-1.3 正确密码 `redis-cli -a <pwd> ping` → PONG | **BLOCKED→替代验证 PASS**：healthcheck 渲染结果 `[CMD, redis-cli, -a, <pwd>, --no-auth-warning, ping]` 与官方用法一致 |

渲染实录（`REDIS_PASSWORD=super_secret_pwd_123` 测试值）：

```
command: [redis-server, --requirepass, super_secret_pwd_123]
healthcheck.test: [CMD, redis-cli, -a, super_secret_pwd_123, --no-auth-warning, ping]
api.environment.REDIS_URL: redis://:super_secret_pwd_123@redis:6379/0
```

**AC-1 结论：PASS（静态/渲染层）；运行时条款标记人工验收**

---

## AC-2 API 自动携带密码连接

| 用例 | 结果 |
|------|------|
| AC-2.1 api `REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0` | **PASS**（diff + 渲染验证） |
| AC-2.2 `REDIS_PASSWORD` 默认 `""`，env 注入生效 | **PASS**（直调：`Settings().REDIS_PASSWORD == ''`；`os.environ['REDIS_PASSWORD']=...` 后读取生效） |
| AC-2.3 `from_url` 解析含密码 URL | **PASS**（直调：`AsyncRedis.from_url('redis://:pwd@redis:6379/0').connection_pool.connection_kwargs['password'] == 'pwd'`，host/port/db 均正确） |

**AC-2 结论：PASS**

---

## AC-3 配置模板完备

| 用例 | 结果 |
|------|------|
| AC-3.1 `.env.example` 含 `REDIS_PASSWORD=` 空值 + 注释 | **PASS** |
| AC-3.2 `.env.prod.example` 存在且含关键占位符 | **PASS** |
| AC-3.3 无硬编码真实密码 | **PASS**（grep 全量扫描） |

**AC-3 结论：PASS**

---

## AC-4 敏感信息不泄露

| 用例 | 结果 |
|------|------|
| AC-4.1 `deps/auth.py` 无 print URL / 成功消息 | **PASS**（grep 无 `print` 残留） |
| AC-4.2 日志走 logger 且不含 URL | **PASS**（代码审查：debug 不含 URL；error 仅异常类型+消息） |
| AC-4.3 无硬编码密码 | **PASS** |

**AC-4 结论：PASS**

---

## AC-5 开发环境回归

| 用例 | 结果 |
|------|------|
| AC-5.1 dev compose 未修改 | **PASS**（`git diff --stat` 为空） |
| AC-5.2 现有 Redis 相关测试通过 | **PASS**（`test_auth_api.py` 15/15，覆盖 register/login/logout/黑名单全链路，实际读写本地无密码 Redis） |
| AC-5.3 dev `REDIS_URL` 默认值不变 | **PASS**（直调：`Settings().REDIS_URL == 'redis://localhost:6379/0'`） |

### 回归套件汇总

| 套件 | 结果 | 说明 |
|------|------|------|
| `tests/integration/test_auth_api.py` | 15 passed | 含 logout → access_token 黑名单 → Redis 读写路径 |
| `tests/test_exception_handlers.py` | 7 passed | F1.3 回归（config.py 同文件改动无副作用） |
| `tests/test_agent_runtime.py` | 5 passed | AI 回归 |

**AC-5 结论：PASS（32/32）**

---

## AC-6 变更范围（静态）

| 用例 | 结果 |
|------|------|
| AC-6.1 实际修改文件 ⊆ 白名单 | **PASS** |
| AC-6.2 py_compile | **PASS**（2 个 Python 文件） |
| AC-6.3 yaml 语法检查 | **PASS**（`yaml.safe_load` × 2 + `docker compose config`） |

**AC-6 结论：PASS**

---

## 汇总判定

| AC | 判定 |
|----|------|
| AC-1 prod compose `requirepass` | **PASS**（AC-1.2/AC-1.3 运行时条款留人工验收） |
| AC-2 API 自动携带密码 | **PASS** |
| AC-3 模板完备 | **PASS** |
| AC-4 不泄露 | **PASS** |
| AC-5 dev 回归 | **PASS** |
| AC-6 变更范围 | **PASS** |

---

## 结论

**Runtime Test：PASS**

- 本地可验证条款全部通过：dev 环境 32/32 测试无回归，配置字段与 URL 解析行为符合预期。
- 仅 AC-1.2/AC-1.3（真实 prod Redis 的 NOAUTH/PONG）因本地无生产环境标记为人工验收项，已提供 `docker compose config` 渲染证据与官方指令语义作为替代验证。
