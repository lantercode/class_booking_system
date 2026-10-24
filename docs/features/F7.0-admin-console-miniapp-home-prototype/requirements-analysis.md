# F7.0 需求分析：后台管理端增强与小程序首页配置

> 日期：2026-10-19
> 阶段：**需求分析 / 技术方案评审 / 高保真可交互原型**（不实现正式业务代码）
> 性质：只读审计 + 原型交付。所有现状结论均带 `file:line` 证据，未确认项一律进 open-decisions.md。

---

## 一、阶段 1：项目与现有原型检查结果

### 1.1 Git 与工作区

| 检查项 | 结果 |
|--------|------|
| 当前分支 | `main`（`git rev-parse --abbrev-ref HEAD`） |
| 工作区状态 | **存在大量未提交修改**（`M`：admin-web 多个 views、apps/api 多个模块、`.env.example`；`D`：`ai/tools/*`、`ai/auth/*`、`MEMBERSHIP_CARD_FIXES_REPORT.md`） |
| 处置 | **本次未执行任何 Git 写操作**，未清理、未覆盖、未 stash 用户未提交修改；所有 F7.0 产物仅新增于新目录 |
| 最近提交 | `71da90f fixed：小程序打包问题修改` |

> ⚠️ 当前工作区包含用户未提交的在改代码（尤其 `apps/admin-web/src/views/users/index.vue`、`classrooms/index.vue` 处于 `M` 状态）。F7.0 原型**不得**以"修改这些文件"的方式交付，只做独立原型目录产物。

### 1.2 Monorepo 结构（已核实）

```
apps/api         FastAPI 后端（/api/v1）           apps/admin-web   管理端 Vue3+TS+Vite+Element Plus+Pinia
apps/student-web 学员 Web                          apps/teacher-web  教师 Web
apps/miniapp     uni-app 微信小程序（学员/教师双角色）
packages/api-client  Web 三端 HTTP 客户端          packages/api-types  OpenAPI 生成类型
```

后端业务模块目录（`apps/api/src/app/modules/`）：`admin / ai / auth / booking / classroom / course / membership / notification / order / payment / permission / role / schedule / student / teacher / tenant / upload / user`。

### 1.3 现有管理端（admin-web）

| 项 | 现状 | 证据 |
|----|------|------|
| 布局 | `el-container`：左侧 `el-aside`(220/64) + `el-header` + `el-main` + `el-footer` | `apps/admin-web/src/layout/AdminLayout.vue` |
| 主题 | 侧边栏深色 `#1a1a2e`，激活项渐变 `#667eea→#764ba2`，主区背景 `#f0f2f5`，Element Plus 主色 `#409eff`；**非**小程序香槟金 | AdminLayout.vue:184-292 |
| 一级导航（11 项） | 用户管理 / 角色权限 / 教师管理 / 学员管理 / 课程管理 / 教室管理 / 排期管理 / 卡产品管理 / 会员卡管理 / 机构设置（`/dashboard` 已在菜单注释掉） | AdminLayout.vue:145-157 |
| 右上角用户区 | `el-dropdown`：`el-avatar`(icon=UserFilled) + 昵称 + ArrowDown，下拉**仅「退出登录」** | AdminLayout.vue:58-74 |
| 面包屑 | 「首页 / 当前页标题」 | AdminLayout.vue:51-56 |
| 全局反馈 | 各页用 `ElMessage` / `ElMessageBox`；无统一全局弹窗组件 | users/index.vue 等 |
| 路由 | 静态路由表，含 `/dashboard,/users,/roles,/teachers,/students,/courses,/schedules,/classrooms,/tenant,/membership,/card-types` | `apps/admin-web/src/router/index.ts` |

**用户管理页现状**（`apps/admin-web/src/views/users/index.vue`）

- 工具栏：搜索（占位「搜索手机号/昵称」240px）+ 角色筛选 + 状态筛选 + 「新增」按钮。
- 表格列：序号 / 昵称 / 手机号 / 教师编号 / 学员编号 / 状态(tag) / 微信绑定(tag) / 注册时间 / 操作（编辑 / 重置密码 / 删除 / 解绑微信）。
- **无头像列**；**无「头像」编辑项**。
- 弹窗：新增（手机号/昵称/密码/角色）、编辑（手机号 disabled/昵称/状态/角色）、重置密码。
- 四态：`loading` / `empty-text="暂无数据"` / `loadError`→`el-result` 重试 / 成功。分页 `el-pagination`。
- 数据源：`userApi.list({page,page_size,keyword,role_code,status})` → `GET /users`。

