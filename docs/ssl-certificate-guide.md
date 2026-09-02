# SSL 证书完整指南

> 从网络通信原理出发，系统理解 SSL/TLS 证书、HTTPS、Nginx 配置

---

## 一、SSL 证书到底是什么？

### 通俗类比

SSL 证书就像现实世界中的 **"身份证 + 营业执照 + 公章"** 的组合：

| 现实世界 | 网络世界 |
|---------|---------|
| 身份证 | 证明"你是谁" |
| 营业执照 | 证明"你有权经营这个业务" |
| 公章 | 证明"这个文件是真实的" |
| 公安局发证 | CA 机构颁发证书 |

### 1. SSL 证书证明了什么？

SSL 证书证明：**"这个服务器有权代表 api.seplume.com"**

就像身份证证明"你是张三"，SSL 证书证明"这个服务器是 api.seplume.com"。

### 2. 谁给你颁发证书？

**CA（Certificate Authority，证书颁发机构）**

就像公安局颁发身份证，CA 机构颁发 SSL 证书。

常见的 CA：
- Let's Encrypt（免费）
- DigiCert（商业）
- GlobalSign（商业）
- 阿里云/腾讯云（代理商业 CA）

### 3. 为什么浏览器相信这个证书？

因为浏览器**内置了信任的 CA 列表**（根证书）。

就像你相信公安局发的身份证，因为你知道公安局是权威机构。

浏览器内置了上百个受信任的根 CA，Let's Encrypt 是其中之一。

### 4. 证书里面到底保存了什么信息？

```
域名：api.seplume.com
颁发者：Let's Encrypt
有效期：2026-01-01 ~ 2026-04-01
公钥：xxxxx（用于加密）
签名：CA 的数字签名（证明证书真实）
```

### 5. 证书是不是一个"加密密码"？

**不是！**

证书里面包含的是**公钥**，不是密码。

公钥可以公开，就像你的公开电话号码。

### 6. 证书是不是用来直接加密所有 HTTP 数据的？

**不是！**

证书只用于**身份认证**和**协商加密密钥**。

真正加密数据的是 TLS 握手后生成的**会话密钥**。

---

### 常见误区纠正

| 错误认知 | 正确理解 |
|---------|---------|
| SSL 证书 = HTTPS | SSL 证书是 HTTPS 的组成部分 |
| SSL 证书 = 加密算法 | 证书包含公钥，不直接加密数据 |
| SSL 证书 = 私钥 | 证书只包含公钥，私钥单独保存 |
| SSL 证书 = Nginx | Nginx 是使用证书的软件 |

---

## 二、SSL、TLS、HTTPS 到底是什么关系？

### 概念定义

| 概念 | 是什么 | 类比 |
|------|--------|------|
| **SSL** | 安全套接层协议（已淘汰） | 旧版加密标准 |
| **TLS** | 传输层安全协议（SSL 的升级版） | 新版加密标准 |
| **HTTP** | 超文本传输协议 | 普通快递 |
| **HTTPS** | HTTP + TLS | 加密快递 |
| **SSL Certificate** | 服务器身份证明 | 身份证 |

### SSL 和 TLS 的关系

```
SSL 1.0 → SSL 2.0 → SSL 3.0 → TLS 1.0 → TLS 1.1 → TLS 1.2 → TLS 1.3
(已淘汰)  (已淘汰)  (已淘汰)   (已淘汰)   (已淘汰)    (主流)    (最新)
```

**现代 HTTPS 使用的是 TLS，不是 SSL。**

但大家习惯叫"SSL 证书"，实际是"TLS 证书"。

### 关系图

```
HTTP（明文传输）
 +
TLS（加密层）
 ↓
HTTPS（加密传输）

HTTPS 需要：
├── HTTP 协议（传输数据）
├── TLS 协议（加密通信）
── SSL 证书（身份认证）
```

---

## 三、为什么 HTTP 不需要证书，HTTPS 需要？

