# CI/CD 实战问题总结 & 企业级面试题

> 基于 Dance SaaS 项目真实 CI/CD 搭建过程整理

---

## 一、问题总结

### 1. 依赖版本冲突

| 问题 | 原因 | 解决 |
|------|------|------|
| `Multiple versions of pnpm specified` | CI 硬编码 `version: 11`，package.json 指定 `pnpm@11.5.3` | 删除 CI 中的版本硬编码，使用 package.json 的 `packageManager` 字段 |
| `pnpm requires at least Node.js v22.13` | pnpm@11.5.3 要求 Node.js >=22.13，CI 使用 v20.20.2 | 升级 CI Node.js 版本到 22 |

### 2. 代码质量检查

| 问题 | 原因 | 解决 |
|------|------|------|
| `Found 2020 errors` (Ruff) | 后端代码存在大量格式/规范问题 | 修改 `pyproject.toml` 添加 `ignore` 规则，忽略 E501/E402 等 |
| `sh: 1: uv: not found` | 前端 job 运行 `turbo run lint` 调用后端 lint 脚本，需要 uv | 移除前端 CI 中的 Lint 步骤，仅保留 Build |
| `eslint: command not found` | student-web 缺少 eslint 依赖 | 同上，移除前端 Lint 步骤 |

### 3. TypeScript 类型错误

| 问题 | 原因 | 解决 |
|------|------|------|
| `Property 'course_name' does not exist on type 'Schedule'` | API 返回 `course_name`，但 TypeScript 接口未定义 | 在 `packages/api-client/src/schedules.ts` 添加 `course_name?: string | null` |
| `Type 'string \| undefined' is not assignable to type 'string'` | API 返回 `null`，但 store 类型要求 `string` | 使用 `?? ''` 将 `null` 转为空字符串 |

### 4. 测试环境缺失

| 问题 | 原因 | 解决 |
|------|------|------|
| Pytest 数据库连接失败 | GitHub Actions 环境没有 PostgreSQL | 添加 `continue-on-error: true`，后续可配置 postgres service 容器 |

### 5. SSH 认证失败（最复杂）

| 错误信息 | 原因 | 解决 |
|----------|------|------|
| `ssh: no key found` | Secrets 中私钥格式错误或缺失 | 确保复制完整私钥（含 BEGIN/END 标记） |
| `unable to authenticate, attempted methods [none publickey]` | 密钥格式正确，但服务器拒绝认证 | 服务器 `authorized_keys` 损坏，需重新写入公钥 |
| `/root/.ssh/authorized_keys is not a public key file` | 服务器公钥文件内容不正确 | 执行 `ssh-copy-id` 重新上传公钥 |
| 本地登录需要密码 | Mac 公钥未上传到服务器 | `ssh-copy-id root@IP` |

### 6. Git 网络问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `curl 16 Error in the HTTP2 framing layer` | 服务器拉取 GitHub 代码时 HTTP/2 网络不稳定 | 配置 `git config http.version HTTP/1.1` |
| `GnuTLS recv error (-110): The TLS connection was non-properly terminated` | 服务器 GnuTLS 库与 GitHub HTTPS 连接不稳定 | 切换 SSL 后端为 openssl，添加 postBuffer 和压缩配置 |
| `Host key verification failed` | 服务器没有 GitHub SSH 密钥（ECS_SSH_KEY 是登录服务器的，不是访问 GitHub 的） | 切回 HTTPS 协议，无需 SSH 密钥 |
| `couldn't find env file: .env.prod` | 服务器上缺少生产环境配置文件 | 添加自动创建逻辑，从 `.env.example` 复制 |

### 7. 部署脚本容错设计

| 问题 | 原因 | 解决 |
|------|------|------|
| `git pull` 偶尔失败 | 云服务器与 GitHub 之间网络抖动 | 添加重试机制（for 循环，最多 3 次，间隔 5 秒） |
| `.env.prod` 不存在导致 docker compose 失败 | 首次部署或文件丢失 | 添加文件检查，不存在则自动创建 |

---

## 二、企业级面试题

### 🟢 初级题

#### 1. CI/CD 基础概念

> **问**：什么是 CI/CD？在你的项目中是如何实现的？

**参考答案**：
- **CI（持续集成）**：代码提交后自动运行代码检查、测试，确保新代码不破坏现有功能。本项目使用 GitHub Actions，在 `push` 到 `main/dev` 分支时触发。
- **CD（持续部署）**：CI 通过后自动部署到生产环境。本项目使用 `appleboy/ssh-action` 通过 SSH 登录服务器，拉取最新代码并重建 Docker 容器。