**教室管理页现状**（`apps/admin-web/src/views/classrooms/index.vue`）

- **只有卡片网格视图**（`el-row` + `el-col :span="8"` + `el-card`），**无表格视图**。
- 卡片内容：教室名称 + 状态 tag（`正常/维护中`）+ 设备列表 + 操作（编辑 / 维护·启用 / 删除）。
- **无封面图 / 无编号 / 无位置 / 无容纳人数**。
- 弹窗：教室名称 + 设备（`el-select` 多选 allow-create，预设 镜子/把杆/音响/投影仪/瑜伽垫/灯光）。
- 数据源：`classroomApi.list({keyword,page_size})` → `GET /classrooms`。

### 1.4 现有小程序首页（miniapp）

| 项 | 现状 | 证据 |
|----|------|------|
| `pages/index/index.vue` | **实为授权/登录入口页**（品牌名「舞蹈约课」+ 微信一键登录），**不含**首页内容区块 | index.vue:12-99、250-312 |
| 真实内容首页 | `pages/student/courses/index.vue`（学员端首页/课程首页） | pages.json:79-84 |
| TabBar | `pages.json` **未配置 `tabBar`**；底部导航是组件 `HomeTabBar.vue`（当前仅渲染「首页」tab） | pages.json 全文；HomeTabBar.vue:1-16 |
| AI 助手 | `AiAssistant.vue` 悬浮入口（一级入口，非 Tab） | index.vue:204-205 |

**`pages/student/courses/index.vue` 渲染区块与数据来源**（关键）：

| 顺序 | 区块 | UI 标题文案 | 数据来源 | 类型 |
|------|------|-------------|----------|------|
| 1 | Banner 轮播 | `swiper`（页面顶部，占满头部） | `const banners = ref([...])` 硬编码 5 条 `{title,subtitle,imageUrl}` | **静态** |
| 2 | 师资团队 | 「师资团队」 | `teachers` ← `teacherApi.list()` → `GET /teachers` | **真实 API** |
| 3 | 推荐课程 | 「推荐课程」 | `courses` ← `studentApi.getCourses()` → `GET /courses` | **真实 API** |
| 4 | 舞蹈视频 | 「舞动 · 让生活更美好」 | `const videos = ref([...])` 硬编码 3 条 `{title,description,duration,coverUrl,videoUrl}` | **静态** |
| — | 公告/活动 | **不存在该区块** | — | **缺失** |
| 5 | 底部导航 | `HomeTabBar` | — | 组件 |
| 6 | AI 助手 | `AiAssistant` 悬浮 | — | 组件 |

### 1.5 后端现状（已核实）

| 项 | 现状 | 证据 |
|----|------|------|
| 用户模型 | **`users.avatar_url` 字段已存在**（`String(500)`） | `modules/user/models.py:39` |
| 用户 DTO | `UserResponse.avatar_url` 已有；`UserUpdate.avatar_url` 已有；`UserCreate` 继承 `UserBase.avatar_url` | `modules/user/schemas.py:19,41,59` |
| 用户 API | `POST/GET(列表)/GET(详情)/PATCH/DELETE /users`、`POST /users/{id}/password/reset`、`PUT /users/{id}/roles`、`POST /users/{id}/wechat/unbind`；均带 `@require_permissions` | `modules/user/router.py` |
| 当前用户 API | `GET /auth/me`、`PATCH /auth/me`（**仅允许 `nickname` 与 `avatar_url`**，其余字段被白名单过滤）、`POST /auth/logout` | `modules/auth/router.py:135-173`；`auth/service.py:37-67` |
| 前端 api-client | `User.avatar_url` 已有；`UserUpdateParams.avatar_url` 已有 | `packages/api-client/src/users.ts:7,46` |
| 管理端 store | `adminInfo {id,phone,nickname,avatar?,roles?}`；登录后 `fetchAdminInfo()` 调 `GET /auth/me` | `apps/admin-web/src/stores/auth.ts:6-12,73-92` |
| 教室模型 | `classrooms` 表**仅** `id / name / equipment(ARRAY) / status` | `modules/course/models.py:18-30`（Classroom 定义在 course 模块） |
| 教室 DTO | `ClassroomCreate/Update/Response` 仅 name/equipment/status | `modules/classroom/schemas.py` |
| 教室 API | `POST/GET/GET{id}/PATCH/DELETE /classrooms` | `modules/classroom/router.py` |
| **上传模块** | `modules/upload/models.py` **为空文件**；无 router/service → **不存在任何上传接口** | `modules/upload/` 目录仅空 `models.py` |
| 首页配置相关 | **不存在** banner / notice / home-config / video-config 任何后端路由 | 全模块检索无命中 |
| 鉴权/租户 | `get_current_user` + `@require_permissions`/`@require_roles`；租户经 ContextVar + `TenantAwareRepository` 自动注入 | 见 `.trae/rules/security/*` |

