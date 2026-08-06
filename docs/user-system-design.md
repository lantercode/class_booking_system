# 舞蹈机构 SaaS 用户体系架构设计

---

## 方案选择：推荐方案 C（混合模式）

| 方案 | 核心逻辑 | 适用场景 | 推荐度 |
|------|---------|---------|--------|
| A | 用户自主注册 + 选身份 | 开放平台（抖音/小红书类） | 不推荐 |
| B | 管理员全量创建 | 企业内部系统 | 太封闭 |
| **C** | **管理员预创建 + 微信绑定** | **SaaS 商业产品** | **强烈推荐** |

**核心原因：舞蹈机构是 B2B2C 模式，机构付费、学员使用，学员身份必须由机构确认，不能自选。**

---

## 一、用户生命周期设计

### 1.1 新学员如何加入系统？

```
┌─────────────────────────────────────────────────────┐
│                  学员加入三通道                        │
├───────────────┬───────────────┬───────────────────────┤
│  通道1: 报名后自动创建  │ 通道2: 管理员手动创建  │ 通道3: 微信扫码注册申请  │
│  (主要通道 80%)         │ (补充通道 15%)        │ (辅助通道 5%)          │
├───────────────┼───────────────┼───────────────────────┤
│ 线下/线上报名             │ 前台录入新学员信息      │ 学员扫码小程序           │
│      ↓                   │      ↓                 │      ↓                 │
│ 管理员创建学员档案        │ 创建学员 + 关联课程      │ 微信授权登录             │
│      ↓                   │      ↓                 │      ↓                 │
│ 生成学员二维码            │ 发送邀请链接/二维码       │ 填写基本信息             │
│      ↓                   │      ↓                 │      ↓                 │
│ 学员扫码绑定微信          │ 学员扫码绑定微信         │ 提交注册申请             │
│      ↓                   │      ↓                 │      ↓                 │
│ 自动关联已有档案          │ 自动关联已有档案         │ 管理员审核               │
│      ↓                   │      ↓                 │      ↓                 │
│ 进入学员端 确认           │ 进入学员端 确认          │ 审核通过 -> 进入学员端 确认 │
└───────────────┴───────────────┴───────────────────────┘
```

**关键设计：学员不能自己选择"我是学员"，因为身份是由机构付费关系决定的。**

### 1.2 老学员如何迁移？

```
迁移策略：
1. 管理员批量导入 Excel（姓名、手机号、剩余课时、原有课程）
2. 系统生成专属绑定二维码，打印张贴或私发
3. 老学员扫码 -> 微信授权 -> 自动匹配手机号 -> 绑定成功
4. 如果手机号不匹配 -> 提示联系管理员更新
```

### 1.3 教师如何加入？

```
教师加入流程：
1. 管理员后台创建教师账号（姓名、手机号、教师编号、可授课程）
2. 系统生成教师专属绑定二维码
3. 教师扫码 -> 微信授权 -> 绑定 -> 进入教师端
4. 教师端首次登录引导：设置教学偏好、可用时间段
```

**教师绝对不允许自主注册。** 这和安全无关，是业务逻辑——机构雇了谁、谁能上课，必须由机构决定。

### 1.4 用户注销如何处理？

```
注销策略：
┌──────────────────────────────────────────┐
│ 学员注销                                   │
│ -> 软删除（status = INACTIVE）              │
│ -> 保留上课记录、消费记录（财务审计需要）        │
│ -> 解绑微信（openid 置空，可重新绑定新学员）     │
│ -> 180天后可物理删除（GDPR合规）              │
├──────────────────────────────────────────┤
│ 教师注销                                   │
│ -> 离职处理（status = RESIGNED）             │
│ -> 保留授课记录                              │
│ -> 转移未完成的排课给其他教师                   │
│ -> 解绑微信                                  │
└──────────────────────────────────────────┘
```

---

## 二、微信身份 vs 业务身份设计

### 核心原则：一个微信账号 = 一个业务身份 = 一个租户