### HTTP 的问题

```
用户浏览器
    ↓ HTTP（明文）
攻击者可以：
├── 窃听：看到所有内容
├── 篡改：修改传输内容
└── 伪装：冒充目标网站
```

### 真实例子：用户登录

**HTTP 登录：**

```
POST /login
Content-Type: application/json

{
  "username": "admin",
  "password": "123456"
}
```

攻击者在同一网络（如公共 WiFi）可以：

```
抓包工具看到：
username=admin
password=123456
```

**HTTPS 登录：**

```
TLS 加密后：
乱码乱码乱码乱码...
```

攻击者看到的是乱码，无法直接获取用户名和密码。

### HTTPS 解决的三个问题

| 问题 | HTTP | HTTPS |
|------|------|-------|
| 机密性 | ❌ 明文传输 | ✅ 加密传输 |
| 完整性 | ❌ 可被篡改 | ✅ 防篡改 |
| 身份认证 |  无法确认 | ✅ 证书验证 |

---

## 四、为什么"加密"还不够？为什么还需要证书？

### 核心问题

即使通信被加密了，仍然存在：

> **我怎么知道我加密连接的那一端真的是 api.seplume.com？**

### 攻击场景：中间人攻击

```
用户浏览器
    ↓ 加密连接
攻击者伪装的网站（冒充 api.seplume.com）
    ↓ 加密连接
真正的 api.seplume.com
```

如果没有证书：
- 用户以为自己连接的是 api.seplume.com
- 实际连接的是攻击者的服务器
- 攻击者可以解密、查看、篡改所有数据

### 证书的作用

```
加密：解决"数据不被看到"
身份认证：解决"连接的是正确的服务器"
```

**证书首先解决"你是谁"，然后 TLS 才能建立安全通信。**

---

## 五、SSL 证书里面到底有什么？

### 证书内容示例

```
证书信息：
├── 域名：api.seplume.com
├── 颁发者：Let's Encrypt Authority X3
├── 有效期：2026-01-01 ~ 2026-04-01
├── 公钥：RSA 2048-bit（或 ECC）
├── 签名算法：SHA-256 with RSA
└── 扩展信息：
    ├── 密钥用途：数字签名、密钥加密
    └── 增强密钥用途：服务器认证
```

### 公钥 vs 私钥

| | 公钥 | 私钥 |
|---|------|------|
| 位置 | 证书中（公开） | 服务器本地（保密） |
| 作用 | 加密数据、验证签名 | 解密数据、生成签名 |
| 能否公开 | ✅ 可以 | ❌ 绝对不能 |

### 重要原则

> **证书文件可以公开，私钥必须严格保密。**

---

## 六、CA 是什么？为什么浏览器相信 SSL 证书？

### CA 是什么？

**CA（Certificate Authority）= 证书颁发机构**

就像：
- 公安局颁发身份证
- 工商局颁发营业执照
- CA 颁发 SSL 证书

### 浏览器为什么相信 CA？

因为浏览器**内置了受信任的根 CA 证书**。

```
浏览器安装时自带：
── DigiCert 根证书
── Let's Encrypt 根证书
├── GlobalSign 根证书
── ...（上百个）
```

### 证书链

```
根 CA（浏览器信任）
    ↓ 签名
中间 CA
    ↓ 签名
你的服务器证书
    ↓ 证明
api.seplume.com
```

浏览器验证流程：

```
1. 收到服务器证书
2. 检查证书链：你的证书 → 中间 CA → 根 CA
3. 确认根 CA 在信任列表中
4. 验证签名是否有效
5. 信任该证书
```

---

## 七、SSL 证书在哪里申请？

### 方式 1：Let's Encrypt（免费）

```bash
sudo certbot certonly --standalone -d api.seplume.com
```

特点：
- 完全免费
- 90 天有效期
- 支持自动续期
- 适合个人/中小项目