### 1.6 现有原型与设计文档盘点

统一原型目录 = `docs/features/F6.0-membership-card-prototype/`（**本次不得覆盖其任何文件**）。

可复用工程惯例（务必沿用）：

- 单文件 HTML 原型：`prototype/index.html`（内联 `<style>` + 内联 `<script>`，`STATE` 全局状态 + `setView()`/`renderAll()`/`goXxx()` 视图函数 + `resetData()`）。
- 视觉 token（index.html:8-18）：`--blue:#409EFF`、`--brand:#667eea`、`--brand2:#764ba2`、`--gold:#C9A66B`、`--red:#f56c6c`、`--orange:#e6a23c`、`--bg:#f0f2f5`、`--border:#ebeef5`、`--text:#303133`。
- 验证脚本：`verify-prototype.js`（Node CommonJS，正则抽取 `<script>` → `new Function` 语法检查 → DOM stub 下真实调用函数 → `ok(name,cond,extra)` 计数 → 退出码 通过 0 / FAIL 1）。
- 文档模板：`screen-inventory.md` / `interaction-spec.md` / `entity-state-model.md` / `open-decisions.md` / `prototype-acceptance.md`。

### 1.7 缺失项（如实记录）

- `apps/api/src/app/modules/upload/models.py` 为空 → 上传能力**未实现**（原型只能 Mock）。
- 教室 `cover_image_url / capacity / location / code` 字段**均不存在** → 属新增字段，须标「待评审」。
- 首页「公告/活动」区块在小程序**不存在** → 属新增设计。
- banner/video 在小程序为**硬编码静态数据** → 需新增后台配置实体。
- 无 `docs/features/F7.0-*` 既有产物（本轮为首次创建）。

---

## 二、需求拆解（A / B / C / D / E）

### 需求 A：用户管理增加头像上传

**目标**：管理端用户列表展示头像；新增/编辑用户支持头像上传全流程。

- 列表：增加「头像」列（`el-avatar`，缺失时默认头像），**保留**现有搜索/角色筛选/状态筛选/分页/操作列，**不删减**现有字段与操作。
- 弹窗：头像上传区 = 点击选择 → 本地预览 → 更换 → 移除 → 上传中 → 格式/大小校验错误 → 上传失败与重试 → 取消（避免未保存覆盖）。
- 技术评估点（详见 solution-design.md 第四节）：图片与用户资料关联方式 / PG 存 URL vs object key vs 文件记录 / 本地 vs 生产对象存储 / 是否阿里云 OSS / FastAPI 上传 vs 受控直传 / 类型·大小·权限·租户隔离·清理策略。

**现状差异**：DB/DTO/api-client **已具备 `avatar_url`**，缺的是（a）列表与弹窗 UI，（b）**上传接口**（upload 模块为空壳）。

### 需求 B：右上角登录用户资料修改

**目标**：全局用户菜单 + 个人资料弹窗。

