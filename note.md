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
| 八 | 🔧 | [真机模式页面渲染后闪现消失](#八真机模式页面渲染后闪现消失) | 前端、loading状态管理、微信小程序渲染机制 |

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

## 八 🔧 真机模式页面渲染后闪现消失

> **分类：前端** | **影响范围：排期页面、课程列表、历史记录等所有数据加载页面** | **优先级：P0（致命）** | **状态：待解决 ⚠️**

### 现象

在微信小程序**真机模式**（特别是低端 Android 设备）下，用户执行以下操作后出现**数据闪现后立即消失**的问题：

1. **排期页面**：切换日期后，排期列表短暂显示（0.5-1秒），然后突然消失，页面回到空状态或持续 loading
2. **课程列表**：切换舞蹈种类分类后，课程卡片闪现一下就没了
3. **历史记录**：进入页面时数据一闪而过，随后白屏
4. **通用特征**：
   - 开发者工具模拟器正常，仅在真机复现
   - 弱网环境下更明显
   - 快速连续操作时必现

### 待排查方向

- [ ] Loading 状态生命周期管理（是否及时释放）
- [ ] Vue 响应式更新时机（v-model + @change 执行顺序）
- [ ] 真机环境性能差异（JS引擎、内存、网络）
- [ ] 数据竞态条件（并发请求导致的状态覆盖）

---

<!-- TODO: 解决此问题后补充以下章节 -->
<!-- ### 原因 -->
<!-- ### 解决方案 -->
<!-- ### 修复前后对比 -->
<!-- ### 涉及文件 -->
<!-- ### 面试要点 -->
<!-- ### 扩展优化建议 -->