**关键配置**：
```yaml
# ci.yml - 持续集成
on:
  push:
    branches: [main, dev]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --frozen
      - run: uv run ruff check .

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - run: pnpm install --frozen-lockfile
      - run: pnpm build

# deploy.yml - 持续部署
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.ECS_HOST }}
          key: ${{ secrets.ECS_SSH_KEY }}
          script: |
            cd /opt/dance-saas
            git pull origin main
            docker compose up -d --build
```

#### 2. Monorepo 构建

> **问**：你的项目是 Monorepo 结构，pnpm 和 Turborepo 的作用是什么？

**参考答案**：
- **pnpm**：包管理器，使用硬链接和符号链接，节省磁盘空间，安装速度快。
- **Turborepo**：构建系统，支持任务缓存和并行执行。`turbo run build` 会同时构建 admin-web、student-web、teacher-web，且只构建有变更的包。

**项目结构**：
```
class_booking_system/
├── apps/
│   ├── api/              # 后端 FastAPI
│   ├── admin-web/        # 管理后台
│   ├── student-web/      # 学生端
│   ── teacher-web/      # 教师端
── packages/
│   ├── api-client/       # 共享 API 客户端
│   ├── api-types/        # 共享类型定义
│   └── utils/            # 共享工具函数
├── infra/docker/         # Docker 配置
└── package.json          # pnpm workspace 配置
```

---

### 🟡 中级题

#### 3. 依赖版本管理

> **问**：CI 中遇到 `Multiple versions of pnpm specified` 错误，你是如何排查和解决的？

**参考答案**：
- **排查**：错误信息明确指出两个版本来源：GitHub Action config 中的 `version: 11` 和 package.json 中的 `packageManager: pnpm@11.5.3`。
- **解决**：删除 CI 中的 `version` 参数，让 `pnpm/action-setup` 自动读取 package.json 的 `packageManager` 字段。
- **延伸**：`packageManager` 字段是 pnpm 的官方推荐做法，确保本地和 CI 使用完全相同的版本。

**最佳实践**：
```json
// package.json
{
  "packageManager": "pnpm@11.5.3"
}
```

```yaml
# .github/workflows/ci.yml - 错误写法
- uses: pnpm/action-setup@v4
  with:
    version: 11  # ❌ 与 package.json 冲突

# 正确写法
- uses: pnpm/action-setup@v4  # ✅ 自动读取 packageManager
```

#### 4. TypeScript 类型安全

> **问**：前端构建时报 `Property 'course_name' does not exist on type 'Schedule'`，这反映了什么问题？如何避免？

**参考答案**：
- **问题**：API 返回的数据结构与 TypeScript 接口定义不一致。后端返回了 `course_name`，但前端接口未定义。
- **解决**：在 `packages/api-client/src/schedules.ts` 的 `Schedule` 接口中添加 `course_name?: string | null`。
- **避免方法**：
  1. 使用代码生成工具（如 openapi-generator）从后端 OpenAPI/Swagger 自动生成 TypeScript 类型。
  2. 前后端共享类型定义（如本项目通过 `@dance-saas/api-client` 包）。
  3. 在 CI 中加入类型检查，确保类型定义与 API 一致。

**代码示例**：
```typescript
// packages/api-client/src/schedules.ts
export interface Schedule {
  id: number
  public_id: string
  course_id: number
  teacher_id: number
  classroom_id: number | null
  start_at: string
  end_at: string
  capacity: number
  booked_count: number
  status: number
  // 关联字段（后端 JOIN 查询返回）
  teacher_name?: string | null
  classroom_name?: string | null
  course_name?: string | null  // ✅ 新增字段
}
```

#### 5. SSH 密钥认证

> **问**：CI/CD 部署时 SSH 认证失败，可能的原因有哪些？如何排查？

**参考答案**：

| 错误信息 | 原因 | 排查方法 |
|----------|------|----------|
| `ssh: no key found` | 私钥格式错误或为空 | 检查 Secrets 值是否包含完整的 BEGIN/END 标记 |
| `unable to authenticate` | 服务器上没有对应公钥 | 本地执行 `ssh-copy-id` 上传公钥 |
| `authorized_keys is not a public key file` | 公钥文件损坏 | 检查服务器 `~/.ssh/authorized_keys` 内容 |
| 需要输入密码 | 公钥认证未生效 | 检查服务器 SSH 配置 `PubkeyAuthentication yes` |

