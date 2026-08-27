# Dance SaaS - 舞蹈机构约课 SaaS 系统

一套面向舞蹈机构的多租户 SaaS 约课系统，支持学员端、教师端与管理后台。

## 技术栈

- **后端**: Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL 15 + Redis 7
- **前端**: Vue 3 + Vite + TypeScript + Element Plus + Pinia
- **构建**: Monorepo (pnpm + Turborepo)
- **部署**: Docker Compose + Nginx
- **CI/CD**: GitHub Actions (自动构建、测试、部署)

> 最后更新：2026-08-27

## 快速开始

### 前置依赖

| 工具 | 版本 |
|---|---|
| Node | ≥ 20 |
| pnpm | ≥ 8 |
| Python | ≥ 3.12 |
| uv | latest |
| Docker | latest |

### 启动开发环境

```bash
# 1. 复制环境变量
cp .env.example .env

# 2. 启动 PostgreSQL + Redis
pnpm db:up

# 3. 安装依赖
pnpm install
cd apps/api && uv sync && cd ../..

# 4. 启动后端
pnpm dev:api

# 5. 验收：健康检查
curl http://localhost:8000/api/v1/common/health
```

## 项目结构

```
class_booking_system/
├── apps/
│   ├── api/              # FastAPI 后端
│   ├── admin-web/        # 管理后台 (Vue 3 + Element Plus)
│   ├── student-web/      # 学员端 (Vue 3 + Element Plus)
│   ├── teacher-web/      # 教师端 (Vue 3 + Element Plus)
│   └── miniapp/          # 微信小程序端 (uni-app + Vue 3 + TypeScript)
├── packages/
│   ├── api-types/        # OpenAPI 生成的 TS 类型
│   ├── api-client/       # axios 封装
│   ├── shared-ui/        # 跨端 Vue 组件
│   ├── utils/            # 共享工具
│   └── config/           # 共享配置
├── infra/
│   └── docker/           # Docker Compose
└── class_booking_system_plan.md  # 完整开发计划
```

## 开发计划

完整 7 步计划（技术选型 → 架构 → 目录 → 数据库 → API → 路线图 → 20 个 Task）见 [class_booking_system_plan.md](./class_booking_system_plan.md)。

### 当前进度

| Task | 状态 | 完成日期 | 说明 |
|------|------|----------|------|
| **T01** | ✅ 完成 | 2026-06-13 | Monorepo + Docker 基础设施 |
| **T02** | ✅ 完成 | 2026-06-25 | 数据库迁移 + ORM 模型 + 种子数据 + 单元测试 |
| **T03** | ✅ 完成 | 2026-06-29 | **Auth 模块集成测试 (19/19 通过)** |
| **T04** | ✅ 完成 | 2026-07-06 | **User 模块完整实现 (API 测试通过)** |
| **T05** | ✅ 完成 | 2026-07-06 | **学员端骨架 + 端到端贯通 (注册→登录→课程列表)** |
| **T06** | ✅ 完成 | 2026-07-09 | **管理后台全部页面 + 后端业务模块完善** |
| **T07-T12** | ✅ 完成 | 2026-07-21 | **业务功能开发完成** |
| **T13** | ✅ 完成 | 2026-08-05 | **微信小程序端 (miniapp) 完整开发** — 22 个页面、12 个组件、8 个 API 模块、双角色入口 |
| **T14** | ✅ 完成 | 2026-08-05 | **近期修复 + 文档完善** — 小程序 API 路径修复、预约列表关联查询、auth router 冗余清理、note.md 面试/任务标签体系 |
| **T15** | ✅ 完成 | 2026-08-17 | **AI Agent 智能助手** — MCP Server + AgentRuntime + 多轮对话 + 小程序 AI 组件 |
| **T16** | ✅ 完成 | 2026-08-18 | **小程序 UI 统一优化** — 视觉一致性、CSS 性能、间距标准化 |

---

## 已实现功能

### 学员端功能
| 功能 | 说明 |
|------|------|
| 用户注册/登录 | 手机号注册、密码登录 |
| 课程浏览 | 课程列表、课程详情 |
| 预约管理 | 查看排期、预约课程、取消预约 |
| 我的预约 | 查看预约记录、取消预约 |
| 个人中心 | 查看/编辑个人信息、退出登录 |

### 教师端功能
| 功能 | 说明 |
|------|------|
| 课表查看 | 按日期查看自己的排期课表 |
| 学员列表 | 查看预约学员、签到管理 |
| 个人中心 | 查看/编辑教师档案、退出登录 |

### 管理后台功能
| 功能 | 说明 |
|------|------|
| 课程管理 | 课程CRUD、分类/难度设置 |
| 教师管理 | 教师CRUD、启用/禁用 |
| 教室管理 | 教室CRUD |
| 学员管理 | 学员列表、启用/禁用、删除 |
| 排期管理 | 单条排期、批量排期、启用/禁用、删除 |
| 预约管理 | 预约列表、取消预约 |

### 核心业务特性
| 特性 | 说明 |
|------|------|
| 预约容量限制 | 排期容量管理、满员检测 |
| 时间冲突检测 | 教室/教师时间冲突检测 |
| 取消时间限制 | 开课前90分钟不可取消 |
| 多租户支持 | 支持多机构部署 |
| RBAC权限 | 角色权限控制 |
| AI 智能助手 | 自然语言对话预约/查询/取消课程 |

---

## 小程序端 (miniapp) ✨

基于 **uni-app + Vue 3 + TypeScript** 构建的微信小程序，支持学员端和教师端双角色。

### 技术栈

| 技术 | 用途 |
|------|------|
| uni-app (Vue 3) | 跨端框架，编译为微信小程序 |
| TypeScript | 类型安全 |
| SCSS | 样式预处理（自定义主题变量体系） |
| uni.request | 网络请求封装（含 Token 自动刷新） |

