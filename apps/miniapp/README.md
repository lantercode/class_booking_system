# 小程序（miniapp）

> 本文档由 README.md 迁移而来。技术栈：uni-app + Vue3 + TypeScript，学员/教师双角色。

## 小程序端 (miniapp) ✨

基于 **uni-app + Vue 3 + TypeScript** 构建的微信小程序，支持学员端和教师端双角色。

### 技术栈

| 技术            | 用途                              |
| --------------- | --------------------------------- |
| uni-app (Vue 3) | 跨端框架，编译为微信小程序        |
| TypeScript      | 类型安全                          |
| SCSS            | 样式预处理（自定义主题变量体系）  |
| uni.request     | 网络请求封装（含 Token 自动刷新） |

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
│   ├── HomeTabBar.vue         # 学员底部导航栏
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

| 路由                             | 页面     | 功能                           |
| -------------------------------- | -------- | ------------------------------ |
| `pages/student/courses/index`    | 课程列表 | 搜索课程、分类筛选、查看详情   |
| `pages/student/courses/detail`   | 课程详情 | 课程信息 + 排期列表 + 预约入口 |
| `pages/student/schedule/index`   | 排期查看 | 按日期查看排期、预约/取消      |
| `pages/student/bookings/index`   | 我的预约 | 预约记录列表、取消预约         |
| `pages/student/profile/index`    | 个人中心 | 个人信息概览                   |
| `pages/student/profile/edit`     | 编辑资料 | 修改昵称、头像等               |
| `pages/student/profile/settings` | 设置     | 退出登录                       |
| `pages/student/profile/history`  | 历史记录 | 已完成/已取消的预约            |

#### 教师端

| 路由                             | 页面     | 功能                    |
| -------------------------------- | -------- | ----------------------- |
| `pages/teacher/courses/index`    | 课程列表 | 查看自己教授的课程      |
| `pages/teacher/courses/form`     | 课程编辑 | 创建/编辑课程信息       |
| `pages/teacher/schedule/index`   | 排期列表 | 查看自己的排期课表      |
| `pages/teacher/schedule/form`    | 排期编辑 | 创建/编辑排期           |
| `pages/teacher/students/index`   | 学员管理 | 查看预约学员 + 签到操作 |
| `pages/teacher/profile/index`    | 个人中心 | 教师档案概览            |
| `pages/teacher/profile/edit`     | 编辑资料 | 修改教师档案            |
| `pages/teacher/profile/settings` | 设置     | 退出登录                |

#### 通用

| 路由                       | 页面       | 功能                 |
| -------------------------- | ---------- | -------------------- |
| `pages/index/index`        | 首页       | 登录/注册/角色选择   |
| `pages/bind/manual`        | 手机号绑定 | 微信登录后绑定手机号 |
| `pages/notification/index` | 消息通知   | 系统通知列表         |

### API 层（8 个模块）

| 模块           | 方法                                                                                                                     | 说明     |
| -------------- | ------------------------------------------------------------------------------------------------------------------------ | -------- |
| `authApi`      | login / register / wechatAutoLogin / wechatLogin / bindPhone / refreshToken / logout / getMe / updateMe / changePassword | 认证     |
| `userApi`      | getUserList / getUser / createUser / updateUser / deleteUser / updateStatus                                              | 用户管理 |
| `courseApi`    | list / create / get / update / delete / batchDelete                                                                      | 课程管理 |
| `scheduleApi`  | list / create / get / update / delete / batchCreate                                                                      | 排期管理 |
| `bookingApi`   | list / create / cancel / get                                                                                             | 预约管理 |
| `teacherApi`   | list / getCourses / getSchedules / getStudents / checkIn / updateProfile                                                 | 教师端   |
| `studentApi`   | getCourses / getSchedules / getBookings / updateProfile                                                                  | 学员端   |
| `classroomApi` | list / create / update / delete                                                                                          | 教室管理 |

### 核心特性

| 特性           | 说明                                               |
| -------------- | -------------------------------------------------- |
| 双角色入口     | 首页根据用户角色自动路由到学员端/教师端            |
| Token 自动刷新 | 401 自动静默刷新，失败后跳转登录页                 |
| 租户识别       | 通过 `x-tenant-slug` 请求头传递租户信息            |
| 自定义导航栏   | 沉浸式导航栏，适配微信小程序自定义导航             |
| 主题变量体系   | 完整的 SCSS 变量/混入/动画主题系统                 |
| 组件化         | 12 个封装组件（导航栏、卡片、按钮、分段控制器等）  |
| 全局错误处理   | 统一错误拦截 + Toast 提示                          |
| 超时控制       | 登录 10s 超时 / 普通请求 30s 超时 + Promise 总超时 |

---