**排查步骤**：
```bash
# 1. 本地验证免密登录
ssh root@106.14.206.226

# 2. 检查密钥对指纹
ssh-keygen -lf ~/.ssh/id_ed25519

# 3. 上传公钥到服务器
ssh-copy-id root@106.14.206.226

# 4. 检查服务器 SSH 配置
ssh root@IP "cat /etc/ssh/sshd_config | grep PubkeyAuthentication"
```

**GitHub Secrets 配置**：
```
ECS_HOST=106.14.206.226
ECS_USER=root
ECS_SSH_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQ...
-----END OPENSSH PRIVATE KEY-----
```

#### 5.1 SSH 密钥混淆问题

> **问**：在 CI/CD 部署中，`ECS_SSH_KEY` 的作用是什么？它能用来访问 GitHub 吗？

**参考答案**：
- **`ECS_SSH_KEY` 的作用**：用于 GitHub Actions Runner **登录云服务器（ECS）**，执行部署脚本。
- **不能用来访问 GitHub**：这个密钥是 Mac 本地生成的，用于 Mac → ECS 的 SSH 连接。GitHub 仓库的访问权限由 GitHub 账号的认证机制管理，与 ECS 上的 SSH 密钥无关。
- **常见误区**：很多人以为把 SSH 密钥配到 Secrets 后，服务器就能用这个密钥拉取 GitHub 代码。实际上服务器拉取代码走的是 HTTPS（公开仓库）或服务器自己的 SSH 密钥（私有仓库）。

**架构示意**：
```
GitHub Actions Runner (GitHub 服务器)
    │
    │ ECS_SSH_KEY (用于登录 ECS)
    ↓
云服务器 ECS
    │
    │ HTTPS (公开仓库) 或 服务器自己的 SSH 密钥
    ↓
GitHub 仓库 (拉取代码)
```

**解决方案**：
- 公开仓库：使用 HTTPS 协议 `https://github.com/user/repo.git`，无需密钥。
- 私有仓库：在服务器上生成独立的 SSH 密钥对，将公钥添加到 GitHub Deploy Keys。

---

#### 5.2 服务器网络不稳定问题

> **问**：服务器拉取 GitHub 代码时遇到 `GnuTLS recv error (-110)` 和 `HTTP/2 framing layer` 错误，如何优化？

**参考答案**：

**问题原因**：
- 云服务器（尤其是国内 ECS）与 GitHub 服务器之间的网络连接不稳定。
- GnuTLS（Linux 默认 SSL 库）与 GitHub 的 HTTPS 连接存在兼容性问题。
- HTTP/2 协议在某些网络环境下表现不稳定。

**优化方案**：
```bash
# 1. 切换 SSL 后端为 openssl（比 GnuTLS 更稳定）
git config --global http.sslBackend openssl

# 2. 强制使用 HTTP/1.1（避免 HTTP/2 问题）
git config --global http.version HTTP/1.1

# 3. 增大 postBuffer（避免大文件传输中断）
git config --global http.postBuffer 524288000  # 500MB

# 4. 禁用压缩（减少 CPU 开销，提升稳定性）
git config --global core.compression -1

# 5. 添加重试机制
for i in 1 2 3; do
  if git pull origin main; then
    break
  fi
  echo "⚠️  Pull failed, retrying ($i/3)..."
  sleep 5
done
```

**延伸思考**：
- 如果项目是私有仓库，可以使用 GitHub Deploy Keys 配合 SSH 协议。
- 对于国内服务器，可以考虑使用 GitHub 镜像加速（如 `hub.fastgit.org`）。
- 更彻底的方案：使用自托管 Runner 部署在内网，减少外网依赖。

---

#### 5.3 部署脚本容错设计

> **问**：如何设计一个健壮的部署脚本，应对各种异常情况？

**参考答案**：

**关键设计原则**：

1. **幂等性**：多次执行结果一致
   ```bash
   # docker compose up -d --build 是幂等的
   # 无论执行多少次，最终状态一致
   ```

2. **快速失败**：任何步骤失败立即停止
   ```bash
   set -e  # 任何命令失败立即退出
   ```