```
┌─────────────────────────────────────────────────────┐
│                    身份模型                           │
│                                                      │
│  WeChat Account (认证层)                              │
│  ├── openid (小程序唯一标识)                           │
│  ├── unionid (跨小程序/公众号统一标识)                  │
│  ├── phone (微信手机号)                               │
│  └── nickname / avatar (微信头像昵称)                  │
│           │                                          │
│           │ 1:1 绑定                                  │
│           ▼                                          │
│  User (业务层)                                        │
│  ├── user_type: STUDENT | TEACHER | ADMIN             │
│  ├── tenant_id (所属机构)                             │
│  └── status: ACTIVE | INACTIVE | RESIGNED             │
│           │                                          │
│           │ 1:1                                      │
│           ▼                                          │
│  Student / Teacher (详情层)                            │
│  └── 扩展信息（学员号、教师编号、剩余课时等）              │
└─────────────────────────────────────────────────────┘
```

### 为什么一个微信 = 一个业务身份？

```
不支持一个微信多个身份的原因：
  - 教师在小程序里要切换"教师模式"和"学员模式"？
  - 权限混乱：同一个微信既是教师又是学员，数据隔离怎么做？
  - 教师端和学员端是不同的微信小程序（AppId不同），天然隔离

正确做法：
  - 学员端小程序 -> 只能绑定 Student 身份
  - 教师端小程序 -> 只能绑定 Teacher 身份
  - 管理后台 Web -> Admin 身份，账号密码登录
  - 如果某教师同时是其他机构的学员 -> 用不同租户隔离
```

### 特殊情况：教师也是管理员

```
教师小张同时也是机构管理员：

方案：一个 user，两个角色
  user 表：user_type = TEACHER
  user_roles 表：
    ├── role = TEACHER (教师端小程序可用)
    └── role = ADMIN   (管理后台 Web 可用)

  教师端小程序 -> 识别 TEACHER 角色 -> 进入教师端
  管理后台 Web  -> 识别 ADMIN 角色  -> 进入管理后台
  同一套账号密码/微信登录，不同入口看到不同界面
```

---

## 三、权限模型设计（RBAC + 租户隔离）

### 3.1 角色体系

```
角色层级：
┌──────────────────────────────────────────────┐
│ SUPER_ADMIN (平台级，SaaS 平台运营方)           │
│   └── 管理所有租户、查看全局数据、系统配置        │
├──────────────────────────────────────────────┤
│ TENANT_ADMIN (租户级，舞蹈机构老板/店长)         │
│   └── 管理本机构所有数据、创建教师/学员、查看报表  │
├──────────────────────────────────────────────┤
│ TEACHER (教师)                                │
│   └── 查看排课、管理学员、签到、请假审批          │
├──────────────────────────────────────────────┤
│ STUDENT (学员)                                │
│   └── 查看课程、预约、请假、查看学习记录          │
├──────────────────────────────────────────────┤
│ RECEPTION (前台)                              │
│   └── 录入学员、办理报名、收费、打印小票          │
└──────────────────────────────────────────────┘
```

### 3.2 权限粒度

```
权限设计（细粒度，可组合）：
┌──────────────────────────────────────────────────┐
│ 资源             │ 操作                          │
│ student          │ create, read, update, delete  │
│ teacher          │ create, read, update, delete  │
│ course           │ create, read, update, delete  │
│ schedule         │ create, read, update, delete  │
│ booking          │ create, read, cancel, checkin │
│ order            │ create, read, refund          │
│ report           │ read, export                  │
│ settings         │ read, update                  │
└──────────────────────────────────────────────────┘

角色 = 一组权限的集合（可以自定义）
TENANT_ADMIN = { student:*, teacher:*, course:*, schedule:*, booking:*, order:*, report:*, settings:* }
TEACHER      = { schedule:read, booking:read, booking:checkin, student:read }
STUDENT      = { course:read, schedule:read, booking:create, booking:cancel, booking:read }
```

### 3.3 关键设计决策：角色固定绑定 vs 动态授权？

```
推荐：固定角色 + 可扩展权限组合

固定角色：TENANT_ADMIN, TEACHER, STUDENT, RECEPTION
  -> 每个 user 必须属于至少一个固定角色
  -> 固定角色决定用户在哪个端（小程序/Web）操作

动态权限：每个租户可以自定义角色
  -> 例如：某机构想要"高级教师"角色，多一个 schedule:create 权限
  -> 租户管理员可以创建自定义角色、分配权限组合
```