### 目录结构

```
apps/miniapp/src/
├── api/
│   └── index.ts                  # 统一 API 层（8 个模块，含 Token 自动刷新）
├── components/
│   ├── AppAvatar.vue             # 头像组件
│   ├── AppBadge.vue              # 状态徽标
│   ├── AppButton.vue             # 按钮组件
│   ├── AppCard.vue               # 卡片组件
│   ├── AppEmpty.vue              # 空状态组件
│   ├── AppFilterTabs.vue         # 筛选标签
│   ├── AppInput.vue              # 输入框组件
│   ├── AppLoading.vue            # 加载组件
│   ├── AppNavbar.vue             # 自定义导航栏
│   ├── AppSegmentedControl.vue   # 分段控制器
│   ├── StudentTabBar.vue         # 学员底部导航栏
│   └── TeacherTabBar.vue         # 教师底部导航栏
├── pages/
│   ├── index/                    # 首页（登录/注册/角色选择）
│   ├── bind/                     # 手机号绑定
│   ├── student/                  # 学员端页面
│   │   ├── courses/              # 课程列表 + 课程详情
│   │   ├── schedule/             # 排期查看 + 预约
│   │   ├── bookings/             # 我的预约记录
│   │   └── profile/              # 个人中心 + 编辑 + 设置 + 历史
│   ├── teacher/                  # 教师端页面
│   │   ├── courses/              # 课程列表 + 创建/编辑
│   │   ├── schedule/             # 排期列表 + 创建/编辑
│   │   ├── students/             # 学员管理 + 签到
│   │   └── profile/              # 个人中心 + 编辑 + 设置
│   └── notification/             # 消息通知
├── styles/
│   ├── base/                     # 重置 + 排版基础样式
│   ├── theme/                    # 主题变量 + 混入 + 动画
│   └── index.scss                # 全局样式入口
├── utils/
│   ├── auth.ts                   # 认证工具（Token 管理）
│   ├── date.ts                   # 日期格式化
│   ├── errorHandler.ts           # 全局错误处理
│   ├── helpers.ts                # 通用工具函数
│   ├── notification.ts           # 消息通知工具
│   └── wechat.ts                 # 微信 API 封装
├── static/tabs/                  # 底部导航栏图标 (10 张)
└── App.vue / main.ts             # 入口文件
```

### 页面路由（22 个页面）

#### 学员端

| 路由 | 页面 | 功能 |
|------|------|------|
| `pages/student/courses/index` | 课程列表 | 搜索课程、分类筛选、查看详情 |
| `pages/student/courses/detail` | 课程详情 | 课程信息 + 排期列表 + 预约入口 |
| `pages/student/schedule/index` | 排期查看 | 按日期查看排期、预约/取消 |
| `pages/student/bookings/index` | 我的预约 | 预约记录列表、取消预约 |
| `pages/student/profile/index` | 个人中心 | 个人信息概览 |
| `pages/student/profile/edit` | 编辑资料 | 修改昵称、头像等 |
| `pages/student/profile/settings` | 设置 | 退出登录 |
| `pages/student/profile/history` | 历史记录 | 已完成/已取消的预约 |

#### 教师端

| 路由 | 页面 | 功能 |
|------|------|------|
| `pages/teacher/courses/index` | 课程列表 | 查看自己教授的课程 |
| `pages/teacher/courses/form` | 课程编辑 | 创建/编辑课程信息 |
| `pages/teacher/schedule/index` | 排期列表 | 查看自己的排期课表 |
| `pages/teacher/schedule/form` | 排期编辑 | 创建/编辑排期 |
| `pages/teacher/students/index` | 学员管理 | 查看预约学员 + 签到操作 |
| `pages/teacher/profile/index` | 个人中心 | 教师档案概览 |
| `pages/teacher/profile/edit` | 编辑资料 | 修改教师档案 |
| `pages/teacher/profile/settings` | 设置 | 退出登录 |

#### 通用

| 路由 | 页面 | 功能 |
|------|------|------|
| `pages/index/index` | 首页 | 登录/注册/角色选择 |
| `pages/bind/manual` | 手机号绑定 | 微信登录后绑定手机号 |
| `pages/notification/index` | 消息通知 | 系统通知列表 |

### API 层（8 个模块）

| 模块 | 方法 | 说明 |
|------|------|------|
| `authApi` | login / register / wechatAutoLogin / wechatLogin / bindPhone / refreshToken / logout / getMe / updateMe / changePassword | 认证 |
| `userApi` | getUserList / getUser / createUser / updateUser / deleteUser / updateStatus | 用户管理 |
| `courseApi` | list / create / get / update / delete / batchDelete | 课程管理 |
| `scheduleApi` | list / create / get / update / delete / batchCreate | 排期管理 |
| `bookingApi` | list / create / cancel / get | 预约管理 |
| `teacherApi` | list / getCourses / getSchedules / getStudents / checkIn / updateProfile | 教师端 |
| `studentApi` | getCourses / getSchedules / getBookings / updateProfile | 学员端 |
| `classroomApi` | list / create / update / delete | 教室管理 |

### 核心特性

| 特性 | 说明 |
|------|------|
| 双角色入口 | 首页根据用户角色自动路由到学员端/教师端 |
| Token 自动刷新 | 401 自动静默刷新，失败后跳转登录页 |
| 租户识别 | 通过 `x-tenant-slug` 请求头传递租户信息 |
| 自定义导航栏 | 沉浸式导航栏，适配微信小程序自定义导航 |
| 主题变量体系 | 完整的 SCSS 变量/混入/动画主题系统 |
| 组件化 | 12 个封装组件（导航栏、卡片、按钮、分段控制器等） |
| 全局错误处理 | 统一错误拦截 + Toast 提示 |
| 超时控制 | 登录 10s 超时 / 普通请求 30s 超时 + Promise 总超时 |

