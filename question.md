# 📋 待解决问题清单 (Questions & Issues)

> **记录开发过程中遇到的待解决问题和需要后续处理的事项**

---

## 🐳 Docker & 基础设施相关问题

### ❌ Issue #001: PyCharm Database 工具无法连接 Docker 容器中的 PostgreSQL

**状态**：🔴 未解决 (Unresolved)  
**优先级**：⭐⭐⭐ 中等  
**创建时间**：2026-06-30  
**最后更新**：2026-06-30  
**标签**：`docker` `postgresql` `pycharm` `database` `connection`

---

#### 📝 问题描述

在 PyCharm IDE 中使用内置的 **Database** 工具尝试连接运行在 Docker 容器中的 **PostgreSQL** 数据库时，无法成功建立连接。

**环境信息**：
```
操作系统: macOS
IDE: PyCharm (版本未知)
数据库: PostgreSQL 15-alpine (Docker容器)
容器名: dance-saas-postgres
端口映射: 5432:5432 (宿主机:容器)
```

---

#### 🔍 问题分析

##### **理论连接方式**

根据 Docker 网络原理：

| 运行位置 | 访问目标 | 应使用的 Host |
|---------|---------|--------------|
| **PyCharm (宿主机)** | Docker PostgreSQL 容器 | `localhost` 或 `127.0.0.1` ✅ |

**关键点**：
- ✅ PyCharm 运行在**宿主机（Mac）**上，不是 Docker 容器内
- ✅ 因此应该使用 `localhost` 直接访问端口映射后的服务
- ⚠️ 不像 RedisInsight（运行在 Docker 内部）那样需要 `host.docker.internal`

##### **正确的连接参数**（来自 .env 配置）

```yaml
Host:     localhost
Port:     5432
User:     dance
Password: dance_dev_pass
Database: dance_saas
URL:      postgresql://dance:dance_dev_pass@localhost:5432/dance_saas
```

---

#### 🛠️ 排查步骤（已执行）

##### ✅ Step 1: 检查容器状态

```bash
docker ps | grep postgres
# 预期输出：Up XX minutes (healthy)
```

**结果**：✅ 容器正常运行

---

##### ✅ Step 2: 检查端口监听

```bash
lsof -i :5432
# 预期输出：*:6379 (LISTEN)
```

**结果**：✅ 端口正常监听

---

##### ✅ Step 3: 测试数据库连通性

```bash
docker exec dance-saas-postgres pg_isready -U dance -d dance_saas
# 预期输出：accepting connections
```

**结果**：✅ 数据库就绪

---

##### ❌ Step 4: PyCharm Database 配置测试

**操作**：
1. 打开 PyCharm → View → Tool Windows → Database
2. 点击 `+` → Data Source → PostgreSQL
3. 填写连接参数
4. 点击 "Test Connection"

**结果**：❌ **连接失败**（具体错误信息待补充）

---

#### 💡 可能的原因假设

| 编号 | 假设原因 | 可能性 | 验证方法 | 状态 |
|------|---------|--------|---------|------|
| H1 | **SSL 配置问题** - PyCharm 默认启用 SSL，但 Docker PG 未配置 | ⭐⭐⭐⭐ 高 | 在 Advanced 设置中关闭 SSL | 🔍 待验证 |
| H2 | **驱动程序问题** - PyCharm 缺少或版本不兼容的 PostgreSQL 驱动 | ⭐⭐⭐ 中 | 更新/重新下载 JDBC 驱动 | 🔍 待验证 |
| H3 | **认证方式问题** - md5/scram-sha-256 不匹配 | ⭐⭐ 低 | 检查 pg_hba.conf | 🔍 待验证 |
| H4 | **网络防火墙/VPN 干扰** - 本地安全软件阻止连接 | ⭐⭐ 低 | 关闭 VPN/防火墙后重试 | 🔍 待验证 |
| H5 | **PyCharm 版本 Bug** - 特定版本的已知问题 | ⭐ 低 | 升级到最新版或查看 issue tracker | 🔍 待验证 |

---

#### 🎯 解决方案建议

##### **方案 A：禁用 SSL 连接（最可能有效）**

**步骤**：
1. 在 PyCharm Database 配置窗口中
2. 切换到 **"Advanced"** 标签页
3. 找到 **"SSL"** 部分
4. 选择 **"No SSL"** 或取消勾选 **"Use SSL"**
5. 重新点击 **"Test Connection"**

**预期结果**：✅ 连接成功

---

##### **方案 B：使用 URL 方式连接**

**步骤**：
1. 在配置窗口中选择 **"URL only"** 标签
2. 输入完整连接字符串：
   ```
   jdbc:postgresql://localhost:5432/dance_saas?user=dance&password=dance_dev_pass&ssl=false
   ```
3. 注意添加 `ssl=false` 参数

**预期结果**：✅ 绕过 SSL 问题

---

##### **方案 C：更新 JDBC 驱动**