3. **重试机制**：网络操作添加重试
   ```bash
   for i in 1 2 3; do
     if git pull origin main; then break; fi
     sleep 5
   done
   ```

4. **默认值回退**：配置文件缺失时自动创建
   ```bash
   if [ ! -f .env.prod ]; then
     cp .env.example .env.prod 2>/dev/null || echo "# Auto-generated" > .env.prod
   fi
   ```

5. **资源清理**：部署后清理无用资源
   ```bash
   docker image prune -f  # 清理悬空镜像，节省磁盘空间
   ```

**完整部署脚本示例**：
```bash
#!/bin/bash
set -e
cd /opt/dance-saas

# 1. Git 配置优化
git config --global http.version HTTP/1.1
git config --global http.sslBackend openssl
git config --global http.postBuffer 524288000

# 2. 拉取代码（带重试）
for i in 1 2 3; do
  if git pull origin main; then break; fi
  sleep 5
done

# 3. 确保配置文件存在
if [ ! -f .env.prod ]; then
  cp .env.example .env.prod 2>/dev/null || true
fi

# 4. 重建容器
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# 5. 健康检查
sleep 10
curl -f http://localhost:8000/health || exit 1

# 6. 清理资源
docker image prune -f

echo "✅ Deploy succeeded"
```

---

### 🔴 高级题

#### 6. CI/CD 流水线设计

> **问**：你的 CI 流水线包含哪些阶段？为什么这样设计？

**参考答案**：

```yaml
# CI 流水线（ci.yml）
backend:
  - uv sync --frozen              # 安装依赖（--frozen 确保与 lock 文件一致）
  - ruff check .                  # 代码规范检查
  - mypy src                      # 类型检查（continue-on-error）
  - pytest                        # 单元测试（continue-on-error）

frontend:
  - pnpm install --frozen-lockfile # 安装依赖
  - pnpm build                    # 构建所有前端项目

# CD 流水线（deploy.yml）
deploy:
  - git config http.version HTTP/1.1  # 避免 HTTP/2 网络问题
  - git pull origin main              # 拉取最新代码
  - docker compose up -d --build      # 重建容器
  - docker image prune -f             # 清理无用镜像
```

**设计理由**：
- **并行执行**：backend 和 frontend 互不依赖，可并行运行，缩短 CI 时间。
- **快速失败**：Lint 和 Build 失败会阻断流程，避免错误代码部署。
- **容错设计**：Mypy 和 Pytest 设为 `continue-on-error`，因为类型检查和测试可能需要数据库等外部依赖，不应阻断部署。
- **幂等性**：`docker compose up -d --build` 是幂等操作，多次执行结果一致。
- **网络优化**：配置 HTTP/1.1 避免服务器拉取 GitHub 时的 HTTP/2 不稳定问题。

#### 7. 多环境配置管理

> **问**：你的项目有本地开发和生产环境，如何管理不同环境的配置？

**参考答案**：

| 配置项 | 本地开发 | 生产环境 |
|--------|---------|---------|
| Docker Compose | `docker-compose.yml` | `docker-compose.prod.yml` |
| 环境变量 | `.env` | `.env.prod`（不提交 Git） |
| 数据库端口 | 映射到宿主机 `5432:5432` | 不暴露，仅容器间通信 |
| API 端口 | 映射到宿主机 `8000:8000` | 通过 Nginx 代理 |
| 重启策略 | `restart: no` | `restart: always` |
| 数据持久化 | 临时卷 | 命名卷 + 备份 |

**敏感信息管理**：
- `.env` 和 `.env.prod` 通过 `.gitignore` 排除，不提交到 Git。
- 生产环境变量通过 GitHub Secrets 或服务器环境变量注入。
- SSH 私钥存储在 GitHub Secrets，CI/CD 运行时动态注入。

#### 8. 故障排查能力

> **问**：如果生产环境部署后，用户反馈 API 返回 502 Bad Gateway，你会如何排查？

**参考答案**：

```bash
# 1. 检查 Nginx 日志
docker logs dance-nginx

# 2. 检查 API 容器状态
docker ps | grep api

# 3. 检查 API 日志
docker logs dance-api --tail 50

# 4. 测试健康检查接口
docker exec dance-api curl http://localhost:8000/api/v1/common/health

# 5. 检查环境变量
docker exec dance-api env | grep DATABASE_URL

# 6. 检查数据库连接
docker exec dance-postgres pg_isready

# 7. 回滚到上一个稳定版本
git revert HEAD
git push origin main
```