---

## T06 详细内容（2026-07-09）✨ 新增

### 🎯 任务概述

完成 **管理后台全部页面** + **后端业务模块完善**，实现课程、排期、教室、学员、教师、角色等核心业务功能。

---

### 📊 管理后台页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 仪表盘 | `/dashboard` | 统计卡片 + 近期排期 + 禁用教师/学员列表 |
| 用户管理 | `/users` | 用户 CRUD + 角色分配 + 状态管理 |
| 角色管理 | `/roles` | 角色 CRUD + 权限分配 |
| 教师管理 | `/teachers` | 教师列表 + 启用/禁用 + 删除（含排课校验） |
| 学员管理 | `/students` | 学员列表 + 搜索/筛选 + 状态管理 |
| 课程管理 | `/courses` | 课程 CRUD + 分类/难度筛选（支持自定义输入） |
| 排期管理 | `/schedules` | 排期 CRUD + 学员查看 + 时间冲突检测 |
| 教室管理 | `/classrooms` | 教室卡片展示 + 设备管理（支持自定义输入） + 维护/启用 |
| 租户管理 | `/tenant` | 租户配置 |

---

### 🔧 后端新增/完善模块

#### Booking 模块（预约）
| 接口 | 功能 |
|------|------|
| POST `/bookings` | 创建预约 |
| GET `/bookings` | 预约列表（按排期/学员筛选） |
| PATCH `/bookings/{id}` | 更新预约状态 |
| DELETE `/bookings/{id}` | 取消预约 |

#### Schedule 模块（排期）
| 接口 | 功能 |
|------|------|
| POST `/schedules` | 创建排期（含教室维护状态校验） |
| GET `/schedules` | 排期列表（按课程/教师/教室筛选） |
| PATCH `/schedules/{id}` | 更新排期（含冲突检测） |
| DELETE `/schedules/{id}` | 删除排期 |

#### Classroom 模块（教室）
| 接口 | 功能 |
|------|------|
| POST `/classrooms` | 创建教室 |
| GET `/classrooms` | 教室列表（卡片展示） |
| PATCH `/classrooms/{id}` | 更新教室（维护/启用） |
| DELETE `/classrooms/{id}` | 删除教室（含排课校验） |

#### Course 模块（课程）
| 接口 | 功能 |
|------|------|
| POST `/courses` | 创建课程 |
| GET `/courses` | 课程列表（分类/难度筛选） |
| PATCH `/courses/{id}` | 更新课程 |
| DELETE `/courses/{id}` | 删除课程 |

---

### ✨ 关键业务规则

#### 删除保护
| 模块 | 删除条件 |
|------|---------|
| 教师 | 无未来排课才能删除 |
| 教室 | 无未来排课才能删除 |
| 排期 | 无预约记录才能删除 |

#### 教室维护
- 维护中的教室 **拒绝创建新排期**
- 已有排期不受影响
- 编辑排期更换教室时校验新教室状态

#### 搜索筛选
- 所有列表页统一 `@keyup.enter` + `@clear` + `@change` 触发搜索
- 搜索/筛选参数传递到后端，分页与筛选同时生效
- 分页统一显示 `共 X 条`

#### 自定义选项
- 教室设备、课程分类、课程难度均支持 `allow-create` 自由输入
- 无需修改代码即可添加新选项

---

### 📁 核心文件清单

```
apps/admin-web/                    # 管理后台（全新创建）
├── src/
│   ├── layout/AdminLayout.vue     # 管理后台布局（侧边栏+顶栏+内容区）
│   ├── router/index.ts            # 路由配置（11个页面）
│   ├── stores/auth.ts             # 认证状态管理
│   ├── mock/index.ts              # Mock 数据
│   └── views/
│       ├── dashboard/index.vue    # 仪表盘
│       ├── users/index.vue        # 用户管理
│       ├── roles/index.vue        # 角色管理
│       ├── teachers/index.vue     # 教师管理
│       ├── students/index.vue     # 学员管理
│       ├── courses/index.vue      # 课程管理
│       ├── schedules/index.vue    # 排期管理
│       ├── classrooms/index.vue   # 教室管理（卡片布局）
│       ├── login/index.vue        # 登录页
│       ├── register/index.vue     # 注册页
│       └── tenant/index.vue       # 租户管理

apps/teacher-web/                  # 教师端（全新创建）
├── src/
│   ├── views/                     # 教师端页面
│   └── ...

apps/api/src/app/modules/          # 后端模块
├── booking/                       # 预约模块（新增）
│   ├── router.py
│   ├── service.py
│   ├── repository.py
│   └── schemas.py
├── schedule/                      # 排期模块（完善）
│   ├── router.py
│   ├── service.py
│   ├── repository.py
│   └── schemas.py
├── classroom/                     # 教室模块（完善）
│   ├── router.py
│   ├── service.py
│   ├── repository.py
│   └── schemas.py
├── course/                        # 课程模块（完善）
│   ├── router.py
│   ├── service.py
│   ├── repository.py
│   └── schemas.py
└── user/                          # 用户模块（完善）
    ├── router.py
    ├── service.py
    └── schemas.py

packages/api-client/src/           # API 客户端（扩展）
├── bookings.ts
├── classrooms.ts
├── courses.ts
├── roles.ts
├── schedules.ts
└── users.ts
```

---

## T02 详细内容（2026-06-25）

### 核心交付物

#### 1. 数据库架构（17 张表）

