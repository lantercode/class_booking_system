# 项目实战问题记录 & 面试问答

> class_booking_system 开发过程中的真实问题排查与解决方案

**图例**：🎤 = 面试背诵（真实问题排查 + 面试问答）　🔧 = 待开发任务（后续计划）　📋 = 速查备忘

---

## 目录

| 序号 | 标签 | 问题 | 涉及技术 |
|------|------|------|---------|
| 一 | 🎤 | [Docker 容器间通信 — RedisInsight 连不上 Redis](#一docker-容器间通信--redisinsight-连不上-redis) | 网络隔离、host.docker.internal |
| 二 | 🎤 | [本地开发微信登录报 IP 不在白名单](#二本地开发微信登录报-ip-不在白名单) | 公网出口 IP、代理、微信平台安全 |
| 三 | 🎤 | [个人版小程序 getPhoneNumber 不可用](#三个人版小程序-getphonenumber-不可用) | 小程序主体类型、前端降级 |
| 四 | 🎤 | [FastAPI 307 重定向导致 401 未认证](#四fastapi-307-重定向导致-401-未认证) | redirect_slashes、axios header 丢失 |
| 五 | 📋 | [环境速查 — pnpm workspace / Redis 连接](#五环境速查--pnpm-workspace--redis-连接) | 开发工具 |
| 六 | 🔧 | [业务错误码体系](#六业务错误码体系) | 状态码设计、架构规范 |
| 七 | 🔧 | [CI/CD 接入计划](#七cicd-接入计划) | GitHub Actions、自动化测试部署 |
| 八 | 🎤 | [微信小程序页面栈溢出与 iOS 真机渲染问题](#八-微信小程序页面栈溢出与-ios-真机渲染问题) | 页面栈、合成层、scroll-view、iOS兼容 |
| 九 | 🎤 | [生产部署实战复盘 → 企业级面试知识图谱](#九-生产部署实战复盘--企业级面试知识图谱) | Docker/GitOps/Nginx/多租户/JWT 全栈 |
| 十 | 🎤 | [CI/CD 部署成功但浏览器端数据不是最新](#十cicd-部署成功但浏览器端数据不是最新) | 浏览器缓存、Nginx Cache-Control、Vite 文件名哈希 |


---

---

## 一 🎤 Docker 容器间通信 — RedisInsight 连不上 Redis

### 现象

RedisInsight 容器中填 `Host: 127.0.0.1, Port: 6379`，测试连接失败。但从宿主机 `redis-cli ping` 正常。

### 原因

`127.0.0.1` 在容器内指向容器自身，不是宿主机。RedisInsight 和 Redis 都在 Docker 容器中，用了错误地址。

### 解决

把 `Host` 改为 `host.docker.internal`（Docker Desktop 提供的特殊 DNS，容器内访问宿主机用）。

### 面试要点

- **容器网络隔离**：每个容器有独立网络命名空间，`127.0.0.1` 指向自身
- **host.docker.internal**：Docker Desktop 专有，容器访问宿主机的标准方式。Linux 需手动添加 `--add-host`
- **端口映射方向性**：只对"外部→容器"生效，不对"容器内部→宿主机"生效
- **Bridge 网络**：Docker 默认网络模式，通过虚拟网桥 `docker0` 连接容器，内部用 172.17.x.x 通信
- **排查方法**：确认容器运行 → 确认端口监听 → 测试服务可用性 → 分析网络拓扑

---

## 二 🎤 本地开发微信登录报 IP 不在白名单

### 现象

后端本地启动（localhost:8000），调用微信 `jscode2session` 返回：
```
"微信登录失败：invalid ip 116.169.1.54, not in whitelist"
```

### 原因

后端调用微信 API 是**出站请求**，微信看到的是你网络链路的公网出口 IP，不是 `127.0.0.1`。

### 解决

1. 终端执行 `curl -4 ifconfig.me` 获取公网 IPv4 地址
2. 登录微信公众平台 → 开发管理 → 开发设置 → IP 白名单 → 添加该 IP
3. 等几分钟生效

### 面试要点

- **为什么终端 curl 和浏览器查到的 IP 不同？** 浏览器可能走了代理，出口 IP 是代理服务器的。后端 `httpx` 走系统直连，和终端 `curl -4` 一致，以终端结果为准
- **微信为什么要求 IP 白名单？** 防止 AppSecret 泄露后被恶意调用，安全基线要求
- **本地 IP 不固定怎么办？** 家庭宽带是动态 IP，每次变更后手动添加，或部署到固定 IP 的云服务器

---

## 三 🎤 个人版小程序 getPhoneNumber 不可用

### 现象

用户点击「微信手机号一键授权」报错：
```
getPhoneNumber:fail operateWXData:fail jsapi has no permission
```

### 原因

个人主体注册的小程序不支持 `getPhoneNumber` 接口，该接口需要企业/组织主体。

### 解决

**前端降级**：检测 `no permission` 错误后自动跳转手动输入手机号页面：

```ts
if (e.detail.errMsg?.includes('no permission')) {
  uni.showToast({ title: '请手动输入手机号', icon: 'none' })
  setTimeout(() => goToManualBind(), 1200)
}
```

### 面试要点

- **个人版 vs 企业版**：个人版免费但接口受限（无 getPhoneNumber、微信支付），企业版需营业执照 + 300元/年认证
- **降级策略**：前端检测权限错误 → 自动切换手动输入 → 后端 `/auth/wechat-login` 支持手动绑定
- **长期方案**：注册企业版小程序

---

## 四 🎤 FastAPI 307 重定向导致 401 未认证

### 现象

管理后台已登录，但接口请求报：
```
GET /api/v1/users?page=1&page_size=10  → 307 Temporary Redirect
GET /api/v1/users/?page=1&page_size=10 → 401 Unauthorized
```

### 原因

```
前端请求:  GET /api/v1/users     ← 没带 /
后端路由:  @router.get("/") + prefix="/users" → /api/v1/users/  ← 带了 /
                                                                  ↑
Starlette 默认 redirect_slashes=True → 自动 307 重定向
重定向时 axios 创建新请求，不会复制 Authorization header → 401
```

### 解决

**方案一（推荐）**：前端 API 路径统一加尾部 `/`

**方案二**：后端 `FastAPI(redirect_slashes=False)`，所有 `@router.get("/")` 改为 `@router.get("")`

### 面试要点

- **Starlette 默认行为**：`redirect_slashes=True` 会纠正 URL 尾部斜杠，自动 307 重定向
- **为什么 307 会丢 Authorization？** axios 重定向时创建新请求，不复制自定义 header；跨域重定向浏览器也会剥离
- **307 vs 302**：307 保持原始 HTTP 方法（POST 还是 POST），302 会变成 GET
- **预防措施**：前后端约定 URL 风格（统一带 `/` 或不带 `/`），或使用 OpenAPI 自动生成 API 客户端

---

## 五 📋 环境速查

### pnpm workspace

`pnpm install` 在根目录跑一次，自动给 `apps/*` 和 `packages/*` 都装好，这是 workspace 的好处。

使用 `workspace:*` 协议声明本地包依赖，pnpm 用符号链接连接，改一处所有项目生效。

### Redis 连接

容器间访问 Redis 用 `host.docker.internal`，不能用 `127.0.0.1`。

---

## 六 🔧 业务错误码体系

> 当前 HTTP 状态码和业务错误码混用，所有业务校验失败统一返回 `400`，前端只能靠 `msg` 字符串匹配区分错误，不可靠。后续应引入 5 位业务错误码（`XXYYY`，前 2 位模块 + 后 3 位子码），与 HTTP 状态码解耦：HTTP 状态码给拦截器做流程控制（401 跳登录、403 无权限），业务码给页面做精准 UI 反馈（33003 弹窗推荐其他排期、33006 toast 提示重复预约）。详见 `class_booking_system_plan.md` 5.1 节。

---

## 七 🔧 CI/CD 接入计划

> 当前项目没有 CI/CD，所有质量检查（lint、test、build）依赖手动执行。`package.json` 中已有 `lint`/`test`/`build` 脚本，接入 GitHub Actions 只需新增一个 workflow 文件。

### 接入步骤

| Step | 内容 | 工时 |
|------|------|------|
| 1 | 新增 `.github/workflows/ci.yml`，每次 push/PR 自动跑 lint + test | 0.5h |
| 2 | Python 后端接入 `ruff check` + `pytest --cov` | 0.5h |
| 3 | 前端接入 `pnpm lint` + `pnpm typecheck` | 0.5h |
| 4 | 新增 `.github/workflows/deploy.yml`，main 分支 push 自动部署 | 2h |

### 面试要点

- **CI/CD 是什么？** CI（持续集成）= 每次提代码自动跑检查，CD（持续部署）= 检查通过后自动上线。本质是通过自动化消除人工操作的低效和失误。
- **为什么需要 CI/CD？** 没有的话代码质量靠人肉保证（容易遗漏），上线靠手动 SSH（半夜容易搞错）。有 CI/CD 后，`git push` 一条命令完成检查+部署。
- **GitHub Actions 的工作原理？** 在 `.github/workflows/*.yml` 中定义事件（push/PR）→ 触发 job → 在 GitHub 提供的虚拟机中依次执行 steps → 全部通过即成功，任何一步失败即终止。

---

## 八 🎤 微信小程序页面栈溢出与 iOS 真机渲染问题

### 问题一：连续切换页面卡死

**现象**：Tab 之间连续切换约 10 次后，界面卡死，点击无反应。

**根因**：Tab 切换使用了 `uni.navigateTo`（push 新页面），页面栈上限 10 层，超限后静默失败。同时路由比较逻辑有 bug（`url.replace('/pages/', '').replace('/index', '')` 结果带尾部 `/`，与 `currentPage.route` 永远不匹配），防重复跳转完全失效。

**解决**：目标页已在栈中时 `navigateBack` 返回，否则 `redirectTo` 替换当前页。页面栈始终保持在 1-2 层。

```js
const goTo = (url) => {
  const pages = getCurrentPages()
  const targetRoute = url.replace(/^\//, '').replace(/\/index$/, '')
  if (currentPage.route === targetRoute) return
  if (pages.some(p => p.route === targetRoute)) {
    const delta = pages.length - 1 - pages.findIndex(p => p.route === targetRoute)
    uni.navigateBack({ delta })
  } else {
    uni.redirectTo({ url })
  }
}
```

### 面试要点 — 页面栈

| API | 行为 | 页面栈变化 | 适用场景 |
|-----|------|-----------|---------|
| `navigateTo` | 打开新页，保留当前 | push +1 | 列表→详情 |
| `redirectTo` | 关闭当前，打开新页 | replace | Tab 切换 |
| `navigateBack` | 返回上一页或多页 | pop -delta | 返回 |
| `switchTab` | 跳转 tabBar 页面 | 清空→目标页 | Tab 切换 |
| `reLaunch` | 关闭所有，打开新页 | 清空→1 层 | 登录后跳转首页 |

- **页面栈上限 10 层**，超限后 `navigateTo` 静默失败（不报错、不跳转）
- `navigateTo` / `redirectTo` 不能跳转 tabBar 页面，只能用 `switchTab`
- 排查：`getCurrentPages().length` 查看当前栈深度

### 问题二：iOS 真机 scroll-view 内容不显示

**现象**：课程详情页数据已查询成功（console 有日志），但 iOS 真机上 scroll-view 区域空白。

**根因**：详情页使用了双层 flex 嵌套（`scroll-wrapper` → `scroll-view`），iOS 上原生 `scroll-view` 组件需要**显式 px 高度**，`flex: 1; height: 0` 的 CSS 技巧在 iOS 真机上高度塌陷为 0。

**解决**：用 `uni.getSystemInfoSync()` 动态计算可用高度，设为内联 px 样式。

```js
const systemInfo = uni.getSystemInfoSync()
const heroHeightPx = (520 / 750) * systemInfo.windowWidth  // rpx → px
scrollViewHeight.value = systemInfo.windowHeight - heroHeightPx
```

```html
<scroll-view :style="{ height: scrollViewHeight + 'px' }" />
```

### 问题三：iOS 真机滑动列表内容消失

**现象**：手指滑动 scroll-view 时，列表内容消失（被裁剪），松手后可能恢复。

**根因**：CSS 属性触发了 **GPU 合成层（Compositing Layer）**，合成层覆盖在原生 `scroll-view` 上方，滑动时遮挡内容。

**定位过程**（三次修复）：
1. 移除 `page { transform: translateZ(0) }` → 未解决
2. 移除 `page { animation: page-fade-in }` → 未解决
3. 移除 `backdrop-filter` + 祖先 `overflow: hidden` → 解决

### 面试要点 — 合成层

| 触发属性 | 机制 | 风险 |
|---------|------|:---:|
| `transform: translateZ(0)` / `translate3d` | 3D 变换必然创建合成层 | 🔴 |
| `animation` / `transition`（任意属性） | 动画/过渡期间提升 | 🔴 |
| `will-change` | 提前声明需要合成层 | 🔴 |
| `opacity < 1` | 需要与背景混合 | 🔴 |
| `backdrop-filter` / `filter` | 滤镜效果需要合成层 | 🟡 |
| `position: fixed`（iOS） | iOS 上创建合成层 | 🟡 |
| `overflow: hidden` | 创建 BFC，间接触发 | 🟡 |

**核心原则**：合成层是独立 GPU 纹理，覆盖在原生组件上方。微信小程序中，**永远不要在 `page` 或 `scroll-view` 祖先元素上使用会触发合成层的 CSS 属性**。合成层只安全用于浮层（Navbar、TabBar、弹窗）。

**安全法则**：
- `backdrop-filter` 仅用于浮层，别放 scroll-view 兄弟元素上
- `overflow: hidden` 别放 scroll-view 祖先元素上，改为 `overflow: visible`
- 页面过渡动画用 `opacity` 而非 `transform`

---

## 九 🎤 生产部署实战复盘 → 企业级面试知识图谱

> 记录 2026-08-25 首次生产部署（阿里云 ECS + Docker Compose + Nginx）过程中真实遇到的 19 个问题，按面试维度整理成可复用的知识图谱。每个问题给出**现象 / 根因 / 方案 / 面试考点**四要素。

**部署环境**：阿里云 ECS（华东2 上海，2C4G，Ubuntu 22.04）+ Docker + Nginx + Let's Encrypt + GitHub

### 部署阶段回顾

| # | 阶段 | 关键动作 | 耗时 |
|---|-----|---------|------|
| 1 | 采购 ECS + 开安全组 | 22/80/443 端口 | 30 分钟 |
| 2 | 装 Docker / Nginx / Certbot | 换 Docker 官方源 | 20 分钟 |
| 3 | GitHub clone 代码 | Public 仓库无需认证 | 5 分钟 |
| 4 | 配置 `.env.prod` | 5 个变量（生成密钥）| 10 分钟 |
| 5 | Docker Compose 启动三容器 | 首次构建 32 分钟（用清华源加速）| 40 分钟 |
| 6 | Alembic 迁移 + Seed | 建表 + 默认租户 | 3 分钟 |
| 7 | 构建 admin-web + Nginx 部署 | 修复 3 处 TS 错误 | 25 分钟 |
| 8 | 浏览器访问 http://IP 验证 | ✅ 阶段 A 完成 | — |

---

### 一、Linux 运维 & 系统管理

#### 🔴 问题 1：`docker-compose-plugin` 装不上

- **现象**：`apt install docker-compose-plugin` 报 `Unable to locate package`
- **根因**：Ubuntu 官方源没这个包，它属于 Docker 官方源
- **方案**：添加 Docker 官方 apt 源（用阿里云镜像加速），或改用 `docker.io` 老版本 + 独立 compose 二进制
- **面试考点**：
  - Linux 软件包管理机制（apt/yum/dnf 的仓库结构）
  - 官方源 vs 第三方源，如何添加 GPG key
  - `/etc/apt/sources.list.d/` 与主 `sources.list` 的加载顺序

#### 🔴 问题 2：`needrestart` 弹窗打断脚本

- **现象**：apt upgrade 后弹出紫色对话框询问重启服务
- **根因**：Ubuntu 22.04+ 默认启用交互式服务重启确认
- **方案**：`sed -i 's/#$nrconf{restart} = .*/$nrconf{restart} = "a";/' /etc/needrestart/needrestart.conf`
- **面试考点**：
  - 无人值守自动化脚本设计（避免任何交互 prompt）
  - `DEBIAN_FRONTEND=noninteractive` 环境变量的作用
  - Ansible / Chef / Puppet 里如何保证幂等性

---

### 二、容器化 & Docker

#### 🔴 问题 3：Docker Hub 拉镜像 `i/o timeout`

- **现象**：`docker pull redis:7-alpine` 超时报 `dial tcp 103.200.30.143:443: i/o timeout`
- **根因**：大陆服务器访问 `registry-1.docker.io` 网络受限
- **方案**：`/etc/docker/daemon.json` 配置 `registry-mirrors`，用阿里云个人加速器 / DaoCloud / 1ms.run
- **面试考点**：
  - Docker 镜像仓库分层机制（Registry → Repository → Image → Layer）
  - 镜像加速器原理（HTTP 反向代理 + 中转缓存）
  - Harbor 私有仓库、自建 Registry 的必要性
  - 企业内网如何搭建统一的镜像代理层
  - `docker save` / `docker load` 离线迁移镜像

#### 🔴 问题 4：Dockerfile 构建慢（首次 40+ 分钟）

- **现象**：`RUN apt-get install build-essential` 卡在 `deb.debian.org` 下载，`RUN uv sync` 卡在 pypi
- **根因**：Debian/PyPI 官方源海外，国内服务器慢
- **方案**：Dockerfile 里用 `sed` 替换清华 Debian 镜像 + `pip install -i` 指定清华 pypi + `ENV UV_INDEX_URL`
- **改造前后对比**：apt 阶段 2305s → 29s（78 倍提速）
- **面试考点**：
  - **Dockerfile 分层缓存原理**：为什么 `COPY pyproject.toml` 要在 `COPY . .` 之前？依赖不变时才能命中缓存
  - **多阶段构建**（multi-stage build）：build 阶段装编译工具，runtime 阶段只带运行时，减小镜像体积
  - **`.dockerignore` 的作用**：减少构建上下文体积，避免 `node_modules` 被拷进容器
  - **BuildKit** 并发构建 + 缓存挂载（`--mount=type=cache`）
  - **layer 顺序优化**：变化频率低的放前面（依赖），变化频率高的放后面（源码）

#### 🔴 问题 5：容器间网络通信

- **现象**：为什么 API 容器里 `DATABASE_URL=postgresql://...@postgres:5432/...` 能连通？为什么不写 `localhost`？
- **根因**：Docker Compose 自动创建 bridge 网络，服务名作为 DNS 别名
- **面试考点**：
  - Docker 4 种网络模式：bridge / host / none / overlay
  - 容器 DNS 解析（`/etc/resolv.conf` 指向 `127.0.0.11`）
  - `depends_on.condition: service_healthy` vs 简单 `depends_on` 的区别（后者只等启动，不等就绪）
  - Kubernetes 里 Service 的 ClusterIP 和 DNS（`svc-name.namespace.svc.cluster.local`）
  - 跨 host 容器通信：Docker Swarm overlay / K8s CNI

#### 🔴 问题 6：`docker-compose.prod.yml` 端口暴露 `127.0.0.1:8000:8000`

- **考点**：
  - 为什么不写成 `8000:8000`（这样会暴露到 `0.0.0.0` 公网）
  - **Nginx 反代 → 后端服务不直接对外**的分层安全设计
  - 生产环境的**最小暴露原则**
  - K8s 中 `ClusterIP` / `NodePort` / `LoadBalancer` 的暴露层次

---

### 三、GitOps & DevOps 工作流

#### 🔴 问题 7：服务器上直接改文件会被 git pull 覆盖吗？

- **答**：会。Git 认为远程仓库是权威版本，本地未提交的改动会被覆盖或触发冲突
- **考点（超高频）**：
  - **GitOps 核心思想**：Git 是唯一的 Single Source of Truth，服务器只是"消费者"
  - **本地开发 → git push → 服务器 git pull → 重新部署** 的闭环
  - **服务器绝不能有"本地改动"**，否则出现"雪花服务器"（snowflake servers）—— 环境漂移、无法复现
  - **Infrastructure as Code**（IaC）：配置文件与代码同仓库管理
  - Immutable Infrastructure（不可变基础设施）：容器 vs 传统虚机
- **进阶延伸**：ArgoCD / FluxCD 实现 K8s 层面的自动 GitOps

#### 🔴 问题 8：`.env.prod` 为什么不进 git？

- **考点**：
  - **12-Factor App** 中的 "Config" 原则：配置从环境变量注入，不写死在代码
  - `.gitignore` 保护敏感文件（`.env.prod` / `credentials.json` / `*.pem`）
  - **秘密管理**方案：HashiCorp Vault、AWS Secrets Manager、K8s Sealed Secrets、SOPS
  - 已经 commit 过的 secret 如何清理：BFG Repo-Cleaner、`git filter-repo`（旧的 `git filter-branch` 已废弃）
  - **重置密钥比擦 git 历史更重要**（因为 fork / 备份可能已经拿到）

#### 🔴 问题 9：`WECHAT_SECRET` 硬编码进代码

- **现象**：`config.py:39` 明文写 `afc51f233d8ea454ba8df6435750b4dd`
- **面试考点**：
  - **密钥泄露事故复盘**：即使删除代码，git 历史仍能查到（`git log -S "secret"`）
  - **正确姿势**：立刻在微信平台重置 → 环境变量注入 → 用 `git filter-repo` 清历史
  - **Pre-commit hook**：`gitleaks` / `detect-secrets` 阻止密钥入库
  - **企业级方案**：所有 secret 集中管理 + 短期凭证轮换（Vault Dynamic Secrets）

---

### 四、数据库 & ORM

#### 🔴 问题 10：seed.py 报 "relation tenants does not exist"

- **根因**：直接跑 seed 没先跑 `alembic upgrade head`，表还没建
- **面试考点**：
  - **数据库迁移工具**（Alembic / Flyway / Liquibase）的工作原理
  - **`alembic_version` 表**：记录已应用的版本号，实现幂等升级
  - **迁移文件的"向前兼容"设计**：`upgrade()` + `downgrade()` 必须双向可逆
  - **生产迁移的最佳实践**：
    - 大表加列先用 `NULL` 默认值，避免锁表（在线 DDL）
    - 分批数据迁移，避免长事务撑爆 WAL
    - Blue-Green 部署时的 schema 兼容性（"先加字段后改代码，删字段是两个 release"）
  - **零停机迁移**：`pt-online-schema-change` / `gh-ost`

#### 🔴 问题 11：POSTGRES_PASSWORD 含 `/` 和 `+` 特殊字符

- **面试考点**：
  - URL 中的特殊字符必须做 **percent-encoding**（`+` → `%2B`，`/` → `%2F`，`@` → `%40`）
  - 生产密码建议限制字符集，避免连接串解析歧义
  - **密码熵**：至少 64 bits 熵值才算安全（12 位混合密码 ≈ 76 bits）
  - **密钥生成**：`openssl rand -base64 24` 生成 24 字节 → base64 编码为 32 字符

#### 🔴 问题 12：连接字符串 `postgresql+asyncpg://` vs `postgresql://`

- **面试考点**：
  - **SQLAlchemy** 的 `dialect+driver://user:pw@host:port/db` 表达式
  - **asyncpg**（异步）vs **psycopg2**（同步）性能对比
  - **异步 ORM 的意义**：I/O 密集应用同一时刻可承接更多请求（避免 GIL + 线程池瓶颈）
  - **N+1 查询**：`selectinload` / `joinedload` / `contains_eager` 三种解法差异
  - **连接池**：`pool_size` / `max_overflow` / `pool_recycle` / `pool_pre_ping`

---

### 五、前端工程化

#### 🔴 问题 13：vue-tsc 报 3 处 TypeScript 类型错误

**错误 A**：`Property 'children' does not exist on type ...`
- **根因**：数组字面量类型推导为最窄类型，没有 `children` 字段的对象无法访问该字段
- **修复**：显式声明 `interface MenuItem { children?: MenuItem[] }`
- **考点**：TS 类型推导（inference）vs 类型标注（annotation）

**错误 B**：`Property 'split' does not exist on type 'never'`
- **根因**：**类型收窄**（type narrowing）—— `instanceof Date` 分支后剩余类型被推导为 `null`，else 分支的 `typeof === 'string'` 就是 `never`
- **修复**：要么扩展联合类型（`Date | string | null`），要么删掉不可达分支
- **考点**：
  - TS 的 **discriminated union**、**exhaustive check**
  - `never` 类型的意义（unreachable code / bottom type）
  - `strict` 模式下 `strictNullChecks` / `noImplicitAny` 的意义
  - **类型体操**：`Partial` / `Required` / `Pick` / `Omit` / `ReturnType`

#### 🔴 问题 14：Vite build 警告 "chunks larger than 500 kB"

- **面试考点**：
  - **代码分割**（code splitting）：`import()` 动态引入、路由级懒加载
  - **manualChunks** 手动分包：把 vendor / element-plus / echarts 单独打
  - **Tree Shaking** 的原理（ES Module 静态分析 + `sideEffects: false`）
  - **HTTP/2 多路复用** → 允许更细粒度分包（不再需要"一个大 bundle"的假设）
  - **CDN 化第三方库**：`externals` + `<script>` 引入
  - **preload / prefetch** 提示浏览器优先级

---

### 六、Nginx & 反向代理

#### 🔴 问题 15：为什么前端 API 用相对路径 `/api/v1`？

- **面试考点**：
  - **同源策略**：Nginx 把 admin + API 放同一个域名 → 无需处理 CORS
  - **CORS 三要素**：`Access-Control-Allow-Origin` / `Credentials` / `Preflight OPTIONS`
  - **`proxy_pass` 反代**：为什么后端能看到真实客户端 IP？`X-Real-IP` / `X-Forwarded-For` / `X-Forwarded-Proto`
  - **SPA 路由 fallback**：`try_files $uri $uri/ /index.html;` 的作用（history 模式路由）
  - **反向代理 vs 正向代理**的区别

#### 🔴 问题 16：Nginx `sites-available` vs `sites-enabled`

- **面试考点**：
  - Debian/Ubuntu 的双目录约定：`available` 放所有可用配置、`enabled` 是软链接
  - `include /etc/nginx/sites-enabled/*` 的加载机制
  - CentOS/RHEL 系用 `conf.d/` 单目录
  - **`nginx -t`** 语法测试 + **`nginx -s reload`** 热更新（不断连接）

---

### 七、网络 & 安全

#### 🔴 问题 17：Mac 翻墙了为什么服务器还是连不上外网？

- **面试考点**：
  - **网络协议栈是分层且独立的**：Mac 的 VPN 只影响 Mac 的路由表
  - **HTTP_PROXY / HTTPS_PROXY** 环境变量、**透明代理**、**MITM** 原理
  - **企业级方案**：出口代理（Squid）/ NAT 网关 / 云上"跳板机"
  - **Docker daemon 代理**：`~/.docker/config.json` + `systemctl edit docker`

#### 🔴 问题 18：安全组 vs 服务器内部防火墙

- **面试考点**：
  - **两层防火墙**：云平台 SG（云侧，先过） + 主机 `iptables` / `ufw`（主机侧）
  - **深度防御**（Defense in Depth）原则
  - **最小权限原则**：SSH 22 端口只允许办公 IP、生产数据库不对外
  - **Zero Trust** 架构（永不信任、始终验证）
  - **DDoS 防护**：云平台的高防 IP、CDN 分流

#### 🔴 问题 19：为什么小程序强制 HTTPS + 域名备案？

- **面试考点**：
  - **HTTPS 的三个作用**：机密性（加密）/ 完整性（防篡改）/ 身份认证（证书）
  - **TLS 握手过程**（1.2 与 1.3 的差异，1.3 减少一个 RTT）
  - **Let's Encrypt 的 ACME 协议**：HTTP-01 challenge、DNS-01 challenge、TLS-ALPN-01
  - **证书链**：Root CA → Intermediate → Leaf；OCSP stapling
  - **HSTS**（Strict-Transport-Security）防止 SSL Stripping

---

### 八、JWT 认证 & 权限（项目自带高频考点）

**JWT 双 Token 设计**（本项目已实现）：
- Access Token 短命（2h） + Refresh Token 长命（7d）
- **Token 旋转**（Rotation）：每次 refresh 换新 RT，旧 RT 加黑名单
- **Redis 黑名单**：Token 撤销机制，TTL 自动清理

**面试考点**：
- JWT vs Session：无状态优势、注销困难的代价
- JWT 三段结构：Header.Payload.Signature（HMAC / RSA / ECDSA 签名算法）
- `jti`（JWT ID）唯一性 + `iat` 微秒精度防止 replay attack
- **CSRF vs XSS** 攻击场景对比：JWT 存 localStorage 防 CSRF 但怕 XSS，HttpOnly Cookie 相反
- **OAuth 2.0** 各种 Grant Type（Authorization Code / Client Credentials / Device Flow）
- **OpenID Connect** 与 OAuth 2.0 的关系

---

### 九、多租户 SaaS 架构（本项目核心）

**面试超高频问题**："如何设计一个 SaaS 系统的多租户？"

三种方案对比（本项目用方案 3）：

| 方案 | 数据隔离度 | 成本 | 适用场景 |
|------|----------|------|---------|
| 独立数据库（DB per Tenant）| ⭐⭐⭐ | 高 | 银行、医疗（合规严格）|
| 独立 Schema（Schema per Tenant）| ⭐⭐ | 中 | 中大型 SaaS |
| 共享表 + tenant_id（Row-level）| ⭐ | 低 | 中小型 SaaS ✅ |

**本项目的实现**：
- `TenantMixin` 给所有租户表加 `tenant_id` 字段
- `TenantAwareRepository` 基类自动注入 `WHERE tenant_id = ?`
- **ContextVar** 存储当前请求的 tenant_id（比 `threading.local` 更适合 asyncio）
- 中间件从 `x-tenant-slug` 请求头解析租户
- `setup_tenant_query_injection()` 拦截所有 SQL 自动加租户过滤

**面试延伸**：
- **数据泄露风险**：忘写 `WHERE tenant_id` → 跨租户看到别人的数据（本项目自动注入防止）
- 大 B 用户需要独立数据库怎么办？→ 分片路由（sharding router）
- Schema 演进：所有租户共享一份 schema，如何做灰度？
- **PostgreSQL RLS**（Row Level Security）：数据库层面的租户隔离方案

---

### 十、可用性 & 运维

#### 项目已有的健康检查

`docker-compose.prod.yml` 里的 healthcheck：
```yaml
test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
interval: 5s
```

**面试考点**：
- **Liveness / Readiness / Startup Probe**（K8s 三种探针的语义差异）
- **HTTP 200 ≠ 服务就绪**：可能只是进程活着但数据库连不上
- **优雅关闭**（graceful shutdown）：SIGTERM → 停止接新请求 → 处理完在途请求 → 退出
- **SIGKILL 是最后一招**（无法捕获），关闭前必须能收到 SIGTERM

#### 数据备份策略

**面试考点**：
- **3-2-1 备份原则**：3 份数据、2 种介质、1 份异地
- **PITR**（Point-in-Time Recovery）：`pg_dump` 全量 + WAL 归档增量
- **备份验证**：定期恢复演练，未验证的备份 = 没备份
- **RPO / RTO 指标**（Recovery Point/Time Objective）

---

### 十一、通用面试话术模板

**"讲一个你排查过的最难的线上问题"** → 你现在可以讲：

> 云服务器首次部署 Docker 镜像构建卡了 40 分钟。排查发现是 apt-get 从境外 debian.org 拉包超时（`2305.6s` 单步耗时），pypi 装 Python 包也慢。
>
> **根因**：跨境网络延迟 + 镜像构建 layer 无缓存首次拉取，`RUN apt-get install` 单条指令下载 200MB+ 的 build-essential。
>
> **方案**：Dockerfile 里替换清华 Debian/PyPI 镜像源，构建时间从 40 分钟降到 5 分钟（apt 环节 2305s → 29s，78 倍提速）。
>
> **反思**：
> 1. 生产 Dockerfile 应该考虑多环境（国内/海外）适配 —— 用 ARG 参数化镜像源
> 2. CI/CD 应缓存 base image + 依赖层，避免每次全量构建
> 3. 私有镜像仓库 + 分层复用是根治方案，把 base + deps 层预烘焙成"团队公共基础镜像"

---

## 十 🎤 PyCharm 通过 SSH 隧道连接 ECS 数据库

> 记录 2026-08-29 通过 PyCharm SSH 隧道连接阿里云 ECS 上 PostgreSQL 数据库的完整排查过程。涉及 SSH 密钥配置、Docker 端口映射、pg_hba.conf 认证规则等核心知识点。

**环境**：Mac 本地 PyCharm → SSH 隧道 → 阿里云 ECS（106.14.206.226）→ Docker 容器 PostgreSQL

### 问题排查全流程

#### 问题 1：SSH 密钥文件路径错误

**错误信息**：`SSH tunnel creation failed: Connection refused`

**现象**：终端 `ssh root@106.14.206.226` 能正常登录，但 PyCharm SSH 隧道测试失败。

**排查**：
```bash
ls -la /Users/lixiang/.ssh/
# 实际密钥文件: id_ed25519
# PyCharm 配置的: id_rsa（不存在）
```

**根因**：PyCharm SSH 配置中 `Private key file` 路径填错，指向了不存在的 `id_rsa`。

**解决**：修改 PyCharm SSH/SSL 标签页中的密钥路径为 `/Users/lixiang/.ssh/id_ed25519`。

**面试考点**：
- SSH 密钥类型：`id_rsa`（RSA 旧格式）/ `id_ed25519`（Ed25519 新格式，推荐）/ `id_ecdsa`
- 密钥权限要求：私钥必须 `600`（`-rw-------`），否则 SSH 拒绝使用
- `ssh-keygen -y -f <私钥>` 验证密钥是否有效
- 密钥 passphrase（密码短语）vs 服务器登录密码的区别

---

#### 问题 2：Docker 容器端口未映射到宿主机

**错误信息**：SSH 隧道成功，但数据库连接 `Connection refused`

**现象**：SSH 隧道建立成功，但 PyCharm 连接 `localhost:5432` 失败。

**排查**：
```bash
docker port dance-postgres
# 输出: (空) ← 没有端口映射

docker inspect dance-postgres | grep -A 5 "Ports"
# "5432/tcp": null ← 确认未映射
```

**根因**：PostgreSQL 运行在 Docker 容器中，容器内部端口 `5432` 没有映射到宿主机的端口。SSH 隧道转发到宿主机 `localhost:5432`，但宿主机上没有服务监听该端口。

**解决**：重新创建容器并添加端口映射
```bash
docker stop dance-postgres
docker rm dance-postgres

docker run -d \
  --name dance-postgres \
  --network docker_default \
  -p 5432:5432 \              ← 关键参数：宿主机:容器
  -e POSTGRES_DB=dance_saas \
  -e POSTGRES_USER=dance \
  -e POSTGRES_PASSWORD=dance_dev_pass \
  -v docker_pgdata:/var/lib/postgresql/data \
  postgres:15-alpine
```

**验证**：
```bash
docker port dance-postgres
# 输出: 5432/tcp -> 0.0.0.0:5432 ✅

docker ps | grep dance-postgres
# 输出: Up (healthy) ✅
```

**面试考点**：
- **Docker 端口映射原理**：`-p hostPort:containerPort`，iptables DNAT 规则转发
- **端口映射方向性**：只对"外部→容器"生效，容器内部通信不需要映射
- **数据卷持久化**：`-v volume_name:/path`，删除容器数据不丢失
- **Docker 网络模式**：bridge（默认）/ host / none / overlay
- **容器间通信**：同网络下通过服务名 DNS 解析，不需要端口映射

---

#### 问题 3：pg_hba.conf 认证规则冲突

**错误信息**：`FATAL: password authentication failed for user "dance"`

**现象**：服务器上 `docker exec dance-postgres psql -U dance -d dance_saas` 成功，但 PyCharm 连接报密码错误。

**排查**：
```bash
docker exec dance-postgres cat /var/lib/postgresql/data/pg_hba.conf | grep -v "^#"
# 输出:
# local   all   all   trust
# host    all   all   127.0.0.1/32   trust
# host    all   all   ::1/128        trust
# host    all   all   all   scram-sha-256  ← 最后一行覆盖前面规则
```

**根因**：pg_hba.conf 最后一行 `host all all all scram-sha-256` 匹配所有 TCP 连接，要求 `scram-sha-256` 认证，覆盖了前面的 `trust` 规则。PyCharm 通过 SSH 隧道建立的 TCP 连接被这条规则匹配，但密码格式不匹配导致认证失败。

**解决**：注释掉冲突的规则
```bash
docker exec dance-postgres sed -i 's/^host all all all scram-sha-256$/# host all all all scram-sha-256/' /var/lib/postgresql/data/pg_hba.conf
docker restart dance-postgres
```

**面试考点**：
- **pg_hba.conf 格式**：`type database user address auth-method`
- **匹配顺序**：从上到下，第一条匹配的规则生效（类似 iptables）
- **认证方法**：
  - `trust`：无需密码（开发环境方便，生产禁用）
  - `md5`：MD5 密码认证
  - `scram-sha-256`：更安全的密码认证（PostgreSQL 10+ 默认，推荐生产使用）
  - `peer`：操作系统用户名匹配（仅 local 连接）
- **生产环境配置**：
  ```
  local   all   all   peer
  host    all   all   127.0.0.1/32   scram-sha-256
  host    all   all   ::1/128        scram-sha-256
  host    all   all   0.0.0.0/0      reject  ← 拒绝其他所有
  ```

---

#### 问题 4：Docker 网络 IP 不在 pg_hba.conf 允许列表

**错误信息**：`FATAL: no pg_hba.conf entry for host "172.19.0.1", user "dance", database "dance_saas"`

**现象**：SSH 隧道建立成功，端口映射正常，但连接被拒绝，错误显示来源 IP 是 `172.19.0.1`。

**根因**：SSH 隧道建立的连接在 Docker 网络中，来源 IP 是 Docker 网关 `172.19.0.1`，而不是 `127.0.0.1`。pg_hba.conf 中只允许了 `127.0.0.1/32`，没有允许 Docker 网络 IP。

**解决**：添加允许 Docker 网关 IP 的规则
```bash
docker exec dance-postgres bash -c 'echo "host    all    all    172.19.0.1/32    trust" >> /var/lib/postgresql/data/pg_hba.conf'
docker restart dance-postgres
```

**或者更简单（开发环境）**：允许所有 IP
```bash
docker exec dance-postgres bash -c 'echo "host    all    all    0.0.0.0/0    trust" >> /var/lib/postgresql/data/pg_hba.conf'
docker restart dance-postgres
```

**面试考点**：
- **Docker 网络拓扑**：bridge 网络有网关 IP（通常 `172.17.0.1` 或 `172.19.0.1`）
- **SSH 隧道工作原理**：本地端口 → SSH 加密通道 → 服务器本地端口
- **连接来源 IP 变化**：通过 SSH 隧道连接时，数据库看到的来源 IP 是隧道出口 IP
- **CIDR 表示法**：`/32` 表示单个 IP，`/24` 表示 256 个 IP，`/0` 表示所有 IP

---

### 最终正确配置

#### PyCharm SSH/SSL 标签页
```
☑ Use SSH tunnel
Host: 106.14.206.226
Port: 22
Username: root
Authentication type: Key pair
Private key file: /Users/lixiang/.ssh/id_ed25519
```

#### PyCharm General 标签页
```
Host: localhost      ← 必须是 localhost（通过隧道转发）
Port: 5432
User: dance
Password: dance_dev_pass
Database: dance_saas
```

#### 服务器端配置
```bash
# 1. Docker 端口映射
docker port dance-postgres
# 5432/tcp -> 0.0.0.0:5432

# 2. pg_hba.conf 配置
docker exec dance-postgres cat /var/lib/postgresql/data/pg_hba.conf | grep -v "^#"
# local   all   all   trust
# host    all   all   127.0.0.1/32   trust
# host    all   all   172.19.0.1/32  trust  ← 添加的 Docker 网关 IP
```

---

### 排查思路总结

```
问题排查流程:

1. SSH 隧道测试
   ↓ 失败 → 检查密钥路径、SSH 服务、防火墙
   ↓ 成功 ✅

2. 数据库连接测试
   ↓ Connection refused → 检查 Docker 端口映射
   ↓ password authentication failed → 检查 pg_hba.conf 认证规则
   ↓ no pg_hba.conf entry for host → 检查来源 IP 是否在允许列表
   ↓ 成功 ✅
```

### 核心知识点

| 问题 | 核心原因 | 解决方案 | 面试考点 |
|------|---------|---------|---------|
| SSH 连接失败 | 密钥路径错误 | `ls -la ~/.ssh/` 查找正确密钥 | SSH 密钥类型、权限要求 |
| 数据库连接拒绝 | Docker 端口未映射 | `docker run -p 5432:5432` | 端口映射原理、数据卷 |
| 密码认证失败 | pg_hba.conf 规则冲突 | 注释掉 `scram-sha-256` 规则 | 认证方法、匹配顺序 |
| 来源 IP 拒绝 | Docker 网关 IP 未允许 | 添加 `172.19.0.1/32` 到 pg_hba.conf | Docker 网络、CIDR |

### 安全最佳实践

**开发环境**（当前）：
- SSH 隧道 + pg_hba.conf `trust`（方便调试）
- 端口映射到 `0.0.0.0`（本地访问）

**生产环境**（推荐）：
- 不开放数据库端口到公网
- 使用 SSH 隧道或堡垒机访问
- pg_hba.conf 配置 IP 白名单 + `scram-sha-256` 认证
- 定期轮换密码
- 配置数据库审计日志

---

### 十二、可主动展示的项目亮点（简历 & 面试话术）

面试时可主动讲这些"我踩过、我理解、我解决了"的点：

1. **多租户 ContextVar 自动查询注入** —— 展示对 asyncio 上下文传递的理解
2. **JWT 双 Token + Redis 黑名单** —— 展示对无状态认证的深入理解
3. **纯 ASGI 中间件替代 BaseHTTPMiddleware** —— 展示对 Starlette 底层的了解（避免事件循环冲突）
4. **异步 SQLAlchemy 2.0 + asyncpg** —— 展示对新一代 Python 异步生态的掌握
5. **Docker Compose + Nginx + Let's Encrypt 全链路部署** —— DevOps 全流程实操
6. **GitOps 工作流 + 分阶段上线**（阶段 A IP 调试 + 阶段 B 备案后域名切换）—— 展示项目管理能力

---

### 十三、STAR 故事清单（20 个可展开叙述的案例）

从上述问题中提取，每个可以讲成 3-5 分钟的完整故事：

| # | Story 主题 | 关键词 |
|---|-----------|--------|
| 1 | Docker Hub 拉不下镜像 | 镜像加速器 / 国内网络 |
| 2 | Dockerfile 构建 40 分钟优化到 5 分钟 | 分层缓存 / 国内源 |
| 3 | seed.py 报表不存在 | 数据库迁移工具 / 幂等性 |
| 4 | 硬编码 WeChat Secret 泄露事故 | 密钥管理 / git 历史清理 |
| 5 | TypeScript 类型收窄导致 `never` | 类型系统 / discriminated union |
| 6 | 前端 chunk 过大警告 | 代码分割 / Tree Shaking |
| 7 | 相对路径 API 避免 CORS | 同源策略 / 反向代理 |
| 8 | 服务器改文件被 git pull 覆盖 | GitOps / IaC |
| 9 | 多租户忘写 tenant_id 泄露 | Row-level 隔离 / 自动注入 |
| 10 | JWT 双 Token + Redis 黑名单 | 无状态认证 / Token 撤销 |
| 11 | 微信小程序页面栈溢出 | uni-app 生命周期 |
| 12 | scroll-view 合成层冲突 | iOS 渲染 / GPU 合成 |
| 13 | 微信登录 IP 白名单 | 公网出口 IP / 代理透传 |
| 14 | FastAPI 307 重定向丢 header | redirect_slashes / axios |
| 15 | asyncpg 事件循环冲突 | 异步测试 / 独立 Uvicorn |
| 16 | 纯 ASGI 中间件 vs BaseHTTPMiddleware | Starlette 内部机制 |
| 17 | 密码含特殊字符解析失败 | URL 编码 / 密码策略 |
| 18 | 安全组只暴露 127.0.0.1:8000 | 最小暴露原则 / 深度防御 |
| 19 | needrestart 弹窗打断自动化 | 无人值守脚本 |
| 20 | 分阶段上线（备案前 IP 阶段 A → 备案后域名阶段 B）| 项目管理 / 关键路径 |

**建议做法**：每个 story 用 STAR 框架（Situation-Task-Action-Result）写成 200 字的段落，面试前熟练背诵 3-5 个即可覆盖后端 / 前端 / DevOps 三个方向的问答。

---

## 十 🎤 CI/CD 部署成功但浏览器端数据不是最新

### 现象

CI/CD 成功执行完成，服务器上的代码和构建产物都是最新的，但用户通过浏览器访问时，看到的仍然是旧版本界面或旧数据。

### 根因分析

这个问题涉及三层缓存，任何一层未正确处理都会导致"部署成功但用户看不到更新"：

#### 1. 浏览器 HTTP 缓存（最常见）

浏览器会缓存静态资源（HTML/CSS/JS/图片），缓存策略由 Nginx 返回的响应头决定：

| 响应头 | 作用 | 未设置的后果 |
|--------|------|-------------|
| `Cache-Control` | 控制缓存策略 | 浏览器自行决定缓存时长，可能缓存数小时 |
| `ETag` / `Last-Modified` | 验证缓存是否过期 | 无法做条件请求，只能等缓存过期 |

**默认行为**：如果 Nginx 没有配置 `Cache-Control`，浏览器可能缓存 HTML 文件数分钟到数小时，导致用户看不到最新部署。

#### 2. index.html 的特殊性

Vite 构建的 SPA 应用中，`index.html` 是入口文件，它引用了带哈希值的 JS/CSS 文件（如 `app.a1b2c3d4.js`）。

**正确的缓存策略**：
- `index.html` → **不缓存**（`Cache-Control: no-cache`），确保每次访问获取最新入口
- `assets/*.js, assets/*.css` → **长期缓存**（`Cache-Control: public, max-age=31536000, immutable`），因为文件名含哈希，内容变化时文件名也会变化

**问题场景**：如果 `index.html` 被缓存，浏览器不会请求新的 HTML，也就不会引用新的带哈希的 JS/CSS 文件，导致用户一直看到旧版本。

#### 3. Nginx 配置缺失

当前部署流程中，Nginx 配置（`deploy.yml` 第 6 步自动生成的配置）没有设置任何 `Cache-Control` 响应头：

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

这意味着所有静态资源都走默认缓存策略，浏览器可能长时间缓存 `index.html`。

### 解决方案

#### 方案一：Nginx 层配置缓存策略（推荐）

在 Nginx 配置中区分 `index.html` 和静态资源：

```nginx
location / {
    # index.html 不缓存（或每次验证）
    if ($uri = /index.html) {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }
    
    try_files $uri $uri/ /index.html;
}

# 静态资源长期缓存（文件名含哈希）
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

#### 方案二：Vite 构建时添加内容哈希

Vite 默认已经为 `assets/` 下的文件添加内容哈希（如 `app.a1b2c3d4.js`），无需额外配置。确保 `vite.config.ts` 中没有禁用该功能：

```ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name].[hash].js',  // 默认已启用
        chunkFileNames: 'assets/[name].[hash].js',
        assetFileNames: 'assets/[name].[hash].[ext]',
      },
    },
  },
})
```

#### 方案三：用户侧临时解决

在问题修复前，可告知用户以下方法强制刷新：

| 操作 | 快捷键 | 效果 |
|------|--------|------|
| 硬刷新 | `Ctrl+Shift+R` (Win) / `Cmd+Shift+R` (Mac) | 忽略缓存，重新请求所有资源 |
| 清空缓存并硬刷新 | 打开 DevTools → 右键刷新按钮 | 清除当前站点所有缓存 |
| 无痕模式 | `Ctrl+Shift+N` / `Cmd+Shift+N` | 不使用任何缓存 |

### 完整修复后的 Nginx 配置示例

```nginx
server {
    listen 80 default_server;
    server_name _;
    
    root /var/www/admin;
    index index.html;
    
    # SPA history-mode routing
    location / {
        # index.html 不缓存
        if ($uri = /index.html) {
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            add_header Pragma "no-cache";
            add_header Expires "0";
        }
        
        try_files $uri $uri/ /index.html;
    }
    
    # 静态资源长期缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 面试要点

| 问题 | 回答要点 |
|------|---------|
| **部署成功但用户看不到更新，可能是什么原因？** | 三层缓存：浏览器 HTTP 缓存（最常见）、Service Worker 缓存、CDN 缓存。优先检查 Nginx 的 `Cache-Control` 响应头 |
| **SPA 应用的正确缓存策略是什么？** | `index.html` 不缓存（`no-cache`），带哈希的静态资源长期缓存（`max-age=31536000, immutable`） |
| **为什么带哈希的文件名可以长期缓存？** | 内容变化时文件名也会变化（如 `app.a1b2c3d4.js` → `app.e5f6g7h8.js`），浏览器会当作新资源请求，不会命中旧缓存 |
| **`Cache-Control: no-cache` 和 `no-store` 的区别？** | `no-cache`：可以缓存，但每次使用前必须向服务器验证；`no-store`：完全不缓存，每次都重新请求 |
| **如何验证缓存策略是否生效？** | 浏览器 DevTools → Network 面板 → 查看响应头 `Cache-Control`；首次请求状态码 200，刷新后看 304（验证通过）或 200 (disk cache)（命中缓存） |
| **Vite 的构建产物有什么特点？** | `index.html` 在根目录不含哈希，`assets/` 下的 JS/CSS 文件名含内容哈希（如 `app.a1b2c3d4.js`），确保内容变化时文件名也变化 |

### 排查 checklist

```
□ 1. 浏览器 DevTools → Network → 查看 index.html 的响应头
     期望：Cache-Control: no-cache 或 no-store
     
□ 2. 查看 JS/CSS 文件的响应头
     期望：Cache-Control: public, max-age=31536000, immutable
     
□ 3. 硬刷新（Ctrl+Shift+R）后是否正常？
     是 → 确认是缓存问题
     
□ 4. Nginx 配置是否包含 Cache-Control 指令？
     否 → 需要更新 Nginx 配置并 reload
     
□ 5. CI/CD 流程中是否包含 Nginx 配置更新步骤？
     否 → 建议将完整 Nginx 配置纳入版本控制，部署时自动同步
```

---