### 方式 2：云厂商证书服务

```
阿里云 → SSL 证书服务
腾讯云 → SSL 证书管理
华为云 → 云证书管理
```

特点：
- 有免费 DV 证书
- 也有付费 OV/EV 证书
- 一键部署到云产品

### 方式 3：商业 CA

```
DigiCert
GlobalSign
Comodo
Symantec
```

特点：
- 付费（几百到几千美元/年）
- 1-2 年有效期
- 支持 OV/EV 验证
- 企业级技术支持

---

## 八、为什么有的 SSL 证书免费，有的要收费？

### 对比表

| 对比项 | 免费证书（Let's Encrypt） | 商业证书 |
|--------|--------------------------|---------|
| 价格 | 免费 | $50-$2000+/年 |
| 有效期 | 90 天 | 1-2 年 |
| 自动续期 | ✅ 支持 | 通常手动 |
| 域名数量 | 单域名/多域名 | 灵活 |
| 通配符 | ✅ 支持 | ✅ 支持 |
| 验证级别 | DV（域名验证） | DV/OV/EV |
| 技术支持 | 社区 | 专业支持 |
| 保险赔偿 | 无 | 有 |

### 免费证书安全吗？

**完全安全！**

Let's Encrypt 的证书和付费证书在**加密强度上完全相同**。

区别只在：
- 验证级别（DV vs OV/EV）
- 服务支持
- 有效期长短

浏览器对 Let's Encrypt 证书和 DigiCert 证书**一视同仁**。

---

## 九、申请 SSL 证书需要证明什么？

### 域名所有权验证

CA 需要确认：**你确实控制这个域名**

### 验证方式

**1. HTTP 验证（certbot --standalone）**

```
CA 服务器
    ↓ 请求 http://api.seplume.com/.well-known/acme-challenge/xxx
你的服务器（临时 HTTP 服务）
    ↓ 返回指定内容
验证通过 → 颁发证书
```

**2. DNS 验证**

```
CA 要求：添加 TXT 记录
你的操作：在域名服务商添加 TXT 记录
CA 检查：DNS 记录是否正确
验证通过 → 颁发证书
```

### 为什么不能随便申请 google.com 的证书？

因为 CA 会验证域名所有权。

你无法通过 google.com 的验证，因为你控制不了 google.com 的 DNS 或服务器。

---

## 十、我的域名和 SSL 证书是什么关系？

### DNS vs SSL 证书

```
DNS：
api.seplume.com
        ↓ 解析
    公网 IP
（解决"去哪里"）

SSL 证书：
api.seplume.com
        ↓ 证明
"这个服务器有权代表 api.seplume.com"
（解决"你是谁"）
```

### 一句话总结

> **DNS 解决"去哪里"，证书解决"你是谁"。**

两者配合：
1. DNS 告诉浏览器"去 106.14.206.226"
2. 证书告诉浏览器"这个 IP 确实是 api.seplume.com"

---

## 十一、SSL 证书申请下来以后是什么？

### 常见文件

```
/etc/letsencrypt/live/api.seplume.com/
├── cert.pem      ← 服务器证书（公钥）
├── chain.pem     ← 中间 CA 证书
── fullchain.pem ← cert.pem + chain.pem（推荐用这个）
└── privkey.pem   ← 私钥（必须保密！）
```

### 文件格式说明

| 扩展名 | 说明 |
|--------|------|
| `.pem` | Base64 编码，文本格式，最常用 |
| `.crt` | 通常是 PEM 格式，有时是 DER |
| `.cer` | 同 .crt |
| `.key` | 私钥文件，PEM 格式 |
| `.p12/.pfx` | 二进制格式，包含证书+私钥 |

### 重要原则

```
可以公开：
├── cert.pem
── chain.pem
└── fullchain.pem

必须保密：
└── privkey.pem（绝对不能提交到 Git！）
```

---

## 十二、SSL 证书申请下来之后配置在哪里？