```
核心表:
├── tenants              # 租户机构
├── users                # 用户账号
├── roles                # 系统角色
├── permissions          # 权限项
├── user_roles           # 用户角色关联
└── role_permissions     # 角色权限关联

业务表:
├── courses              # 课程
├── course_schedules     # 排课
├── bookings             # 预约
├── classrooms           # 教室
├── teacher_profiles     # 老师档案
├── student_profiles     # 学员档案
├── membership_cards     # 会员卡
├── orders               # 订单
├── payments             # 支付
└── audit_logs           # 审计日志
```

#### 2. ORM 模型设计（13 个模块）

- **基础类**: `Base`, `TenantMixin`, `TimestampMixin`
- **核心模块**: tenant, user, auth (roles, permissions)
- **业务模块**: course, schedule, booking, classroom, teacher, student, membership, order, payment, audit_log

#### 3. 种子数据系统

```sql
-- 租户: 奕欣舞蹈 (dance-school) [ID=2]
-- 角色: super_admin, admin, teacher, student (4个)
-- 权限: course(3) + schedule(2) + booking(2) + user(1) + stats(1) = 9个
-- 管理员: 12345678901 / super_admin [ID=1]
```

#### 4. 单元测试

```
✅ 9 个测试全部通过 (0.01s)
   ├── TestTenantModel (3 tests)
   ├── TestUserModel (2 tests)
   ├── TestRoleModel (2 tests)
   └── TestPermissionModel (2 tests)
```

#### 5. 基础设施组件

- **全局异常处理**: 自定义异常体系 + 统一错误响应
- **安全工具**: bcrypt 密码哈希 + JWT Token 编解码
- **多租户架构**: ContextVar 上下文管理 + 中间件
- **认证系统**: FastAPI Depends 依赖注入
- **数据库迁移**: Alembic 版本管理

### 技术亮点

- ✅ 多租户数据隔离设计
- ✅ 异步 SQLAlchemy 2.0 ORM
- ✅ 自动时间戳管理
- ✅ 软删除支持
- ✅ 审计日志追踪

---

## 近期修复（2026-08）

| 问题 | 描述 | 修复位置 |
|------|------|----------|
| 小程序课程列表无参报错 | `buildQuery({})` 导致 URL 末尾带 `/`，与后端路由不匹配 404 | `miniapp/src/api/index.ts`（7 处） |
| 预约列表无课程名称 | `BookingResponse` 缺少 schedule/course/classroom/teacher 关联字段 | `booking/schemas.py`、`booking/service.py` |
| auth router 冗余 responses | 删除 4 个 `422`（FastAPI 自动生成）和 3 个通用 `401`（依赖注入已处理） | `auth/router.py` |
| 项目文档完善 | 新增业务错误码体系计划、CI/CD 接入计划、面试问答（🎤/📋/🔧 标签体系） | `note.md` |
| AI Agent 智能助手 | MCP Server + AgentRuntime + 意图识别 + 多轮对话 + 小程序 AI 组件 | `app/ai/`、`modules/ai/router.py`、`miniapp/src/components/AiAssistant.vue` |
| 预约状态筛选 | `status` 参数支持逗号分隔多状态（数字/英文/中文） | `booking/router.py`、`booking/service.py`、`booking/repository.py` |
| 预约时间校验 | 过期排期禁止预约 + 最多约未来两周 | `booking/service.py` |
| AI 路由 Bug 修复 | `get_messages`→`get_history`、`clear_session`→`clear`、`current_user.id`→`current_user.get("user_id")` | `modules/ai/router.py` |

## 近期修复（2026-07）

| 问题 | 描述 | 修复位置 |
|------|------|----------|
| 签到状态复原 | 教师签到后刷新页面状态复原 | `teacher-web/src/views/students/index.vue` |
| 已取消学员展示 | 已取消的学员仍显示在列表中 | `teacher-web/src/views/students/index.vue` |
| 时间格式化 | 时间显示格式优化为年月日时分 | `teacher-web/src/views/students/index.vue` |
| 教师档案编辑 | 修改后刷新页面复原 | `teacher-web/src/views/profile/index.vue` |
| 学员数统计 | 未获取到数据，已隐藏 | `teacher-web/src/views/profile/index.vue` |
| API 500错误 | page_size参数验证失败 | `course/schemas.py`, `course/router.py` |
| tenant_id空值 | 创建教师档案时违反非空约束 | `teacher/service.py` |
| 导入路径错误 | api-client导入路径错误 | `packages/api-client/src/teachers.ts` |
| avatar字段错误 | User模型字段名错误 | `teacher/service.py` |

---

## License

MIT License

## T03 详细内容（2026-06-29）✨ 新增

### 🎯 任务概述

完成 **Auth（认证）模块的完整集成测试**，覆盖用户注册、登录、Token 管理、登出等核心功能。

**测试结果**: **19/19 全部通过** ✅ (执行时间 ~3s)

---

### 📊 测试覆盖详情