- 交互：点头像/姓名 → 下拉（个人资料 / 退出登录，保留现有「退出登录」）→ 个人资料弹窗（头像、昵称、手机号、角色只读）→ 保存/取消/校验/保存失败 → 顶部头像与昵称同步更新。
- 约束：复用现有全局布局与 `GET/PATCH /auth/me`；**普通用户不得修改角色/租户/权限**；未确定字段进 open-decisions.md。

**现状差异**：`PATCH /auth/me` **仅允许 nickname + avatar_url**（service 白名单 L63），故**手机号不可自助修改** → 记入 open-decisions（D-F7-B2）。

### 需求 C：教室管理增加图片展示

**目标**：在现有教室页上扩展，**仅保留卡片视图**（`D-F7-C2`：不提供表格/列表视图与视图切换）。

- 卡片：封面图 / 名称 / 教室编码（**已确认新增**） / 位置(待评审) / 设备 / 操作入口。**已删除容纳人数与启用停用状态**。
- 状态：卡片视图、新增、编辑、图片上传预览、**未设置封面→「暂无图片」占位**、图片失效→占位、搜索无结果、空列表、加载失败。
- **决策（2026-10-19，产品确认）**：教室为图片型实体，卡片视图信息表达更直观，**不并存表格 + 卡片双视图**（避免双视图带来的结构/分页/批量操作归属复杂度）。

**现状差异**：教室表**无图片/编码/位置/容量**字段；页面**仅卡片视图**。新增字段中 `code`（教室编码）为**已确认新增**、`location` 标「待评审」；**`capacity`（容纳人数）已删除、不引入**；不虚构字段。

### 需求 D：后台新增一级导航「小程序装修 / 首页管理」

**目标**：新增一级导航（建议名「小程序装修」，最终名待定，见 D-F7-D1），管理小程序首页模块。

- 第一阶段：**固定模块配置**，非自由拖拽搭建器。
- 模块类型（≥5）：Banner 轮播 / 师资团队 / 推荐课程 / 舞蹈视频 / 公告或活动。
- 页面能力：模块列表 / 名称与类型 / 启用·停用开关 / **排序字段 + 拖动排序**（`D-F7-D2` 已确认）/ 编辑入口 / 配置表单 / 图片上传与预览 / 内容选择或数据来源设置 / 保存草稿 / 预览小程序首页 / 发布 / 发布成功·失败提示。
- 编辑用**右侧抽屉（drawer）或弹窗**，风格与现有后台一致。
- 各模块配置项（不堆无业务价值项）：
  - Banner：图片 / 标题 / 副标题(可选) / 跳转目标 / 展示顺序 / 启用。
  - 师资团队：模块标题 / 展示数量 / 教师选择（复用现有教师数据）。
  - 推荐课程：模块标题 / 课程选择 / 展示数量 / 排序规则。
  - 舞蹈视频：视频标题 / 封面图 / 视频地址 / 跳转目标。
  - 公告/活动：标题 / 内容 / 图片(可选) / 有效期 / 展示状态。

### 需求 E：小程序首页从静态数据转为后台管理数据

**数据流**：后台编辑 → 保存草稿 → 预览 → 发布 → FastAPI 保存并提供已发布配置 → 小程序调首页接口 → 按模块类型/顺序/展示状态渲染。

**必须评估**：草稿与线上发布是否分离；预览能否看未发布修改；发布失败是否保留旧版本；小程序请求失败降级；模块为空/停用展示；图片失效占位；首页接口是否需租户上下文；已发布配置跨租户隔离；改草稿不影响线上。

**现状差异**：banner/video 为小程序硬编码；师资/课程已走真实 API（可复用为"内容选择"数据源）；无首页配置后端。

---

## 三、现状与目标差异汇总（Gap 表）