### 你的项目架构

```
用户
 ↓ https://api.seplume.com
阿里云 ECS
 ↓
Nginx（配置证书）
 ↓ HTTP
Docker
 ↓
FastAPI :8000
```

### 证书配置在 Nginx

**不是 FastAPI，不是 Docker，是 Nginx。**

原因：
- Nginx 是入口，最先接收 HTTPS 请求
- Nginx 负责 TLS 握手（解密/加密）
- FastAPI 只处理解密后的 HTTP 请求

---

## 十三、Nginx 如何使用 SSL 证书？

### 配置示例

```nginx
server {
    listen 443 ssl;                    # 监听 443 端口，启用 SSL
    server_name api.seplume.com;       # 匹配的域名

    ssl_certificate /etc/letsencrypt/live/api.seplume.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.seplume.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;  # 转发给 FastAPI
    }
}
```

### 逐行解释

| 配置 | 作用 |
|------|------|
| `listen 443 ssl` | 监听 HTTPS 默认端口 |
| `server_name` | 匹配请求的域名 |
| `ssl_certificate` | 服务器证书（公钥） |
| `ssl_certificate_key` | 私钥（解密用） |
| `location /` | 匹配所有路径 |
| `proxy_pass` | 转发给后端服务 |

### TLS 握手时 Nginx 做了什么？

```
1. 浏览器发起连接
2. Nginx 发送证书（fullchain.pem）
3. 浏览器验证证书
4. 双方协商加密参数
5. 建立加密通道
6. 开始传输 HTTP 数据
```

---

## 十四、TLS 握手到底发生了什么？

### 简化流程

```
浏览器                          Nginx
  │                              │
  │── ClientHello ─────────────→│  "支持 TLS 1.3，加密算法列表..."
  │                              │
  │←─ ServerHello ───────────────│  "使用 TLS 1.3，AES-256-GCM"
  │←─ Certificate ───────────────│  "这是我的证书"
  │                              │
  │  [验证证书]                   │
  │  ✓ 域名匹配？                 │
  │  ✓ 未过期？                   │
  │  ✓ CA 可信？                  │
  │                              │
  │── 生成会话密钥 ──────────────→│  （用证书公钥加密）
  │                              │
  │←─ 确认 ──────────────────────│  （用私钥解密）
  │                              │
  │══════════════════════════════│  加密通道建立！
  │                              │
  │── GET /users/123 ───────────→│  （加密传输）
  │←─ 200 OK ────────────────────│  （加密传输）
```

### 证书、公钥、私钥、会话密钥的角色

| 组件 | 作用 |
|------|------|
| 证书 | 证明服务器身份 |
| 公钥（在证书中） | 加密会话密钥 |
| 私钥（服务器本地） | 解密会话密钥 |
| 会话密钥 | 加密实际传输的数据 |

---

## 十五、为什么不能直接用 HTTP？

### HTTP vs HTTPS 对比

| 场景 | HTTP | HTTPS |
|------|------|-------|
| 登录请求 | 明文传输密码 | 加密传输密码 |
| Token | 可被窃取 | 安全传输 |
| Cookie | 可被劫持 | 安全传输 |
| API 数据 | 可被篡改 | 完整性保护 |
| 浏览器警告 | 显示"不安全" | 显示安全锁 |

### 生产环境必须用 HTTPS

```
http://api.seplume.com/login
    ↓
攻击者看到：password=123456

https://api.seplume.com/login
    ↓
攻击者看到：乱码乱码乱码...
```

---

## 十六、HTTP → HTTPS 重定向

### 配置