```
tests/integration/test_auth_api.py
├── TestRegister (4 tests)        ← 用户注册
│   ├── test_register_success           正常注册 (201 + 双 Token)
│   ├── test_register_duplicate_phone   重复手机号 (400)
│   ├── test_register_invalid_phone_format 无效格式 (422)
│   └── test_register_weak_password     弱密码 (422)
├── TestLogin (3 tests)           ← 用户登录
│   ├── test_login_success              正确凭据 (200)
│   ├── test_login_wrong_password       错误密码 (401)
│   └── test_login_nonexistent_user     不存在用户 (401)
├── TestGetMe (3 tests)           ← 获取用户信息
│   ├── test_get_me_with_token          有效 Token (200)
│   ├── test_get_me_without_token       无 Token (401)
│   └── test_get_me_invalid_token       无效 Token (401)
├── TestRefreshToken (3 tests)    ← 刷新令牌
│   ├── test_refresh_token_success      正常刷新 (新双 Token)
│   ├── test_refresh_token_already_used 重复使用 RT (401)
│   └── test_refresh_token_invalid      无效 RT (401)
├── TestLogout (2 tests)          ← 用户登出
│   ├── test_logout_success             带 RT 登出 (200)
│   └── test_logout_without_refresh_token 无 RT 登出 (200)
├── TestCompleteAuthFlow (1 test) ← 完整链路
│   └── test_complete_happy_path        register→login→me→refresh→logout
└── TestEdgeCases (3 tests)       ← 边界情况
    ├── test_missing_required_fields     缺少字段 (422)
    ├── test_extra_fields_ignored        额外字段 (201)
    └── test_sql_injection_protection    SQL 注入防护

Total: 19 tests ✅ 100% 通过
```

---

### 🔐 安全机制实现

#### 1️⃣ JWT 双 Token 设计

```json
{
  "access_token": {
    "user_id": 123,
    "tenant_id": 456,
    "iat": 1719648000.123456,  // 微秒精度
    "exp": 1719652400,          // 2小时后过期
    "type": "access",
    "jti": "uuid-xxxx"          // 全局唯一 ID
  },
  "refresh_token": {
    "user_id": 123,
    "iat": 1719648000.654321,
    "exp": 1720252800,          // 7天后过期
    "type": "refresh",
    "jti": "uuid-yyyy"
  }
}
```

**唯一性保证**: `iat` (微秒时间戳) + `jti` (UUID v4)

#### 2️⃣ Redis 黑名单机制

```
Key:   blacklist:{token_jti}
Value: {token_type, user_id, blacklisted_at}
TTL:   token_remaining_lifetime (自动过期)
```

**特性**:
- ✅ O(1) 时间复杂度查找
- ✅ TTL 自动过期机制
- ✅ 支持分布式部署
- ✅ 防止 Token 重放攻击

#### 3️⃣ Token 旋转策略

```
登录 → [RT_1] → 刷新 → [RT_2]
                  ↓
            RT_1 加入黑名单
                  ↓
         再次使用 RT_1 → ❌ 失败 (已在黑名单)
```

---

### 🏗️ 技术架构突破

#### ⭐ 核心问题：asyncpg 事件循环冲突

**症状**:
```
RuntimeError: Task got Future attached to a different loop
RuntimeError: Event loop is closed
```

**根因分析**:
1. ASGITransport 在当前进程运行 FastAPI
2. asyncpg 连接绑定到特定事件循环
3. Pytest fixture 创建/销毁导致循环切换
4. 连接池中的连接与新循环不兼容

**最终方案**: ✅ 使用真实 Uvicorn HTTP 服务器

```python
# conftest.py - Session 级别服务器
@pytest.fixture(scope="session")
def live_server(event_loop):
    port = 8765
    
    def run_server():
        config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port)
        server = uvicorn.Server(config)
        server.run()
    
    # 在独立线程中启动
    _server_thread = threading.Thread(target=run_server, daemon=True)
    _server_thread.start()
    
    yield f"http://127.0.0.1:{port}"
```

**优势**:
- ✅ 完全隔离的事件循环（无冲突）
- ✅ 接近生产环境的测试方式
- ✅ 100% 稳定性（19/19 通过）

---

### 📈 性能指标

| 指标 | 数值 |
|------|------|
| **总测试数量** | 19 个 |
| **通过率** | 100% |
| **执行时间** | ~3 秒 |
| **API 平均响应** | 20-50ms |

#### API 响应时间（本地测试）

| 接口 | 平均响应 | P99 |
|------|---------|-----|
| POST /register | ~50ms | ~80ms |
| POST /login | ~30ms | ~50ms |
| GET /me | ~20ms | ~30ms |
| POST /refresh-token | ~40ms | ~60ms |
| POST /logout | ~30ms | ~50ms |

---

### 📁 核心文件清单

```
apps/api/
├── src/app/modules/auth/
│   ├── router.py              # API 路由 (5个接口)
│   ├── service.py             # 业务逻辑 (已清理 TODO)
│   ├── schemas.py             # Pydantic 模型 (完整文档)
│   ├── repository.py          # 数据库操作
│   └── models.py              # ORM 模型
├── src/app/core/
│   ├── security.py            # JWT/密码工具
│   └── config.py              # 配置管理
├── src/app/deps/
│   └── auth.py                # 依赖注入
├── src/app/middleware/
│   └── tenant_middleware.py   # 纯ASGI中间件
└── tests/
    ├── conftest.py             # 全局 Fixtures
    └── integration/
        ├── test_auth_api.py   # 19个测试用例
        └── T03_AUTH_README.md  # 详细文档 (~800行)
```

---

### 🔧 解决的关键问题

| # | 问题 | 难度 | 解决方案 |
|---|------|------|----------|
| 1 | asyncpg 事件循环冲突 | ⭐⭐⭐⭐⭐ | Uvicorn 真实服务器 |
| 2 | JWT Token 唯一性 | ⭐⭐⭐ | iat + jti 字段 |
| 3 | BaseHTTPMiddleware 冲突 | ⭐⭐⭐⭐ | 纯 ASGI 中间件 |
| 4 | Redis 初始化错误 | ⭐⭐ | AsyncRedis.from_url() |
| 5 | Swagger 文档不完善 | ⭐⭐ | summary/description/responses |

---

### 📖 API 文档

启动后端服务后访问：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

**认证接口列表**:

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 | ❌ |
| POST | `/api/v1/auth/login` | 用户登录 | ❌ |
| POST | `/api/v1/auth/logout` | 用户登出 | ✅ Bearer Token |
| POST | `/api/v1/auth/refresh-token` | 刷新令牌 | ❌ |
| GET | `/api/v1/auth/me` | 获取当前用户 | ✅ Bearer Token |

