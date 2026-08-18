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