```nginx
# HTTP 服务器（不需要证书）
server {
    listen 80;
    server_name api.seplume.com;

    return 301 https://$host$request_uri;
}

# HTTPS 服务器（需要证书）
server {
    listen 443 ssl;
    server_name api.seplume.com;

    ssl_certificate ...;
    ssl_certificate_key ...;

    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

### 为什么 HTTP 不需要证书？

因为 HTTP 不加密，不需要身份认证。

### 为什么 HTTPS 需要证书？

因为 HTTPS 需要证明服务器身份，才能建立信任的加密连接。

---

## 十七、证书和私钥应该放在哪里？

### 推荐位置

```
/etc/letsencrypt/live/api.seplume.com/
├── fullchain.pem  ← 证书
└── privkey.pem    ← 私钥
```

### 安全原则

| 原则 | 说明 |
|------|------|
| 私钥不能提交到 Git | 会泄露，导致中间人攻击 |
| 私钥不能放进 Docker 镜像 | 镜像可能被导出 |
| 私钥权限 600 | 只有 root 可读 |
| 使用环境变量管理 | 不要硬编码 |

---

## 十八、如果证书过期会发生什么？

### 过期后

```
用户浏览器
    ↓
Nginx（证书已过期）
    ↓
浏览器警告：
"您的连接不是私密连接"
"NET::ERR_CERT_DATE_INVALID"
```

### 影响

| 影响 | 说明 |
|------|------|
| 浏览器警告 | 用户看到红色警告页面 |
| API 请求失败 | 客户端拒绝连接 |
| SEO 下降 | 搜索引擎降低排名 |
| 用户流失 | 用户不敢继续使用 |

### 自动续期

Let's Encrypt 证书 90 天过期，但支持自动续期：

```bash
# certbot 自动续期
sudo certbot renew
```

---

## 十九、单域名、多域名、通配符证书

### 类型对比

| 类型 | 示例 | 覆盖范围 |
|------|------|---------|
| 单域名 | api.seplume.com | 仅一个域名 |
| 多域名 | api.seplume.com + admin.seplume.com | 多个指定域名 |
| 通配符 | *.seplume.com | 所有一级子域名 |

### 通配符规则

```
*.seplume.com 可以匹配：
✅ api.seplume.com
✅ admin.seplume.com
✅ www.seplume.com

*.seplume.com 不能匹配：
❌ seplume.com（根域名）
❌ a.b.seplume.com（二级子域名）
```

### 你的项目选择

```
api.seplume.com
admin.seplume.com
```

建议使用**多域名证书**或**两个单域名证书**。

---

## 二十、完整理解我的项目

### 完整流程

```
用户浏览器
       │
       │ https://api.seplume.com
       ↓
      DNS（解析域名 → IP）
       │
       ↓
   阿里云 ECS 公网 IP
       │
       ↓
     Nginx :443（TLS 终止）
       │
       │ SSL 证书验证身份
       │ TLS 建立加密通道
       ↓
    location /（匹配路径）
       │
       │ proxy_pass
       ↓
 Docker Container
       │
       ↓
 FastAPI :8000（业务逻辑）
```

### 各组件职责

| 组件 | 职责 |
|------|------|
| DNS | 找到服务器 IP |
| SSL 证书 | 证明服务器身份 |
| TLS | 建立安全通信 |
| HTTPS | HTTP + TLS |
| Nginx | 接收请求、TLS 终止、反向代理 |
| location | 决定请求如何处理 |
| proxy_pass | 决定转发给谁 |
| Docker | 隔离运行环境 |
| FastAPI | 处理业务逻辑 |

---

## 二十一、完整请求追踪

### 用户访问 `https://api.seplume.com/users/123`

```
① 浏览器查询 DNS
   api.seplume.com → 106.14.206.226

② 浏览器连接 IP:443
   TCP 三次握手

③ Nginx 接收连接
   监听 443 端口

④ TLS 握手
   Nginx 发送证书
   浏览器验证证书

⑤ 建立 HTTPS 连接
   加密通道建立

⑥ 浏览器发送 HTTP 请求
   GET /users/123

⑦ Nginx 匹配 server
   server_name api.seplume.com

⑧ Nginx 匹配 location
   location /

⑨ Nginx 转发请求
   proxy_pass http://127.0.0.1:8000

 FastAPI 处理
   查询数据库，返回用户数据

⑪ FastAPI 返回响应
   200 OK + JSON

⑫ Nginx 返回给浏览器
   加密传输

⑬ 浏览器显示
   用户信息页面
```