**步骤**：
1. 在 PyCharm 中打开 **Settings/Preferences**
2. 导航到 **Build, Execution, Deployment** → **Data Sources** → **Drivers**
3. 找到 **PostgreSQL** 驱动
4. 点击 **"Download"** 或 **"Update"** 获取最新版本
5. 重启 PyCharm 后重新配置连接

---

##### **方案 D：使用命令行工具替代（临时方案）**

如果 GUI 工具暂时不可用，可以使用以下替代工具：

1. **DBeaver**（免费开源）
   - 下载地址：https://dbeaver.io/download/
   - 对 Docker 数据库支持更好

2. **pgAdmin 4**（PostgreSQL 官方工具）
   - 可通过 Docker 运行：
     ```bash
     docker run -p 8080:80 \
       -e 'PGADMIN_DEFAULT_EMAIL=user@domain.com' \
       -e 'PGADMIN_DEFAULT_PASSWORD=SuperSecret' \
       -d dpage/pgadmin4
     ```

3. **VS Code 插件**
   - 安装 "PostgreSQL" 扩展
   - 通常比 PyCharm Database 更稳定

---

#### 📌 相关资源与参考

**官方文档**：
- [PyCharm Database Documentation](https://www.jetbrains.com/help/pycharm/working-with-databases.html)
- [Docker PostgreSQL Image](https://hub.docker.com/_/postgres)

**类似问题讨论**：
- [StackOverflow: PyCharm can't connect to PostgreSQL in Docker](https://stackoverflow.com/questions/tagged/pycharm+docker+postgresql)
- [JetBrains Issue Tracker](https://youtrack.jetbrains.com/issues/PY)

**相关笔记文件**：
- `/Users/lixiang/Desktop/class_booking_system/note.md` - Docker 网络架构面试题（包含 host.docker.internal 原理）

---

#### ✅ 验证标准（完成条件）

当满足以下**任意一项**时，此问题可标记为已解决：

- [ ] **主要目标**：PyCharm Database 工具能成功连接并浏览 dance_saas 数据库
- [ ] **次要目标**：找到可用的替代工具（如 DBeaver/pgAdmin）并能正常使用
- [ ] **最低目标**：明确问题根因并记录解决方案（即使暂不使用 PyCharm Database）

---

#### 📊 进度跟踪

| 日期 | 操作 | 结果 | 下一步 |
|------|------|------|--------|
| 2026-06-30 | 创建问题记录 | - | 尝试方案A（禁用SSL） |
| - | - | - | - |
| - | - | - | - |

---

#### 💬 备注

```markdown
**重要提示**：
1. 此问题不影响项目开发和测试（可通过代码和命令行访问数据库）
2. 主要影响开发体验（无法在 IDE 中可视化查看数据）
3. 建议优先级：中等（可在空闲时解决）

**关联问题**：
- Issue #000: RedisInsight 连接 Docker Redis（已解决 ✅）
  - 解决方案：使用 host.docker.internal
  - 对比参考：PyCharm 不需要此方案（因为运行位置不同）
```

---

## 🔄 其他待解决问题

*(目前只有上述一个问题，后续遇到新问题时继续在此文档中添加)*

---

### 📝 如何添加新问题

按照以下模板格式添加新的 issue：

```markdown
### ❌ Issue #XXX: [问题标题]

**状态**：🔴 未解决 / 🟡 进行中 / 🟠 已验证 / ✅ 已解决  
**优先级**：⭐⭐⭐⭐⭐ 紧急 / ⭐⭐⭐⭐ 高 / ⭐⭐⭐ 中 / ⭐⭐ 低 / ⭐ 极低  
**创建时间**：YYYY-MM-DD  
**标签**：`tag1` `tag2` `tag3`

---

#### 📝 问题描述

[详细描述问题的现象、环境、影响范围]

#### 🔍 问题分析

[初步分析和排查思路]

#### 🛠️ 排查步骤

[已执行的排查步骤和结果]

#### 💡 可能的原因假设

[列出可能的根本原因及验证计划]

#### 🎯 解决方案建议

[提出解决方案和备选方案]

#### 📌 相关资源与参考

[链接、文档、相关文件]

#### ✅ 验证标准

[定义什么情况下算作问题解决]

#### 📊 进度跟踪

[时间线记录]
```

---

## 📈 统计概览

| 状态 | 数量 | 占比 |
|------|------|------|
| 🔴 未解决 | 1 | 100% |
| 🟡 进行中 | 0 | 0% |
| 🟠 已验证 | 0 | 0% |
| ✅ 已解决 | 0 | 0% |
| **总计** | **1** | **100%** |

**按优先级分布**：
- ⭐⭐⭐⭐⭐ 紧急：0 个
- ⭐⭐⭐⭐ 高：0 个
- ⭐⭐⭐ 中：1 个 (Issue #001)
- ⭐⭐ 低：0 个
- ⭐ 极低：0 个

---

*文档维护说明*：
- 此文档由开发者手动维护
- 每次更新问题时请同步修改统计概览
- 问题解决后请保留记录（不要删除），仅更改状态为 ✅
- 定期review未解决的问题，避免积压

---

*最后更新：2026-06-30*
*文档版本：v1.0*
