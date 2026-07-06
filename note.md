# pnpm
1、why？ pnpm install 在 monorepo 根目录跑一次就够了，会自动给 apps/* 和 packages/* 都装好。这是 workspace 的好处。

# redis
1、Redis 容器已启动但仍连接失败，测试方法test_refresh_token_success时报的错

---

# 🐳 Docker 网络架构面试题集

> **基于实战项目：RedisInsight 容器连接 Redis 容器的排查过程**

## 目录
- [第一部分：基础概念篇](#第一部分基础概念篇)
- [第二部分：核心原理篇](#第二部分核心原理篇)
- [第三部分：实战场景篇](#第三部分实战场景篇)
- [第四部分：高级优化篇](#第四部分高级优化篇)
- [参考答案速查表](#参考答案速查表)

---

## 第一部分：基础概念篇

### Q1: 什么是 Docker 容器的网络隔离性？

**考察点**：Docker 网络命名空间的基本概念

**核心要点**：
- 每个 Docker 容器拥有**独立的网络命名空间**（Network Namespace）
- 容器内的 `127.0.0.1` / `localhost` 指向的是**容器自身**，不是宿主机
- 不同容器之间默认通过 **Bridge 网桥**进行通信
- 端口映射（Port Mapping）只对**从外部访问容器**有效

**类比理解**：
```
Docker 宿主机 = 一栋公寓楼
每个容器 = 一个独立房间（有独立门牌号）
127.0.0.1 = 我自己的房间
host.docker.internal = 公寓楼前台/总机
```

---

### Q2: 为什么在容器内访问 `127.0.0.1:6379` 连不上宿主机的 Redis？

**考察点**：容器网络隔离的实际影响

**错误认知 vs 正确理解**：

| 错误认知 | 正确理解 |
|---------|---------|
| 127.0.0.1 = 宿主机 | 127.0.0.1 = 容器自己 |
| localhost = 宿主机 | localhost = 容器自己 |
| 端口映射对内部生效 | 端口映射只对外部生效 |

**实际数据流**：
```
❌ 容器内执行：
   RedisInsight → 127.0.0.1:6379 → RedisInsight自己的6379端口（不存在）→ 连接失败

✅ 从宿主机执行：
   浏览器/Python脚本 → 127.0.0.1:6379 → Docker代理 → Redis容器的6379 → 成功
```

---

### Q3: 什么是 `host.docker.internal`？

**考察点**：Docker Desktop 提供的特殊 DNS 解析

**定义**：
> `host.docker.internal` 是 Docker Desktop (Mac/Windows) 提供的特殊 DNS 名称，
> 专门用于**容器内部访问宿主机上的服务**

**工作原理**：
```bash
# Docker Desktop 启动时自动配置：

1. 在容器内的 /etc/hosts 添加条目：
   192.168.65.2  host.docker.internal  host-gateway

2. 设置网络路由：
   容器 → host.docker.internal (192.168.65.2)
         → Docker Desktop 虚拟机
         → Mac/Windows 宿主机
         → 访问宿主机服务 ✅
```

**使用示例**：
```yaml
# docker-compose.yml 或连接配置中：
Host: host.docker.internal  # 不是 127.0.0.1！
Port: 6379
```

---

## 第二部分：核心原理篇

### Q4: 请详细解释 Docker 的 Bridge 网络模式

**考察点**：Docker 默认网络的底层实现

**架构图解**：
```
┌─────────────────────────────────────────────────────┐
│ Docker 宿主机                                        │
│                                                     │
│   ┌──────────────────────────────────────────┐      │
│   │          docker0 网桥 (虚拟交换机)         │      │
│   │                                          │      │
│   │   ┌─────────┐    ┌─────────┐             │      │
│   │   │ veth-ABC│    │ veth-XYZ│             │      │
│   │   └────┬────┘    └────┬────┘             │      │
│   │        │              │                  │      │
│   │   ┌────┴────┐   ┌────┴────┐            │      │
│   │   │ContainerA│   │ContainerB│           │      │
│   │   │(Redis)   │   │(Insight)│            │      │
│   │   │172.17.0.2│   │172.17.0.3│           │      │
│   │   └─────────┘   └─────────┘             │      │
│   └──────────────────────────────────────────┘      │
│                                                     │
│   宿主机网卡：192.168.1.100                          │
│   端口映射：6379→ContainerA:6379                     │
└─────────────────────────────────────────────────────┘
```

**关键特性**：
1. 每个容器获得独立的虚拟网卡和 IP 地址
2. 容器间可以通过 IP 或容器名通信
3. 容器无法直接访问宿主机的 127.0.0.1
4. 需要通过端口映射暴露服务给外部

---

### Q5: 端口映射（Port Mapping）的工作机制是什么？

**考察点**：Docker 如何将外部流量转发到容器

**配置方式**：
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"  # 格式：宿主机端口:容器端口
```

**数据流向详解**：
```
外部请求流程：
浏览器/客户端
    ↓
127.0.0.1:6379 (宿主机)
    ↓
docker-proxy 进程（用户空间）
    ↓
iptables NAT 规则（内核空间）
    ↓
veth-xxx 虚拟网卡
    ↓
docker0 网桥
    ↓
容器内部的 6379 端口
    ↓
Redis 进程处理请求 ✅
```

**重要限制**：
```bash
# ❌ 这个规则只对"从外部进入"的流量生效
# 容器内部访问 127.0.0.1 不会触发端口映射！

# 验证方法：
docker exec redisinsight wget -qO- http://127.0.0.1:6379
# 失败！因为 127.0.0.1 是容器自己，不是宿主机
```

---

### Q6: `host.docker.internal` 在不同平台上的实现差异？

**考察点**：跨平台兼容性和底层实现

| 平台 | 支持情况 | 实现方式 |
|------|---------|---------|
| **Docker Desktop (Mac)** | ✅ 原生支持 | 特殊网关 + DNS 注入 |
| **Docker Desktop (Windows)** | ✅ 原生支持 | 同上 |
| **Linux (原生 Docker)** | ⚠️ 不支持 | 需要手动配置 |

**Linux 解决方案**：
```bash
# 方法1：使用 --add-host 参数
docker run --add-host=host.docker.internal:host-gateway myapp

# 方法2：使用 docker-compose extra_hosts
services:
  myapp:
    extra_hosts:
      - "host.docker.internal:host-gateway"

# 方法3：直接使用宿主机 IP（不推荐）
# 先获取：hostname -I | awk '{print $1}'
# 然后硬编码到配置中
```

**获取宿主机 IP 的通用方法**：
```bash
Mac:
  ipconfig getifaddr en0

Linux:
  ip route get 1 | awk '{print $7; exit}'

Windows:
  ipconfig | findstr /i "IPv4"
```

---

## 第三部分：实战场景篇

### Q7: 你在实际项目中遇到过容器网络问题吗？如何解决的？

**考察点**：故障排查能力和实战经验

**真实案例（你的项目）**：

#### **问题描述**
```
环境：
- Redis 运行在 Docker 容器中（dance-saas-redis:6379）
- RedisInsight 也运行在 Docker 容器中（redisinsight:5540）
- 需要在 RedisInsight GUI 中连接 Redis 查看缓存数据

现象：
- RedisInsight 中填写 Host: 127.0.0.1, Port: 6379
- 点击 Test Connection 报错："Could not connect to 127.0.0.1:6379"
- 但从宿主机命令行执行 redis-cli ping 返回 PONG ✅
```

#### **排查步骤**

```bash
Step 1: 确认 Redis 容器运行正常
  docker ps | grep redis
  # 输出：Up 49 minutes (healthy) ✅

Step 2: 确认端口监听
  lsof -i :6379
  # 输出：*:6379 (LISTEN) ✅

Step 3: 测试 Redis 功能
  docker exec dance-saas-redis redis-cli ping
  # 输出：PONG ✅

Step 4: 发现关键线索
  docker ps | grep redisinsight
  # 输出：redisinsight 也在容器中运行！

Step 5: 定位根因
  # 两个容器都在 Docker 内部
  # RedisInsight 的 127.0.0.1 ≠ 宿主机的 127.0.0.1
```

#### **解决方案**

```bash
修改 RedisInsight 连接配置：
  Old: Host = 127.0.0.1  ❌
  New: Host = host.docker.internal  ✅

验证：
  点击 Test Connection → Connection successful ✅
  可以看到 Redis 缓存数据（包括 Token 黑名单）
```

#### **经验总结**

```markdown
✅ 学到的知识点：
1. 容器网络隔离是 Docker 的基本特性
2. 不能假设容器内的 127.0.0.1 就是宿主机
3. host.docker.internal 是容器访问宿主机的标准方案
4. 排查问题时要从网络层面思考，不能只看应用层

🛠️ 故障排查方法论：
1. 确认基础设施状态（容器是否运行）
2. 确认网络连通性（端口监听）
3. 测试服务可用性（功能验证）
4. 分析网络拓扑（容器 vs 宿主机）
5. 应用正确的连接方式
```

---

### Q8: 如何选择合适的容器间通信方式？

**考察点**：架构设计决策能力

**四种方案对比**：

| 方案 | 适用场景 | 配置示例 | 优缺点 |
|------|---------|----------|--------|
| **host.docker.internal** | 容器访问宿主机服务 | `Host: host.docker.internal` | ✅ 简单直观<br>❌ 仅限访问宿主机 |
| **容器名称/DNS** | 同一 compose 文件中的服务 | `Host: service_name` | ✅ 服务发现自动<br>❌ 只能访问同网络容器 |
| **宿主机 IP** | 跨网络或特殊需求 | `Host: 192.168.1.100` | ✅ 通用性强<br>❌ IP 可能变化 |
| **共享网络** | 多个 compose 项目通信 | 自定义 network | ✅ 灵活可控<br>❌ 配置复杂 |

**决策树**：
```
需要连接的目标是什么？
│
├─ 宿主机上的服务（非容器化）
│   └─ 使用 host.docker.internal ✅
│
├─ 同一个 docker-compose.yml 中的其他服务
│   └─ 使用 service name（容器名）✅
│
├─ 不同 docker-compose.yml 中的服务
│   ├─ 共享自定义 network
│   └─ 或使用 host.docker.internal（如果目标在宿主机暴露了端口）
│
└─ 外部服务器
    └─ 使用实际的 IP 或域名
```

---

### Q9: 如何在生产环境中管理 Docker 网络？

**考察点**：生产环境的最佳实践

**推荐配置**：

```yaml
version: '3.8'

services:
  api:
    networks:
      - backend     # 数据库/Redis 层
      - frontend    # 对外暴露层
  
  redis:
    networks:
      - backend     # 只允许后端访问
    # 不加入 frontend 网络 → 安全隔离
  
  postgres:
    networks:
      - backend     # 只允许后端访问

networks:
  backend:
    driver: bridge
    internal: true  # 内部网络，禁止外部访问
    
  frontend:
    driver: bridge
    # 允许外部通过端口映射访问
```

**安全最佳实践**：
```bash
1. 最小权限原则
   - 只暴露必要的端口
   - 限制网络访问范围

2. 网络分段
   - 前端/后端/数据库分离
   - internal: true 保护敏感服务

3. 避免使用 host 网络模式
   - 除非绝对必要
   - 会失去隔离性优势

4. 使用 secrets 管理敏感信息
   - 不要在环境变量中传密码
```

---

## 第四部分：高级优化篇

### Q10: Docker 网络性能如何优化？

**考察点**：性能调优经验

**常见瓶颈与优化策略**：

```markdown
1. 减少网络跳数
   问题：容器 A → 网桥 → 容器 B（多次上下文切换）
   优化：使用 host 网络模式（牺牲安全性换性能）

2. 批量操作减少往返
   问题：频繁的小请求导致延迟累积
   优化：使用 Pipeline / 事务批量提交

3. 选择合适的驱动
   Bridge: 通用性好，性能中等
   Overlay: 跨主机，性能较差
   Host: 性能最好，无隔离
   IPvlan/Macvlan: 接近物理网络性能

4. 调整 MTU 大小
   默认 1500，某些场景可调整提升吞吐量
```

**监控指标**：
```bash
# 查看容器网络统计
docker stats --no-stream

# 关注指标：
- NET I/O: 网络输入输出量
- PIDs: 进程数（间接反映连接数）
- CPU/MEM: 资源占用
```

---

### Q11: 如何设计多租户系统的 Docker 部署架构？

**考察点**：结合业务场景的架构设计

**基于你的项目的推荐架构**：

```yaml
# 方案A：单实例多租户（当前方案）
version: '3.8'
services:
  api:
    build: .
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    networks:
      - app-network

  postgres:
    image: postgres:15-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - app-network

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data
    networks:
      - app-network

networks:
  app-network:

volumes:
  pgdata:
  redisdata:
```

**扩展方案（未来）**：
```yaml
# 方案B：每个大租户独立部署（高隔离要求时）
# 使用 Docker Compose profiles 或多个 compose 文件

# tenant-a/docker-compose.yml
services:
  api-tenant-a:
    environment:
      - TENANT_ID=a
      - REDIS_URL=redis://redis-a:6379/0
  redis-a:
    # ...

# tenant-b/docker-compose.yml  
services:
  api-tenant-b:
    environment:
      - TENANT_ID=b
      - REDIS_URL=redis://redis-b:6379/0
  redis-b:
    # ...
```

---

## 参考答案速查表

### ⭐ 必背知识点（5个）

1. **容器网络隔离**：每个容器有独立的网络栈，127.0.0.1 指向自身
2. **host.docker.internal**：容器访问宿主机的标准 DNS 名称
3. **端口映射方向性**：只对外部→容器生效，不对容器内部→宿主机生效
4. **Bridge 网络模式**：Docker 默认网络，通过虚拟网桥连接容器
5. **服务发现**：同一 compose 中的容器可通过服务名互相访问

### 🔥 TOP5 高频面试题

| 排名 | 问题 | 出现频率 | 难度 |
|------|------|---------|------|
| 1 | 为什么容器内 127.0.0.1 连不上宿主机？ | ★★★★★ | ★★☆ |
| 2 | host.docker.internal 是什么原理？ | ★★★★☆ | ★★★ |
| 3 | 如何排查 Docker 网络问题？ | ★★★★☆ | ★★★ |
| 4 | Bridge vs Host 网络模式区别？ | ★★★☆☆ | ★★☆ |
| 5 | 生产环境如何设计网络架构？ | ★★★☆☆ | ★★★★ |

### 💡 加分技巧

1. **画图说明**：面试时画出网络拓扑图，展示清晰思路
2. **举实例**：用你项目中的 RedisInsight+Redis 案例
3. **讲权衡**：不同方案的 trade-off（安全 vs 性能 vs 复杂度）
4. **提监控**：主动提到网络监控和故障排查工具
5. **联系业务**：从多租户隔离角度谈网络设计的重要性

---

## 📚 学习资源

- [Docker Networking Documentation](https://docs.docker.com/network/)
- [Understanding Container Networking](https://kubernetes.io/docs/concepts/cluster-administration/networking/)
- [Docker Compose Networking](https://docs.docker.com/compose/networking/)
- [host.docker.internal Explanation](https://docs.docker.com/desktop/networking/#i-want-to-connect-from-a-container-to-the-host)

---

*文档版本：v1.0*
*最后更新：2026-06-30*
*基于项目实战：RedisInsight 连接 Redis 容器排查过程*