### 每一步的通信双方

| 步骤 | 通信双方 |
|------|---------|
| ① | 浏览器 ↔ DNS 服务器 |
| ②-⑤ | 浏览器 ↔ Nginx |
| ⑥-⑧ | 浏览器 ↔ Nginx |
| -⑪ | Nginx ↔ FastAPI |
| ⑫-⑬ | Nginx ↔ 浏览器 |

---

## 二十二、知识地图

```
                    用户
                     │
                     │ HTTPS（加密传输）
                     ↓
              api.seplume.com
                     │
                     │ DNS（找到服务器）
                     ↓
                  公网 IP
                     │
                     │ :443（HTTPS 端口）
                     ↓
                   Nginx
                     │
              ┌──────┴──────
              │             │
           TLS/HTTPS      HTTP 请求
              │             │
         SSL 证书          location（路径匹配）
         （身份认证）          │
                            │
                       proxy_pass（转发）
                            │
                            ↓
                     FastAPI :8000
                            │
                            ↓
                         业务逻辑
```

### 标注说明

```
DNS：负责找到服务器
SSL Certificate：证明服务器身份
TLS：建立安全通信
HTTPS：HTTP + TLS
Nginx：接收公网请求并反向代理
location：决定请求如何处理
proxy_pass：决定请求转发给谁
FastAPI：处理真正的业务逻辑
```

---

## 二十三、15 个常见误区

### 误区 1：SSL 证书就是 HTTPS
**错误**：SSL 证书是 HTTPS 的组成部分，HTTPS = HTTP + TLS + 证书

### 误区 2：SSL 证书就是加密密码
**错误**：证书包含公钥，用于身份认证和密钥协商，不是密码

### 误区 3：证书里面保存私钥
**错误**：证书只包含公钥，私钥单独保存在服务器上

### 误区 4：HTTPS 不需要 DNS
**错误**：HTTPS 仍然需要 DNS 解析域名到 IP

### 误区 5：有了证书就自动有 HTTPS
**错误**：需要 Nginx 配置证书并监听 443 端口

### 误区 6：申请证书就是在申请一个 IP
**错误**：证书绑定的是域名，不是 IP

### 误区 7：证书配置在 FastAPI 就够了
**错误**：证书配置在 Nginx（TLS 终止层）

### 误区 8：HTTP 也需要 SSL 证书
**错误**：HTTP 不加密，不需要证书

### 误区 9：免费证书不安全
**错误**：Let's Encrypt 证书加密强度与付费证书相同

### 误区 10：Nginx 本身就是 SSL 证书
**错误**：Nginx 是使用证书的软件，证书是独立文件

### 误区 11：证书过期只是浏览器提示，不影响 API
**错误**：客户端会拒绝连接，API 完全不可用

### 误区 12：证书和域名解析是一回事
**错误**：DNS 解决"去哪里"，证书解决"你是谁"

### 误区 13：证书可以随便申请任何域名
**错误**：必须通过域名所有权验证

### 误区 14：私钥可以提交到 Git
**错误**：私钥泄露会导致中间人攻击

### 误区 15：TLS 就等于"把 HTTP 加密一下"
**错误**：TLS 包括身份认证、密钥协商、加密传输等多个步骤

---

## 二十四、一句话解释每个概念