| # | 能力 | 现状 | 目标（F7.0 原型） | 性质 |
|---|------|------|-------------------|------|
| G1 | 用户头像展示 | 无头像列；DB/ DTO 已有 `avatar_url` | 列表头像列 + 默认头像 | **UI 扩展（后端字段已备）** |
| G2 | 用户头像上传 | **无上传接口**（upload 空壳） | 上传交互全流程（Mock） | **新增接口（候选）** |
| G3 | 个人资料入口 | 下拉仅「退出登录」 | 下拉 + 个人资料弹窗 | UI 扩展（接口已备） |
| G4 | 手机号自助修改 | `PATCH /auth/me` 仅 nickname+avatar | 手机号**只读** | 差异 → 记 open-decision |
| G5 | 教室图片/字段 | 无 image/编码/位置/容量 | 卡片含封面图、教室编码、位置 | **新增 DB 字段（编码已确认；位置待评审；容量已删除）** |
| G6 | 教室视图形态 | 仅卡片网格 | **保持仅卡片视图**（`D-F7-C2`：不新增表格视图/视图切换） | 决策固化（不扩展） |
| G7 | 首页模块配置 | 无 | 模块列表 + 编辑 + 排序 + 启停 | **新增模块** |
| G8 | 首页草稿/预览/发布 | 无 | 草稿·预览·发布机制 | **新增模块** |
| G9 | 首页已发布读取 | 小程序硬编码 banner/video | 小程序调已发布配置接口 | **新增接口** |
| G10 | 公告/活动区块 | 小程序无此区块 | 新增配置 + 预览渲染 | **新增** |

---

## 四、本次范围（In Scope）

1. 需求 A/B/C/D/E 的**原型级设计**与**技术方案评审**（不含正式实现）。
2. 10 项交付物（见第六节）：分析文档 + 页面清单 + 交互规格 + 实体状态 + 待确认决策 + 验收标准 + 可交互 HTML 原型 + Figma 导入说明 + 测试报告 + 原型检查脚本。
3. 图片存储 A/B/C 三方案对比与推荐（结合现有 Docker/Compose/Nginx/阿里云 ECS 部署）。
4. 后续正式实现所需的候选 API 与数据模型建议（先核对现有接口，再定复用/扩展/新增）。

## 五、非目标（Out of Scope）

- ❌ 不修改正式业务代码 / 不修改数据库模型与迁移 / 不修改真实 API。
- ❌ 不修改登录、权限、租户隔离等业务逻辑。
- ❌ 不覆盖 F6.0 及任何既有原型文件；不删除用户文件或未提交修改。
- ❌ 不安装不必要依赖；不接入真实 OSS；不创建真实云存储凭证；不修改部署配置。
- ❌ 不声称 Mock 交互已接通后端；不伪造接口 / 字段 / 数据库结构 / 测试结果。
- ❌ 不实现自由拖拽式（page builder）首页搭建器（第一阶段固定模块）。

## 六、交付物清单（对应任务书第六节）

| # | 交付物 | 路径 |
|---|--------|------|
| 1 | requirements-analysis.md | `docs/features/F7.0-admin-console-miniapp-home-prototype/requirements-analysis.md` |
| 2 | solution-design.md | 同目录 |
| 3 | screen-inventory.md | 同目录 |
| 4 | interaction-spec.md | 同目录 |
| 5 | entity-state-model.md | 同目录 |
| 6 | open-decisions.md | 同目录 |
| 7 | prototype-acceptance.md | 同目录 |
| 8 | 可运行 HTML/CSS/JS 原型 + 启动说明 | `.../prototype/index.html`（启动说明见 `prototype/README.md`） |
| 9 | Figma 导入说明 | `.../figma-import-guide.md` |
| 10 | prototype-test-report.md | 同目录 |
| + | 原型可执行检查脚本 | `.../verify-prototype.js` |

---

## 七、阶段 1 结论

现状与任务书描述**大体一致但有 3 处关键更正**，必须在后续设计与原型中显式处理：

1. **头像链路并非从零**：`users.avatar_url`、DTO、api-client 字段均**已存在**，真正缺的是「上传接口 + 前台展示/编辑 UI」。
2. **教室模型极简**：仅 `name/equipment/status`，任务书要求的「封面图/位置/教室编码」为新增字段（`code` **已确认新增**、`location` 待评审），**容纳人数 `capacity` 已删除、不引入**；不得当作已有字段。
3. **小程序首页 ≠ `pages/index`**：真实内容首页是 `pages/student/courses/index.vue`，其中 banner 与 video 是**硬编码静态数据**，师资与课程已走真实 API；**公告区块不存在**。这决定了需求 D/E 的模块来源分类（见 solution-design.md 第五节）。