---

## 四、数据库设计

### 4.1 核心表结构

```sql
-- ============================================================
-- 1. 微信认证表（认证层，与业务解耦）
-- ============================================================
CREATE TABLE wechat_accounts (
    id              BIGINT PRIMARY KEY,
    openid          VARCHAR(64)  NOT NULL,
    unionid         VARCHAR(64),
    appid           VARCHAR(32)  NOT NULL,
    phone           VARCHAR(20),
    nickname        VARCHAR(100),
    avatar_url      VARCHAR(500),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    
    UNIQUE(openid, appid)
);

-- ============================================================
-- 2. 业务用户表（业务层，核心）
-- ============================================================
CREATE TABLE users (
    id              BIGINT PRIMARY KEY,
    public_id       UUID         NOT NULL UNIQUE,
    tenant_id       BIGINT       NOT NULL,
    wechat_id       BIGINT,
    user_type       VARCHAR(16)  NOT NULL,
    name            VARCHAR(50)  NOT NULL,
    phone           VARCHAR(20),
    password_hash   VARCHAR(256),
    status          VARCHAR(16)  NOT NULL DEFAULT 'ACTIVE',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    
    INDEX idx_users_tenant (tenant_id),
    INDEX idx_users_phone (tenant_id, phone),
    UNIQUE(tenant_id, phone)
);

-- ============================================================
-- 3. 学员详情表（扩展表，1:1 user）
-- ============================================================
CREATE TABLE students (
    id              BIGINT PRIMARY KEY,
    user_id         BIGINT       NOT NULL UNIQUE,
    student_no      VARCHAR(32),
    birthday        DATE,
    gender          VARCHAR(8),
    emergency_contact VARCHAR(20),
    emergency_name  VARCHAR(50),
    remaining_hours DECIMAL(8,2) NOT NULL DEFAULT 0,
    total_hours     DECIMAL(8,2) NOT NULL DEFAULT 0,
    joined_at       DATE,
    source          VARCHAR(32),
    notes           TEXT,
    
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================================
-- 4. 教师详情表（扩展表，1:1 user）
-- ============================================================
CREATE TABLE teachers (
    id              BIGINT PRIMARY KEY,
    user_id         BIGINT       NOT NULL UNIQUE,
    teacher_no      VARCHAR(32),
    bio             TEXT,
    specialties     TEXT[],
    hourly_rate     DECIMAL(10,2),
    max_weekly_hours INT DEFAULT 20,
    joined_at       DATE,
    certificate_urls TEXT[],
    status          VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================================
-- 5. 角色表
-- ============================================================
CREATE TABLE roles (
    id              BIGINT PRIMARY KEY,
    tenant_id       BIGINT,
    name            VARCHAR(50)  NOT NULL,
    display_name    VARCHAR(50)  NOT NULL,
    is_system       BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    
    UNIQUE(tenant_id, name)
);

-- ============================================================
-- 6. 权限表
-- ============================================================
CREATE TABLE permissions (
    id              BIGINT PRIMARY KEY,
    resource        VARCHAR(50)  NOT NULL,
    action          VARCHAR(32)  NOT NULL,
    description     VARCHAR(200),
    
    UNIQUE(resource, action)
);

-- ============================================================
-- 7. 角色-权限关联表
-- ============================================================
CREATE TABLE role_permissions (
    id              BIGINT PRIMARY KEY,
    role_id         BIGINT       NOT NULL,
    permission_id   BIGINT       NOT NULL,
    
    UNIQUE(role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id),
    FOREIGN KEY (permission_id) REFERENCES permissions(id)
);

-- ============================================================
-- 8. 用户-角色关联表
-- ============================================================
CREATE TABLE user_roles (
    id              BIGINT PRIMARY KEY,
    user_id         BIGINT       NOT NULL,
    role_id         BIGINT       NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    
    UNIQUE(user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);
```

### 4.2 为什么这样设计？