---

### 🚀 快速验证命令

```bash
# 启动基础设施
cd infra/docker && docker-compose up -d postgres redis

# 运行 T03 测试套件
cd apps/api && uv run pytest tests/integration/test_auth_api.py -v

# 预期输出
# ========================= 19 passed in 2.98s ==========================
```

---

## T04 详细内容（2026-07-06）✨ 新增

### 🎯 任务概述

完成 **User（用户管理）模块** 的完整实现，包含用户 CRUD、密码管理、角色绑定等核心功能，遵循 DDD 架构模式。

**测试结果**: **API 端点测试全部通过** ✅

---

### 📊 模块架构

```
┌─────────────────────────────────────────────────────────────┐
│                      DDD 分层架构                           │
├─────────────────────────────────────────────────────────────┤
│  Router 层    →  HTTP 入口 / 参数校验 / 权限控制            │
│       ↓                                                     │
│  Service 层   →  业务逻辑 / 事务管理 / 业务规则             │
│       ↓                                                     │
│  Repository 层 →  数据访问 / 查询封装 / 多租户隔离          │
│       ↓                                                     │
│  Model 层     →  ORM 模型 / 数据库映射                     │
└─────────────────────────────────────────────────────────────┘
```

---

### 📁 核心文件清单

```
apps/api/src/app/modules/user/
├── router.py       # REST API 路由 (9个接口)
├── service.py      # 业务逻辑层 (10个方法)
├── repository.py   # 数据访问层 (继承 TenantAwareRepository)
├── schemas.py      # Pydantic 数据模型 (7个模型)
└── models.py       # ORM 模型 (User, UserStatus, GenderStatus)
```

---

### 🔌 API 接口列表

| 方法 | 路径 | 功能 | 权限要求 |
|------|------|------|----------|
| POST | `/api/v1/users` | 创建用户 | `user:create` |
| GET | `/api/v1/users` | 用户列表（分页/搜索） | `user:read` |
| GET | `/api/v1/users/{id}` | 用户详情 | `user:read` |
| PATCH | `/api/v1/users/{id}` | 更新用户 | `user:update` |
| DELETE | `/api/v1/users/{id}` | 删除用户（软删除） | `user:delete` |
| POST | `/api/v1/users/{id}/password/change` | 修改密码（本人） | 本人操作 |
| POST | `/api/v1/users/{id}/password/reset` | 重置密码（管理员） | `user:reset_password` |
| GET | `/api/v1/users/{id}/roles` | 获取角色列表 | `user:read` |
| PUT | `/api/v1/users/{id}/roles` | 分配角色 | `role:assign` |

---

### 🎯 Service 层方法

| 方法 | 功能 | 说明 |
|------|------|------|
| `create_user` | 创建用户 | 验证手机号/邮箱唯一性 |
| `update_user` | 更新用户信息 | 支持部分更新 |
| `delete_user` | 删除用户 | 软删除，禁止删除自己 |
| `get_user_by_id` | 获取用户详情 | 包含角色信息 |
| `list_users` | 分页列表 | 支持关键词搜索、状态筛选 |
| `change_password` | 修改密码 | 验证旧密码 |
| `reset_password` | 重置密码 | 管理员操作 |
| `assign_roles` | 分配角色 | 覆盖式绑定，清除权限缓存 |
| `get_user_roles` | 获取用户角色 | 返回角色列表 |

---

### ✨ 技术特性

#### 1️⃣ 多租户隔离

```python
# UserRepository 继承 TenantAwareRepository
class UserRepository(TenantAwareRepository[User]):
    model_class = User
    # 自动注入 tenant_id 过滤
```

- ✅ 自动处理多租户数据隔离
- ✅ 查询时自动添加 `tenant_id` 条件
- ✅ 继承通用 CRUD 方法

#### 2️⃣ RBAC 权限控制

```python
@router.post("/users", summary="创建用户")
@require_permissions("user:create")  # 权限装饰器
async def create_user(...):
    pass
```

- ✅ 基于 Redis 的权限缓存
- ✅ 支持角色继承权限
- ✅ 细粒度权限控制

#### 3️⃣ 密码安全

- ✅ 使用 bcrypt 加密（12轮）
- ✅ 密码强度验证
- ✅ 支持密码修改/重置

#### 4️⃣ 软删除机制

- ✅ 使用 `deleted_at` 字段标记删除
- ✅ 查询自动过滤已删除记录
- ✅ 支持恢复已删除用户

---

### 🧪 测试覆盖

```
tests/integration/test_user_api.py
├── TestUserCRUD (5 tests)          ← 用户 CRUD 测试
│   ├── test_create_user_success      创建用户
│   ├── test_list_users               用户列表
│   ├── test_get_user_detail          用户详情
│   ├── test_update_user              更新用户
│   └── test_change_password          修改密码
└── TestUserAPIAvailability (1 test)  ← API 可用性
    └── test_user_api_endpoints_exist 9个端点验证
```

**测试结果**: ✅ 全部通过

---

### 📈 性能指标

| 指标 | 数值 |
|------|------|
| **API 端点数量** | 9 个 |
| **Service 方法** | 10 个 |
| **测试覆盖率** | API 可用性 100% |
| **响应时间** | 20-80ms |

---

### 🔧 解决的关键问题

| # | 问题 | 解决方案 |
|---|------|----------|
| 1 | 路由前缀重复 | 统一使用 `/api/v1` 前缀 |
| 2 | 权限检查异常 | 使用 `@require_permissions` 装饰器 |
| 3 | 多租户数据隔离 | 继承 `TenantAwareRepository` |
| 4 | 密码安全 | bcrypt 加密 + 强度验证 |