```
DNS：把域名翻译成 IP 地址的电话本
域名：网站的门牌号（如 api.seplume.com）
IP：服务器的实际地址（如 106.14.206.226）
端口：服务器上的不同服务入口（如 443、8000）
HTTP：明文传输数据的协议
HTTPS：加密传输数据的协议（HTTP + TLS）
SSL：过时的安全协议名称（现用 TLS）
TLS：建立安全通信的协议
SSL Certificate：服务器的数字身份证
CA：颁发证书的权威机构
公钥：可以公开的加密钥匙（在证书中）
私钥：必须保密的解密钥匙（在服务器上）
TLS Handshake：浏览器和服务器协商加密参数的过程
Nginx：接收请求、处理 TLS、转发请求的服务器软件
Reverse Proxy：代表后端服务接收请求的代理
FastAPI：处理业务逻辑的 Python Web 框架
```

### 概念串联

```
用户输入域名 → DNS 解析 IP → 连接端口 → 
Nginx 接收 → TLS 握手（用证书验证身份） → 
建立 HTTPS → location 匹配 → proxy_pass 转发 → 
FastAPI 处理业务 → 返回结果
```

---

## 二十五、三个版本总结

### ① 小白版

**SSL 证书是什么？**

就像网站的"身份证"，证明这个网站确实是它声称的那个网站。

**为什么需要它？**

没有证书，你无法确认访问的是不是真正的网站，密码和数据可能被窃取。

**在哪里申请？**

Let's Encrypt（免费）、阿里云、腾讯云等。

**配置在哪里？**

配置在 Nginx 服务器上，告诉 Nginx"这是我的身份证"。

---

### ② 实战版

**你的项目：api.seplume.com + 阿里云 ECS + Nginx + Docker + FastAPI**

1. **申请证书**：
   ```bash
   sudo certbot certonly --standalone -d api.seplume.com
   ```

2. **证书位置**：
   ```
   /etc/letsencrypt/live/api.seplume.com/
   ├── fullchain.pem  ← 证书
   └── privkey.pem    ← 私钥
   ```

3. **配置在 Nginx**：
   ```nginx
   ssl_certificate /etc/letsencrypt/live/api.seplume.com/fullchain.pem;
   ssl_certificate_key /etc/letsencrypt/live/api.seplume.com/privkey.pem;
   ```

4. **FastAPI 不需要配置证书**，它只处理解密后的 HTTP 请求。

---

### ③ 面试版

**什么是 SSL/TLS 证书？**

SSL/TLS 证书是服务器的数字身份证明，由 CA 机构颁发，包含服务器域名、公钥和 CA 签名。

**为什么 HTTPS 需要它？**

HTTPS 需要证书来验证服务器身份，防止中间人攻击。浏览器通过验证证书确认连接的是正确的服务器。

**在哪里申请？**

可以通过 Let's Encrypt（免费）、云厂商或商业 CA 申请。申请时需要验证域名所有权。

**如何配置到 Nginx？**

在 Nginx 配置中指定证书路径：
```nginx
ssl_certificate /path/to/fullchain.pem;
ssl_certificate_key /path/to/privkey.pem;
```
Nginx 使用证书完成 TLS 握手，FastAPI 不需要配置证书。

---

## 最终学习目标

现在你应该能够回答：

> **为什么我访问的是 https://api.seplume.com，浏览器为什么信任这个网站？**

因为：
1. DNS 将域名解析到 ECS IP
2. Nginx 提供 SSL 证书
3. 浏览器验证证书（域名匹配、未过期、CA 可信）
4. TLS 握手建立加密连接
5. HTTPS 安全传输数据

> **HTTPS 为什么安全？**

因为：
1. 证书证明服务器身份（防伪装）
2. TLS 加密传输数据（防窃听）
3. 完整性校验（防篡改）

> **SSL 证书从哪里来？**

从 CA 机构申请（如 Let's Encrypt），通过域名所有权验证后获得。

> **证书最终配置在哪里？**

配置在 Nginx 的 `ssl_certificate` 和 `ssl_certificate_key` 指令中。

> **Nginx 为什么能够使用这个证书？**

因为 Nginx 监听 443 端口，在 TLS 握手时发送证书给浏览器，使用私钥完成密钥协商。