```
设计原则：
┌────────────────────────────────────────────────────────────┐
│ 1. wechat_accounts 与 users 分离                           │
│    原因：微信是认证手段，不是业务身份。                      │
│    管理员不需要微信也能登录后台。                            │
│    一个微信被注销后，可以绑定另一个业务用户。                 │
│                                                             │
│ 2. users 与 students/teachers 分离（1:1 扩展表）             │
│    原因：users 是通用身份，students/teachers 是专用扩展。     │
│    users 表保持精简，高频查询不拖慢。                         │
│    未来新增"前台"角色，只需加一张 receptionists 扩展表。       │
│                                                             │
│ 3. 固定 user_type + 灵活 role                               │
│    原因：user_type 决定"哪个端登录"，role 决定"能做什么"。     │
│    一个 TEACHER 类型的 user 可以同时拥有 TEACHER 和            │
│    TENANT_ADMIN 两个 role，实现教师兼任管理员。               │
│                                                             │
│ 4. tenant_id 在 users 表上                                  │
│    原因：所有资源都挂租户，SaaS 多租户天然隔离。              │
│    查询时自动过滤 tenant_id，防止跨机构数据泄露。             │
└────────────────────────────────────────────────────────────┘
```

---

## 五、登录流程设计

### 5.1 学员登录流程

```
学员端小程序
═══════════════════════════════════════════════════

  打开小程序
      │
      ▼
  检查本地 token
      │
      ├── 有效 ──→ 直接进入学员端 确认
      │
      └── 无效
          │
          ▼
  wx.login() 获取 code
          │
          ▼
  POST /api/v1/auth/wechat/login
  { code, appid: "student_miniapp" }
          │
          ▼
  后端用 code 换取 openid + unionid
          │
          ▼
  查询 wechat_accounts 是否已绑定 user
          │
          ├── 已绑定 ──→ 检查 user.status
          │                │
          │                ├── ACTIVE ──→ 签发 JWT -> 进入学员端 确认
          │                └── INACTIVE ──→ 提示"账号已停用，请联系机构"
          │
          └── 未绑定 ──→ 返回 bind_token（临时凭证）
                          │
                          ▼
                      引导用户输入手机号
                          │
                          ▼
                      POST /api/v1/auth/wechat/bind
                      { bind_token, phone }
                          │
                          ▼
                      查询 users 表（tenant_id + phone）
                          │
                          ├── 找到学员 ──→ 绑定 wechat_accounts.user_id
                          │                │
                          │                └── 签发 JWT -> 进入学员端 确认
                          │
                          └── 未找到 ──→ 提示"未找到您的学员信息，
                                          请联系机构前台"
```

### 5.2 教师登录流程

```
教师端小程序（流程与学员端相同，但 AppId 不同）
═══════════════════════════════════════════════════

  关键差异：
  1. appid = "teacher_miniapp"
  2. 绑定查询时过滤 user_type = 'TEACHER'
  3. JWT payload 中包含 user_type = 'TEACHER'
  4. 进入教师端后，前端根据 role 权限渲染菜单
```

### 5.3 管理员登录流程

```
管理后台 Web
═══════════════════════════════════════════════════

  打开管理后台
      │
      ▼
  输入账号 + 密码
      │
      ▼
  POST /api/v1/auth/admin/login
  { phone, password }
      │
      ▼
  查询 users 表
  phone + password_hash 验证
  user_type IN ('ADMIN', 'TENANT_ADMIN')
      │
      ├── 验证成功 ──→ 签发 JWT（含 tenant_id, roles）
      │                │
      │                └── 进入管理后台 确认
      │
      └── 验证失败 ──→ 错误提示

  ─────────────────────────────────────────────

  可选：企业微信扫码登录
  （适用于大型连锁机构，与内部 IM 打通）
      │
      ▼
  企业微信 OAuth2.0 授权
      │
      ▼
  获取 corp_id + user_id
      │
      ▼
  查询绑定关系 -> 签发 JWT -> 进入后台
```

---

## 六、安全风险分析

### 6.1 风险矩阵

| 风险 | 方案A（自主注册） | 方案C（混合模式） | 缓解措施 |
|------|:--:|:--:|------|
| 冒充教师 | 高 | 低 | 教师必须管理员创建 |
| 恶意注册 | 高 | 低 | 绑定已有手机号，无匹配则拒绝 |
| 数据泄露 | 中 | 低 | 租户隔离 + JWT 校验 |
| 管理成本 | 低 | 中 | 批量导入 + 二维码自助绑定 |
| 用户增长 | 快 | 中 | 报名即创建，无缝衔接 |