---

### 🚀 快速验证命令

```bash
# 启动基础设施
cd infra/docker && docker-compose up -d postgres redis

# 运行 T04 测试套件
cd apps/api && uv run pytest tests/integration/test_user_api.py -v

# 启动后端服务查看 API 文档
cd apps/api && uv run uvicorn app.main:app --reload
open http://localhost:8000/docs  # Swagger UI
```

---

## T05 详细内容（2026-07-06）✨ 新增

### 🎯 任务概述

完成 **学员端骨架 + 端到端贯通**，在浏览器中走通 **注册 → 登录 → 课程列表** 的完整流程。

**交付结果**: **前端项目零编译错误 + 全部 API 联调通过** ✅

---

### 📊 端到端数据流

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Register │ →  │  Login   │ →  │  /me     │ →  │ Courses  │
│  注册页面  │    │  登录页面  │    │ 用户信息  │    │ 课程列表  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     ↓               ↓               ↓               ↓
 手机号+密码     JWT双Token    完整用户信息      空列表占位
 机构标识        localStorage   Pinia Store     (T06 完善)
```

---

### 📁 核心文件清单

```
apps/student-web/                  # 学员端前端项目（Vue3 + Vite + TS）
├── index.html
├── package.json
├── vite.config.ts                 # Vite 配置（API 代理到 8000）
├── tsconfig.json
├── src/
│   ├── main.ts                    # 入口（注册 Pinia/Router/ElementPlus）
│   ├── App.vue                    # 根组件
│   ├── router/
│   │   └── index.ts               # 路由配置 + 导航守卫
│   ├── stores/
│   │   └── user.ts                # 用户状态管理（Pinia）
│   ├── views/
│   │   ├── login/index.vue        # 登录页面
│   │   ├── register/index.vue     # 注册页面
│   │   └── courses/index.vue      # 课程列表页面
│   └── styles/
│       └── index.scss             # 全局样式

packages/api-client/               # API 客户端封装
├── package.json
└── src/
    └── index.ts                   # axios 封装（Token/租户/刷新）

packages/api-types/                # 自动生成的 TS 类型
├── openapi.json                   # OpenAPI Schema（26 个接口）
└── schema.d.ts                    # TypeScript 类型（2487 行）

apps/api/src/app/modules/course/   # 课程占位路由
└── router.py                      # GET /courses（返回空列表，T06 完善）
```

---

### 🔌 页面路由

| 路由 | 页面 | 认证要求 | 说明 |
|------|------|----------|------|
| `/login` | 登录页 | ❌ 公开 | 手机号+密码+机构标识 |
| `/register` | 注册页 | ❌ 公开 | 手机号+昵称+密码+验证码 |
| `/courses` | 课程列表 | ✅ 需登录 | 未登录自动跳转 `/login` |

---

### 🛠️ 技术实现

#### 1️⃣ API 客户端封装（api-client）

```typescript
// 请求拦截器：自动注入 Token + 租户 ID
this.instance.interceptors.request.use((config) => {
  config.headers.Authorization = `Bearer ${token}`
  config.headers['x-tenant-id'] = tenantId
  return config
})

// 响应拦截器：401 自动刷新 Token
this.instance.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      return await refreshTokenAndRetry(error.config)
    }
    return Promise.reject(error)
  }
)
```

| 特性 | 说明 |
|------|------|
| 🔑 Token 管理 | 自动注入 `Authorization: Bearer xxx` |
| 🔄 Token 刷新 | 401 时自动用 refresh_token 换新 token，无缝重试 |
| 🏢 租户隔离 | 自动注入 `x-tenant-id` header |
| ⏱️ 超时控制 | 15 秒超时 |
| 📤 自动登出 | 刷新失败时清除凭据并跳转登录页 |

#### 2️⃣ 用户状态管理（Pinia）

```typescript
// stores/user.ts
export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const tenantId = ref(localStorage.getItem('tenantId') || '')
  const userInfo = ref<UserInfo | null>(null)

  // 登录：调用 API → 存储 Token → 解码 tenant_id → 获取用户信息
  async function login(params) { ... }
  // 注册：调用 API → 存储 Token → 跳转登录页
  async function register(params) { ... }
  // 登出：清除 Token + 用户信息 + 租户信息
  function logout() { ... }
})
```

| 功能 | 说明 |
|------|------|
| `login()` | API 调用 → 存储双 Token → 解码 JWT 提取 tenant_id → 获取用户信息 |
| `register()` | API 调用 → 自动跳转登录页 |
| `logout()` | 清除全部凭据 → 跳转登录页（含确认弹窗） |
| `fetchUserInfo()` | 调用 `/auth/me` 获取完整用户信息 |

#### 3️⃣ 路由守卫

```typescript
router.beforeEach((to, from, next) => {
  if (to.meta.requiresAuth && !userStore.token) {
    next('/login')  // 未登录 → 跳转登录页
  } else {
    next()
  }
})
```

#### 4️⃣ API 类型自动生成

```bash
# 一键生成：FastAPI OpenAPI → TypeScript 类型
pnpm gen:types