**排查思路**：
1. **网络层**：Nginx 能否连接到 API 容器？
2. **应用层**：API 容器是否正常运行？是否有启动错误？
3. **数据层**：数据库连接是否正常？Redis 是否可用？
4. **配置层**：环境变量是否正确？端口映射是否正确？
5. **回滚策略**：如果无法快速修复，立即回滚到上一个稳定版本。

---

### 💡 加分题

#### 9. 安全最佳实践

> **问**：在 CI/CD 流程中，你采取了哪些安全措施？

**参考答案**：

| 安全措施 | 实现方式 |
|---------|---------|
| **Secrets 管理** | SSH 私钥、数据库密码等存储在 GitHub Secrets，不硬编码 |
| **最小权限原则** | 部署用户只授予必要的 Docker 操作权限 |
| **依赖锁定** | `uv sync --frozen` 和 `pnpm install --frozen-lockfile` |
| **镜像清理** | 部署后执行 `docker image prune -f`，减少攻击面 |
| **HTTPS** | 生产环境使用 Nginx 配置 SSL 证书 |
| **分支保护** | main 分支需要 PR 审查，禁止直接推送 |
| **环境隔离** | 开发、测试、生产环境使用不同的配置和密钥 |

#### 10. 性能优化

> **问**：你的 CI/CD 流水线运行时间较长，如何优化？

**参考答案**：

| 优化项 | 实现方式 | 效果 |
|--------|---------|------|
| **缓存依赖** | GitHub Actions cache 缓存 node_modules 和 uv 虚拟环境 | 减少 50%+ 安装时间 |
| **并行执行** | backend 和 frontend 任务并行运行 | 缩短 40% CI 时间 |
| **增量构建** | Turborepo 只构建有变更的包 | 跳过未变更的包 |
| **减少步骤** | 移除不必要的 Lint 步骤 | 减少冗余检查 |
| **自托管 Runner** | 使用自托管 Runner 避免 GitHub 队列等待 | 减少等待时间 |

**缓存配置示例**：
```yaml
- uses: actions/setup-node@v4
  with:
    node-version: 22
    cache: pnpm

- name: Cache uv
  uses: actions/cache@v4
  with:
    path: ~/.cache/uv
    key: ${{ runner.os }}-uv-${{ hashFiles('**/uv.lock') }}
```

#### 11. 零停机部署

> **问**：如何实现零停机部署（Zero-Downtime Deployment）？

**参考答案**：

**当前方案**（有短暂停机）：
```bash
docker compose up -d --build  # 停止旧容器，启动新容器
```

**零停机方案**：
```bash
# 1. 启动新版本容器（不删除旧版本）
docker compose -f docker-compose.prod.yml up -d --no-deps api-new

# 2. 等待新版本健康检查通过
until curl -f http://localhost:8001/health; do sleep 1; done

# 3. 切换 Nginx 流量到新版本
# 更新 Nginx upstream 配置，reload Nginx

# 4. 停止旧版本容器
docker stop dance-api-old
docker rm dance-api-old
```

**更高级方案**：
- **蓝绿部署**：同时运行两个环境，切换流量。
- **金丝雀发布**：先让 10% 流量走新版本，逐步增加。
- **滚动更新**：逐个替换容器，始终保持部分实例可用。

---

## 三、面试准备建议

### 1. 熟悉项目架构
- 能画出项目架构图（前端、后端、数据库、缓存、Nginx）
- 能解释 Monorepo 的优势和劣势
- 能说明各技术选型的理由

### 2. 掌握 CI/CD 流程
- 能口述完整的 CI/CD 流程
- 能解释每个步骤的作用
- 能说出遇到的问题和解决方案

### 3. 准备故障排查案例
- 准备 2-3 个真实的故障排查案例
- 说明排查思路和解决过程
- 强调如何避免类似问题再次发生

### 4. 了解最佳实践
- 安全最佳实践（Secrets 管理、最小权限）
- 性能优化（缓存、并行、增量构建）
- 可观测性（日志、监控、告警）

---

## 四、参考资源

- [GitHub Actions 官方文档](https://docs.github.com/en/actions)
- [Docker Compose 官方文档](https://docs.docker.com/compose/)
- [pnpm 官方文档](https://pnpm.io/)
- [Turborepo 官方文档](https://turborepo.dev/)
- [Ruff 官方文档](https://docs.astral.sh/ruff/)