### 6.2 关键安全措施

```
1. 微信绑定的安全链路
   ┌─────────────────────────────────────────────┐
   │ wx.login() -> code（5分钟有效，一次性）        │
   │ 后端 code -> openid（服务端请求，不经过前端）   │
   │ openid -> 查询绑定关系（服务端）                │
   │ 绑定 -> phone 必须匹配（不匹配则拒绝）          │
   │ 签发 JWT（含 openid，每次请求校验）            │
   └─────────────────────────────────────────────┘

2. JWT 设计
   payload: {
     user_id,          // 业务用户ID
     tenant_id,        // 所属机构
     openid,           // 微信标识（小程序端校验）
     user_type,        // STUDENT | TEACHER | ADMIN
     roles: [...],     // 角色列表
     iat,              // 签发时间
     exp               // 过期时间（2小时，refresh token 7天）
   }

3. 防刷机制
   - 同一 openid 每分钟最多 3 次登录请求
   - 同一 phone 每天最多 5 次绑定尝试
   - 管理员登录失败 5 次锁定 30 分钟
```

---

## 七、从 MVP 到商业化演进

### 阶段 1：小型舞蹈机构（1-3 个校区，MVP）

```
用户量：100-500 学员，5-20 教师
═══════════════════════════════════════════════

方案：管理员创建 + 微信绑定
  - 管理员手动创建学员/教师
  - 打印二维码，学员扫码绑定
  - 单租户，不区分校区

数据库：
  - 核心表：users, students, teachers, wechat_accounts
  - 不需要 tenant 表（单租户）
  - 不需要 role_permissions（角色固定）

权限：固定角色
  ADMIN / TEACHER / STUDENT，不开放自定义

目标：验证业务流程，快速上线
```

### 阶段 2：多校区 SaaS（3-20 个校区，商业化）

```
用户量：500-5000 学员，20-200 教师，多个机构
═══════════════════════════════════════════════

方案：租户隔离 + 混合模式
  - 引入 tenant 表，每个机构独立数据空间
  - 支持批量导入 Excel 创建学员
  - 开放注册申请通道（需管理员审核）
  - 支持校区概念（一个 tenant 多个 campus）

数据库新增：
  - tenants 表（机构信息、套餐、到期时间）
  - campuses 表（校区）
  - 完整 RBAC 权限体系

权限：可自定义角色
  租户管理员可以创建自定义角色、分配权限

新增功能：
  - 跨机构数据隔离（RLS 或 tenant_id 过滤）
  - 机构间教师共享（连锁机构场景）
  - 数据导出、报表
```

### 阶段 3：大型教育平台（20+ 校区，平台化）

```
用户量：5000+ 学员，200+ 教师，多品牌
═══════════════════════════════════════════════

方案：开放平台 + 微信生态
  - 多个小程序（每个品牌一个，共享 backend）
  - 开放加盟商自助注册
  - 对接企业微信（教师管理 + IM）
  - 对接微信支付（课程购买、会员卡）

数据库新增：
  - organizations 表（品牌/加盟体系）
  - subscriptions 表（套餐订阅）
  - audit_logs 表（操作审计）

权限：租户 + 组织层级
  SUPER_ADMIN -> ORG_ADMIN -> TENANT_ADMIN -> TEACHER -> STUDENT

新增功能：
  - SSO 单点登录（跨小程序）
  - 数据中台（跨机构大数据分析）
  - 开放 API（第三方系统对接）
```

---

## 八、最终输出

### 8.1 推荐方案

**方案 C（混合模式）** 是唯一正确的选择。

核心逻辑：
```
管理员创建业务身份 -> 用户微信登录 -> 绑定已有身份 -> 进入系统
```

这个方案的本质是：**机构是付费方，机构决定谁是谁**。