# 数据流：
# FastAPI app.openapi()
#   → Python 脚本导出 → openapi.json
#     → openapi-typescript → schema.d.ts (2487 行)
```

---

### 🔧 解决的关键问题

| # | 问题 | 根因 | 解决方案 |
|---|------|------|----------|
| 1 | 登录失败 400 | 前端发 `form-urlencoded` + `username`，后端接受 JSON + `phone` | 改为 JSON 格式 + `phone` 字段 |
| 2 | 注册失败 422 | 缺少 `verify_code`（后端必填） | 表单增加验证码字段（开发环境固定值） |
| 3 | `/auth/me` 报 40001 | 租户中间件拦截，缺少 `x-tenant-id` | 加入跳过路径 + 前端存储 tenant_id |
| 4 | `/auth/me` 返回数据不完整 | 直接返回 JWT payload，非用户完整信息 | 新增 `get_current_user_profile` 从数据库查询 |
| 5 | `/courses` 报 404 | 课程 API 未实现 | 创建占位路由返回空列表 |
| 6 | Token 刷新失败 | URL 错误 `/auth/refresh` → 正确 `/auth/refresh-token` | 修正 URL |

---

### ✅ 验证结果

| 检查项 | 结果 |
|--------|------|
| TypeScript 编译 | ✅ 零错误 |
| 前端页面（login/register/courses） | ✅ 全部 200 |
| 注册 API | ✅ 返回 Token + 用户信息 |
| 登录 API | ✅ 返回 Token + 用户信息 |
| `/auth/me` 获取用户信息 | ✅ 返回完整用户信息 |
| `/courses` 课程列表 | ✅ 返回空列表（占位） |
| 路由守卫 | ✅ 未登录自动跳转 `/login` |
| 退出确认弹窗 | ✅ 点击退出弹窗确认 |

---

### 🚀 快速验证命令

```bash
# 启动后端
cd apps/api && PYTHONPATH=src uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端（新终端）
cd apps/student-web && pnpm dev

# 浏览器访问
open http://localhost:5173

# 生成 API 类型
cd /root && pnpm gen:types
```

---

## Phase 2 计划

> 📄 详细计划文档：[docs/phase2_frontend_first_plan.md](docs/phase2_frontend_first_plan.md)

**策略**：前端页面（Mock 数据）→ 后端接口实现 → 前后端联调

| Phase | 任务 | 工时 | 说明 |
|-------|------|------|------|
| **1. 前端页面** | T06 学员端业务页 | 8h | 课程详情/排期日历/预约/我的预约/个人中心 |
| | T07 教师端全套 | 8h | 登录/课程/排期/学员/档案 |
| | T08 管理后台全套 | 8h | 用户/角色/教师/学员/课程/排期/教室/机构 |
| **2. 后端接口** | T09 课程+教室 API | 8h | CRUD + 筛选分页 |
| | T10 排期+预约 API | 10h | 批量排期 + 并发预约 + 冲突检测 |
| | T11 教师档案 API | 6h | 教师档案 CRUD + 角色绑定 |
| | T12 角色权限+审计 | 6h | 权限树 + 审计日志 + 机构设置 |
| **3. 前后联调** | T13 学员端联调 | 6h | Mock → 真实 API |
| | T14 教师端联调 | 6h | Mock → 真实 API |
| | T15 管理后台联调 | 6h | Mock → 真实 API |
| **4. 测试部署** | T16-T20 | 36h | E2E/性能/部署/灰度/上线 |

---

## T16 小程序 UI 统一优化 (2026-08-18)

### 核心改动

#### 1. 视觉一致性
- 统一卡片背景为毛玻璃效果：`rgba(255,255,255,0.95)` + `backdrop-filter: blur(20rpx)`
- 覆盖范围：课程列表、课程详情、排期列表、预约列表、历史记录
- 修复课程详情页卡片阴影从 `$glass-shadow` 到 `$shadow-card` 与其他页面一致

#### 2. CSS 性能优化
- 全局清除 `transition: all`（19 个文件，39 处），替换为精确属性（transform/box-shadow/background 等）
- 消除布局抖动隐患，减少不必要的 repaint
- 影响范围：全局 mixins 3 处、共享组件 4 处、学生端 12 处、教师端 8 处、其他页面 9 处

#### 3. 入场动画标准化
- 统一卡片入场动画：`cardFadeIn`，0.35s，cubic-bezier(0.22, 0.61, 0.36, 1)，位移 8rpx
- 逐条延迟：`index * 0.04s`
- 统一卡片 active 交互效果：`translateY(-2rpx)` + 阴影加深

#### 4. 间距体系标准化
- 内容区水平 padding：统一 `$space-md` (32rpx)
- 卡片间距：统一 `$space-md` (32rpx)
- 卡片内部 padding：统一 `$space-md` (32rpx)
- 空状态 padding：统一 120rpx
- 筛选→内容过渡：统一 `$space-md` (32rpx)

---

## Git 提交记录

```bash
# T02 提交 (2026-06-25)
commit b3da12f
Author: lantercode
Date: 2026-06-25
Message: feat(api): 完成 T02 - 数据库迁移 + 种子数据 + 单元测试
Files changed: 61
Insertions: 56.82 KiB

# T03 提交 (2026-06-29)
commit xxxxxx
Author: lantercode
Date: 2026-06-29
Message: feat(api): 完成 T03 - Auth 模块集成测试
Files changed: 12
Insertions: 8.5 KiB

# T04 提交 (2026-07-06) ⬇️
# 包含:
#   - User 模块完整实现 (router/service/repository/schemas)
#   - 9 个 REST API 端点
#   - 多租户隔离支持
#   - RBAC 权限控制
#   - API 集成测试
#   - 文档更新

# T05 提交 (2026-07-06) ⬇️
# 包含:
#   - 学员端前端项目 (Vue3 + Vite + TypeScript + Element Plus)
#   - API 客户端封装 (axios + Token 刷新 + 租户 header)
#   - API 类型自动生成 (openapi-typescript)
#   - 三个页面 (登录/注册/课程列表)
#   - 用户状态管理 (Pinia + localStorage)
#   - 路由守卫 (未登录跳转)
#   - 退出确认弹窗
#   - 课程占位 API
#   - 端到端联调通过
```