### 8.2 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     舞蹈机构 SaaS 用户体系                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ 学员端小程序   │  │ 教师端小程序   │  │ 管理后台 Web           │   │
│  │ AppId: A      │  │ AppId: B      │  │ Account + Password    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                 │                      │               │
│         │   wx.login()    │   wx.login()         │  POST /login  │
│         ▼                 ▼                      ▼               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Auth Service (认证层)                   │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │   │
│  │  │ WeChat Auth   │  │ JWT Issuer   │  │ Phone Verify  │   │   │
│  │  │ code->openid  │  │ sign/verify  │  │ bind/match    │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                    │
│                              ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Data Layer (数据层)                      │   │
│  │                                                             │   │
│  │  wechat_accounts --1:1-- users --1:1-- students/teachers   │   │
│  │       │                    │                                │   │
│  │       │              ┌─────┴─────┐                          │   │
│  │       │           user_roles  roles -- role_permissions     │   │
│  │       │                         └───── permissions          │   │
│  │       │                                                     │   │
│  │       └── tenant_id ----→ 全局数据隔离                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 8.3 用户注册登录流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户注册 & 登录全流程                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐                                                 │
│  │ 管理员创建用户 │                                                │
│  │  (后台录入)   │                                                │
│  └──────┬──────┘                                                 │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────────┐                │
│  │            users 表写入                       │                │
│  │  user_type: STUDENT | TEACHER | ADMIN        │                │
│  │  status: ACTIVE                               │                │
│  │  phone: 138xxxx                               │                │
│  └──────────────────────┬──────────────────────┘                │
│                         │                                         │
│         ┌───────────────┼───────────────┐                        │
│         ▼               ▼               ▼                        │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐                 │
│  │ 学员端    │   │ 教师端    │   │ 管理后台      │                 │
│  │ 小程序    │   │ 小程序    │   │ Web          │                 │
│  └────┬─────┘   └────┬─────┘   └──────┬───────┘                 │
│       │              │                │                           │
│       ▼              ▼                ▼                           │
│  wx.login()     wx.login()     账号密码登录                        │
│       │              │                │                           │
│       ▼              ▼                ▼                           │
│  获取 openid    获取 openid    验证 password_hash                  │
│       │              │                │                           │
│       ▼              ▼                ▼                           │
│  ┌───────────────────────────────────────────┐                   │
│  │  查询绑定关系                                │                   │
│  │  wechat_accounts.openid -> user_id          │                   │
│  └──────────────────┬────────────────────────┘                   │
│                     │                                             │
│          ┌──────────┼──────────┐                                 │
│          ▼          ▼          ▼                                 │
│     已绑定      未绑定      管理员登录                              │
│          │          │          │                                  │
│          ▼          ▼          ▼                                  │
│   检查 status  输入手机号   直接查询 users                           │
│          │          │          │                                  │
│          ▼          ▼          ▼                                  │
│   签发 JWT    匹配 phone   签发 JWT                               │
│          │          │          │                                  │
│          └──────────┴──────────┘                                  │
│                     │                                             │
│                     ▼                                             │
│              ┌──────────────┐                                    │
│              │ 进入对应端    │                                     │
│              │ 根据 role     │                                    │
│              │ 渲染界面      │                                    │
│              └──────────────┘                                    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 8.4 前后端接口设计

```typescript
// ============================================================
// 认证相关接口
// ============================================================

// 微信小程序登录
POST /api/v1/auth/wechat/login
Body: {
  code: string,          // wx.login() 返回的 code
  appid: string,         // 小程序 AppId
}
Response: {
  token: string,         // JWT（已绑定用户时返回）
  bind_token?: string,   // 临时绑定凭证（未绑定用户时返回）
  need_bind: boolean,    // 是否需要绑定
}

// 微信绑定已有账号
POST /api/v1/auth/wechat/bind
Body: {
  bind_token: string,    // 上一步返回的临时凭证
  phone: string,         // 手机号
}
Response: {
  token: string,         // JWT
  user: { id, name, user_type, roles }
}

// 管理后台登录
POST /api/v1/auth/admin/login
Body: {
  phone: string,
  password: string,
}
Response: {
  token: string,
  user: { id, name, tenant_id, roles }
}

// 刷新 Token
POST /api/v1/auth/refresh
Body: { refresh_token: string }
Response: { token: string, refresh_token: string }

// ============================================================
// 用户管理接口（管理后台）
// ============================================================

// 创建学员
POST /api/v1/admin/students
Body: {
  name: string,
  phone: string,
  student_no?: string,
  course_ids?: number[],
  remaining_hours?: number,
}

// 批量导入学员
POST /api/v1/admin/students/batch
Body: FormData { file: Excel }

// 生成学员绑定二维码
GET /api/v1/admin/students/:id/bind-qrcode
Response: { qrcode_url: string }  // 有效期 7 天

// 创建教师
POST /api/v1/admin/teachers
Body: {
  name: string,
  phone: string,
  teacher_no?: string,
  specialties?: string[],
}

// 获取当前用户信息
GET /api/v1/auth/me
Response: {
  id, name, phone, user_type, roles,
  student?: { student_no, remaining_hours, ... },
  teacher?: { teacher_no, specialties, ... },
}
```

### 8.5 权限模型总结

```
权限判断流程（每次 API 请求）：
┌─────────────────────────────────────────────────────┐
│ 1. JWT 中间件解析 token -> user_id, tenant_id, roles │
│ 2. 租户上下文注入 tenant_id                            │
│ 3. 权限装饰器检查：@require_permission("student:read") │
│    -> 查询 user_roles -> roles -> role_permissions      │
│    -> 匹配 resource + action                          │
│    -> 通过 -> 执行业务逻辑                              │
│    -> 拒绝 -> 403 Forbidden                            │
└─────────────────────────────────────────────────────┘

预置权限（permissions 表初始数据）：

TEACHER 角色权限：
  schedule:read      - 查看排课
  booking:read       - 查看预约
  booking:checkin    - 签到
  student:read       - 查看学员信息

STUDENT 角色权限：
  course:read        - 查看课程
  schedule:read      - 查看排课
  booking:create     - 预约课程
  booking:cancel     - 取消预约
  booking:read       - 查看我的预约

TENANT_ADMIN 角色权限：
  *:*                - 全部权限（本租户内）
```

### 8.6 为什么选择该方案？

```
1. 商业合理性
   -> 舞蹈机构是 B2B2C 模式，机构付费，学员使用
   -> 学员身份必须由机构确认（报名=创建）或管理员创建
   -> 不能让用户自己选"我是学员"，这是业务逻辑不是技术问题

2. 安全性
   -> 教师不能自主注册，防止冒充
   -> 微信绑定需要手机号匹配，双重验证
   -> 租户隔离，数据不会跨机构泄露

3. 扩展性
   -> wechat_accounts 与 users 分离，支持多种登录方式
   -> users 与 students/teachers 分离，支持新增角色
   -> RBAC 可自定义，支持不同机构的差异化需求

4. 用户体验
   -> 老学员只需扫码绑定，不重复填信息
   -> 新学员报名后自动创建，管理员零额外操作
   -> 管理员批量导入，降低迁移成本
```

### 8.7 后续扩展能力

```
1. 会员体系
   在 users 基础上扩展 memberships 表：
   -> 会员等级（普通/银卡/金卡/钻石）
   -> 积分体系
   -> 优惠券

2. 多端统一
   unionid 打通：
   -> 学员小程序 + 公众号 + H5 商城
   -> 同一微信用户在不同端的身份统一

3. 企业微信集成
   -> 教师通过企业微信登录管理后台
   -> 排课提醒通过企业微信推送
   -> 家校沟通（学员家长通过微信服务号接收通知）

4. 开放平台
   -> 第三方系统通过 OAuth2.0 接入
   -> 例如：对接美团/大众点评的团购核销
   -> 例如：对接智能门禁系统（签到自动开门）

5. 数据合规
   -> 用户数据导出（GDPR/个保法）
   -> 数据脱敏（手机号中间4位隐藏）
   -> 操作审计日志（谁在什么时间做了什么）
```

---

**总结：方案 C 是唯一正确解。** 它把"微信登录"当成一个认证手段，而不是业务逻辑的一部分。学员是谁、教师是谁，由机构在后台决定，微信只负责证明"你是你"。这个设计从 MVP 到平台化都能平滑演进，是真正可商业化运营的 SaaS 用户体系。