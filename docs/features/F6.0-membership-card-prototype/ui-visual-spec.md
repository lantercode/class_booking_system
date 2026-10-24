# UI 视觉规格书（UI Visual Spec）—— F6.0 会员卡原型视觉还原依据

> 勘察日期：2026-10-10（状态更新：2026-10-16）
> 用途：供下一个 Agent 在 HTML 中还原"真实页面"视觉时使用。所有颜色值均提取自真实源码，标注 `文件:行号` 证据；未标注证据的 Element Plus 默认值均已显式声明"默认主题"。
> 配套文档：同目录 `existing-page-mapping.md`（页面映射与分类）。
>
> **状态（2026-10-16）**：D1 / D3 / D4 / D5 / D9 决策已确认，原型对应"决策占位"便签改为绿色"已确认"（详见 `interaction-spec.md` 头部状态说明与 `prototype-validation-report.md` v7）。本规格书为纯视觉基准，不含决策占位内容，视觉项无变化。
> **管理端对齐（2026-10-16）**：管理端页面已按真实 admin-web 对齐（2026-10-16），§1（管理后台）列 / 状态文案 / tag 色与真实源码一致；本次仅补充"计费方式 tag 色两页不同"的说明（见 §1.6 注、§1.9），未改动其他视觉项。

---

## 1. 管理后台（apps/admin-web，Vue3 + Element Plus）

### 1.1 主题色

- **Element Plus 主色：默认主题 `#409EFF`**。证据：`apps/admin-web/src/main.ts` L4 直接引入 `element-plus/dist/index.css`，全项目无任何 `--el-color-primary` 覆写；`apps/admin-web/src/styles/index.scss` L45 的主按钮渐变起点为 `#409eff`，L145 链接按钮 `color: #409eff !important`，佐证主色即默认值。
- **品牌紫（辅助识别色，用于侧边栏/logo/激活态）**：`#667eea` → `#764ba2` 渐变。证据：`apps/admin-web/src/layout/AdminLayout.vue` L200（logo 渐变 `linear-gradient(135deg, #667eea, #764ba2)`）、L230（激活菜单右侧 3px 边框 `#667eea`）、L255（hover 图标色 `#667eea`）。
- 语义色全部为 Element Plus 默认：success `#67C23A`、warning `#E6A23C`、danger `#F56C6C`、info `#909399`（页面内联使用见 membership/index.vue L118 `#e6a23c`、L135 `#67c23a` 等）。

### 1.2 布局结构（AdminLayout.vue）

| 区域 | 规格 | 证据 |
|------|------|------|
| 侧边栏 | 宽 220px（折叠 64px），背景 `#1a1a2e`，菜单文字 `#a0a0b8`，激活文字 `#fff`，激活项背景 `linear-gradient(90deg, rgba(102,126,234,0.3), transparent)` + 右侧 3px `#667eea` 边框 | AdminLayout.vue L3、L19-L22、L228-L231 |
| Logo 区 | 高 60px，底部 `1px solid rgba(255,255,255,0.08)` 分隔；logo 图标 36×36、圆角 10px、紫渐变底、白色 Management 图标；标题"约课管理"16px/700/白 | AdminLayout.vue L189-L215 |
| 顶栏 | 白底，高 60px（el-header 默认），左右 padding 24px，阴影 `0 1px 4px rgba(0,0,0,0.06)`；左侧折叠按钮+面包屑（首页/当前页），右侧头像 32px+昵称+下拉 | AdminLayout.vue L45-L75、L235-L241 |
| 内容区 | 背景 `#f0f2f5`，padding 24px，滚动区；底部 footer 高 48px 白底（备案信息） | AdminLayout.vue L286-L292、L294-L298 |
| 页面容器 | `.page-container`：白底、圆角 8px、padding 24px、占满高度 | styles/index.scss L15-L23 |
| 页头 | `.page-header`：标题 h2 20px/600/`#1a1a2e`，与右侧按钮组两端对齐，下边距 16px | styles/index.scss L25-L36 |

### 1.3 菜单文案与图标（侧边栏实际渲染项，AdminLayout.vue L145-L157）

依次为：用户管理(User)、角色权限(Key)、教师管理(Avatar)、学员管理(UserFilled)、课程管理(Reading)、教室管理(OfficeBuilding)、排期管理(Calendar)、卡产品管理(Collection)、会员卡管理(CreditCard)、机构设置(Setting)。注：路由中还定义了"控制台 /dashboard"（router/index.ts L23-L28，icon Odometer），但菜单数组中已被注释掉（AdminLayout.vue L146），侧边栏不显示。

### 1.4 表格样式（styles/index.scss L79-L132，全局定制）

- 外边框 `1px solid #ebeef5`、圆角 8px、overflow hidden。
- 表头：背景 `#f5f7fa !important`、文字 `#303133`、600 字重、14px、底边框 `#ebeef5`。
- 单元格右边框 `1px solid #ebeef5`；斑马纹行背景 `#fafafa`（页面用 `stripe`）。
- 行高为 Element Plus 默认（约 40px+，无覆写）；页面普遍配 `.pagination-wrapper`（右对齐分页，`total, prev, pager, next`，background 模式）。

### 1.5 按钮风格

- 主按钮（type=primary）：**渐变** `linear-gradient(135deg, #409eff 0%, #3a8ee6 100%)`、无边框、阴影 `0 2px 8px rgba(64,158,255,0.3)`、圆角 8px（styles/index.scss L39-L57）。
- 危险按钮（type=danger）：渐变 `linear-gradient(135deg, #f56c6c 0%, #e04040 100%)`、无边框、白字、阴影 `rgba(245,108,108,0.3)`（L59-L74）。
- 次按钮：Element Plus 默认白底描边。
- 表格内操作按钮：`size="small" link` 形态，按语义取 primary/warning/success/danger（membership/index.vue L154-L193）。

### 1.6 状态标签（el-tag size=small 的使用习惯）

| 状态 | tag type | 文案 | 证据 |
|------|----------|------|------|
| 会员卡：未激活(0) | info | 未激活 | membership/index.vue L1074-L1094 |
| 会员卡：正常(1) | success | 正常 | 同上 |
| 会员卡：已过期(2) | warning | 已过期 | 同上 |
| 会员卡：已冻结(3) | danger | 已冻结 | 同上 |
| 会员卡：已作废(6) | info | 已作废 | 同上 |
| 计费方式：次卡 | primary | 次卡 | membership/index.vue L1101-L1109 |
| 计费方式：期卡 | success | 期卡 | 同上 |
| 计费方式：无限卡 | warning | 无限卡 | 同上 |
| 卡产品：上架 | success | 上架 | card-types/index.vue L69-L71 |
| 卡产品：下架 | info | 下架 | 同上 |

规律：**正常/生效 → success；过期/待处理 → warning；冻结/危险 → danger；未激活/作废/下架 → info**。

> 注：**计费方式 tag 色两页不同**——上表三行为**会员卡管理页**（`membership/index.vue` L1101-L1109：`count=primary / period=success / unlimited=warning`）；而**卡产品管理页**（`card-types/index.vue` L276-L280）为 `count=success / period=warning / unlimited=info`。原型 P-A1 用后者、P-A2 用前者。

### 1.7 弹窗风格

- Element Plus 默认 `el-dialog`，宽度 460px–600px（发放 560px、详情 600px、冻结/作废 460px、批量 500px），`:close-on-click-modal="false"`。
- 内部为 `el-form`（label-width 100–110px）或 `el-descriptions :column="2" border`（详情弹窗，membership/index.vue L300）。
- footer 统一：左侧"取消"默认按钮 + 右侧"确定"primary 按钮（loading 态）。
- 特殊：续卡提示弹窗用暖色系排版（标题文字 `#e6a23c`、规则区背景 `#f5f7fa` 圆角 8px、成功提示 `#67c23a`，membership/index.vue L1216-L1272）；冲突卡号徽标为蓝底胶囊 `background: #e8f3ff; color: #165dff` 等宽字体（L1376-L1387）。

### 1.8 membership/index.vue 表格列清单（真实还原用）

| 列 | label | 宽度 | 渲染 |
|----|-------|------|------|
| selection | — | 55 | 复选框（status=2/6 不可选） |
| index | 序号 | 60 | 自动序号 |
| card_no | 会员卡号 | 170 | el-link primary 可点击打开详情，空显示 `-` |
| product_name | 产品名称 | min-width 120 | 纯文本 |
| card_type | 计费方式 | 100 | el-tag small（次卡 primary/期卡 success/无限卡 warning） |
| student_nickname | 学员 | 100 | 纯文本 |
| student_phone | 手机号 | 120 | 纯文本 |
| total_credits | 总次数 | 80 | 仅 count 显示数字，否则 `-` |
| used_credits | 已用 | 80 | 同上 |
| remaining_credits | 剩余 | 80 | 同上 |
| status | 状态 | 120 | el-tag small + 冻结冲突时橙色 WarningFilled 图标 |
| 有效期 | 有效期 | 360 | `YYYY-MM-DD 00:00:00 ~ YYYY-MM-DD 23:59:59` |
| 冻结信息 | 冻结信息 | 140 | 仅列表含冻结卡时显示（v-if hasFrozenCard）：剩余 N 天解冻（≤0 橙 `#e6a23c`，>0 绿 `#67c23a`）+ 冲突 warning plain tag |
| 操作 | 操作 | 240，fixed right | 按状态渲染 link 按钮：激活(success)/冻结(warning)/提前解冻·强制解冻(success)/作废(danger) |

顶部操作区：`发放会员卡`（primary）+ `批量作废`（danger，需选中）；筛选行：搜索框 240px（placeholder"搜索学员或手机号"）+ 状态多选下拉 160px（未激活/正常/已过期/已冻结/已作废）。

### 1.9 card-types/index.vue 表格列清单

| 列 | label | 宽度 | 渲染 |
|----|-------|------|------|
| selection | — | 55 | 复选框 |
| index | 序号 | 60 | 自动序号 |
| name | 产品名称 | min-width 120 | 纯文本 |
| card_type | 计费方式 | 100 | el-tag small（次卡 success / 期卡 warning / 无限卡 info，见 card-types/index.vue L276-L280） |
| total_credits | 包含次数 | 100 | 仅 count |
| validity_days | 有效天数 | 100 | count/period |
| price | 价格(元) | 100 | 纯文本 |
| applicable_course_type_code | 适用课程类型 | 自适应 | el-tag（getCourseTypeTagType），空显示灰字"不限"（`#909399`） |
| status | 状态 | 80 | success"上架"/ info"下架" |
| 操作 | 操作 | 200，fixed right | 编辑(primary)/下架(warning)或上架(success)/删除(danger，仅 status=0) |

顶部：`新增`（primary）+ `批量删除`（danger，仅 admin 且已选中）。新增/编辑弹窗字段：产品名称、计费方式（仅次卡/期卡选项）、包含次数、有效天数、价格(元)、适用课程类型（单选、必填）、描述。

---

## 2. 学员小程序（apps/miniapp，uni-app → 微信小程序）

### 2.1 设计系统主色 —— "高级轻奢 · 香槟金"

定义文件：`apps/miniapp/src/styles/theme/_variables.scss`（经 `vite.config.ts` L27 additionalData 全局注入，App.vue 直接使用 `$` 变量）。

| 变量 | 值 | 行号 |
|------|----|------|
| `$primary-solid` | **`#C9A66B`（香槟金，全局主色）** | L14 |
| `$primary-gradient` | `linear-gradient(135deg, #C9A66B 0%, #D4AF77 50%, #E8D5B7 100%)` | L13 |
| `$primary-dark` / `$primary-light` | `#B8956A` / `#DBC18A` | L15-L16 |
| `$accent-solid`（莫兰迪粉强调色） | `#D9A7B0` | L22 |
| `$bg-primary`（页面主背景，温暖米白） | `#FAF8F5` | L66 |
| `$text-primary` / `$text-secondary` / `$text-tertiary` | `#1A1A1A` / `#5A5248` / `#8E8579` | L73-L75 |
| `$success-color` / `$warning-color` / `$error-color` / `$info-color` | `#7CB986` / `#D4A76A` / `#D4847A` / `#8BA4B8` | L39-L53 |
| `$radius-lg`（卡片圆角） | 20rpx（弹窗 24rpx、底部弹窗顶 32rpx） | L94-L100 |
| `$shadow-sm` | `0 4rpx 16rpx rgba(26,26,26,0.06)` | L182 |

页面级实际背景（会员卡/预约页统一）：`linear-gradient(180deg, #faf6f0 0%, #f5ede3 100%)`（membership/index.vue L984）与 `linear-gradient(180deg, #faf6f0 0%, #f5efe6 100%)`（booking-confirm L746、bookings L311）。

### 2.2 导航栏

- pages.json globalStyle（L160-L166）：`navigationBarBackgroundColor: #ffffff`、`navigationBarTextStyle: black`、标题"舞蹈约课"、页面背景 `#f5f5f5`。
- 会员卡页：原生导航栏，标题**"我的会员卡"**（pages.json L133-L137）。
- 自定义导航页面（navigationStyle: custom）使用 `AppNavbar` 组件，如"预约确认""预约记录"（booking-confirm L3、bookings L3）。

### 2.3 TabBar

**pages.json 无原生 tabBar 配置**；TabBar 为自定义组件，高 100rpx（`$tabbar-height`，_variables.scss L303）：

- 学员端：**`HomeTabBar.vue`**（三 Tab：**首页 / 排期 / 我的**，蓝本 `pages/student/courses|schedule|profile`）。⚠️ 仓库中另有 `StudentTabBar.vue`，但**无任何页面引用（废弃文件）**，不得作为复刻依据。
- 教师端：`TeacherTabBar.vue`（课程/排期/我的）。

**HomeTabBar 规格（`components/HomeTabBar.vue`，原型 ground truth）**：

- 容器 `.tab-bar`：`position:fixed; bottom:0; display:flex; background:#fff; padding:12rpx 0 28rpx; border-top:1rpx solid #f5f5f5; box-shadow:0 -2rpx 12rpx rgba(0,0,0,.04)`。
- 项 `.tab-item`：`flex:1; column; align/justify:center; position:relative; padding:8rpx 0`。
- 文案 `.tab-text`：`font-size:22rpx; color:#999; margin-top:6rpx; transition:.3s`；激活态 `color:#8b7355; font-weight:500`（**激活色为棕 `#8b7355`，非主色金 `#c9a66b`**）。
- 图标：`AppIcon` `tab-home`/`tab-booking`/`tab-profile`，`:size="48"`（rpx），**线性 SVG**（`stroke=currentColor`）；激活 `#8b7355`、非激活 `#999`。
- 指示条 `.tab-indicator`：`position:absolute; bottom:0; width:40rpx; height:4rpx; background:linear-gradient(90deg,#c9a66b,#d9a7b0); border-radius:2rpx`（**仅激活项渲染**）。
- 路由：`首页→/pages/student/courses/index`、`排期→/pages/student/schedule/index`、`我的→/pages/student/profile/index`；切换用 `uni.redirectTo`。
- **显示范围**：仅 `courses`/`schedule`/`profile` 三页挂载；`membership`、`bookings` 等 pushed 页**无 TabBar**（这些页为原生导航栏，带返回）。

> ⚠️ **原型与真实端的差异（本次 AI 助手改造，2026-10-15）**：真实 `HomeTabBar.vue` 目前仍是**三 Tab**；本次产品需求要求将 AI 助手升为**一级 Tab**，原型已改为**四 Tab（首页 / 排期 / AI 助手 / 我的）**：AI 助手插入「排期」与「我的」之间，复用真实 `ai-robot` 线性图标，其余样式（高度/字号/激活色 `#8b7355`/指示条）与三 Tab 完全一致。**真实 miniapp 尚未改造**，且其现行 AI 实现为 `components/AiAssistant.vue`（悬浮 FAB + 650rpx×800rpx 弹窗，配色为**蓝紫 `#667eea→#764ba2`**）。原型按用户明确指令**沿用香槟金主题、不采用蓝紫**，并**如实标注"模拟对话（未接入真实 AI）"，不伪造真实接入**。

### 2.4 我的会员卡页（pages/student/membership/index.vue）

页面结构：顶部"有效课卡 N / 无效课卡 N"双筛选胶囊 Tab → 卡片列表（scroll-view）。

**筛选 Tab**（L999-L1027）：默认半透明白底 `rgba(255,255,255,0.7)`、圆角 50rpx、文字 `#b8a088`；激活态渐变 `linear-gradient(135deg, #d4b896 0%, #c9a66b 100%)` + 白字 + 阴影 `0 4rpx 20rpx rgba(201,166,107,0.35)`。

**卡片视觉**（L1045-L1084，圆角统一 `$radius-lg`=20rpx，阴影 `0 2rpx 12rpx rgba(0,0,0,0.05)`）：

| 卡状态 | class | 背景 | 证据 |
|--------|-------|------|------|
| 使用中 | card-active | 金色渐变 `linear-gradient(135deg, #fdf6e9 0%, #f9edda 30%, #f5e6c8 60%, #f0d9a8 100%)` + 边框 `1rpx solid rgba(201,166,107,0.2)` + 阴影 `rgba(201,166,107,0.2)` | L1051-L1062 |
| 已用完 / 未激活 | card-used-up / card-pending | `linear-gradient(135deg, #faf8f5 0%, #f7f3ed 100%)` | L1064-L1072 |
| 冻结中 | card-frozen | `linear-gradient(135deg, #f5f7fa 0%, #eef1f5 100%)`（蓝灰） | L1074-L1077 |
| 已过期 | card-expired | `linear-gradient(135deg, #f8f6f3 0%, #f3f0eb 100%)` + `opacity: 0.65` | L1079-L1083 |
| 已作废 | card-voided | 复用无效卡灰化观感 | L630-L634 |

**状态徽标**（`.card-status-badge` 胶囊，浅色底+圆点+文字，L1119-L1210）：

| 徽标 | 圆点色 | 文字色 | 底色 |
|------|--------|--------|------|
| 使用中 | `#4caf50` | `#2e7d32` | `rgba(76,175,80,0.12)` |
| 已用完 | `#9e9e9e` | `#757575` | `rgba(158,158,158,0.1)` |
| 未激活 | `#ffb74d` | `#e65100` | `rgba(255,183,77,0.15)` |
| 已过期 | `#ef5350` | `#c62828` | `rgba(244,67,54,0.1)` |
| 已作废 | `#bdbdbd` | `#757575` | `rgba(158,158,158,0.1)` |
| 冻结中 | `#6495ed` | `#4a7bd4` | `rgba(100,149,237,0.12)` |

**卡面内容**：产品名（28rpx/700/`#333`）+ 徽标；"卡号"行（label+号码 `#999`，激活卡 `rgba(90,74,42,0.6)`，带复制图标）；使用区大数字展示——剩余次数 56rpx/700/**`#c9a66b`**、DIN 字体，"/ 总次数"36rpx `#999`（用尽时数字转红 `#ef5350`），分隔竖线 1rpx×24rpx，右侧"有效期至 YYYY-MM-DD"；期卡显示"剩余 N 天"，无限卡显示 ∞ 图标+"不限次"。

**按钮样式**（胶囊 32rpx 圆角，白字 24rpx）：
- `立即激活`：金渐变 `linear-gradient(135deg, #d4b896 0%, #c9a66b 100%)` + 阴影 `rgba(201,166,107,0.3)`（L1569-L1590）。
- `提前解冻`：蓝渐变 `linear-gradient(135deg, #6495ed 0%, #4a7bd4 100%)`（L1605-L1626）；有冲突时灰胶囊提示"存在冲突卡，无法提前解冻"。
- 空状态：3D 金卡插画 + "暂无有效会员卡"/"您还没有领取或激活会员卡" + **`前往办理`** 金渐变胶囊按钮（tap 后 toast"请联系管理员办理会员卡"）+ 权益四宫格（专属课程优惠/更多会员权益/优先预约课程/享受专属服务）。
- 激活/解冻确认使用 `uni.showModal`（"确认激活"/"确认解冻"）。

### 2.5 预约确认页（pages/student/booking-confirm/index.vue）

结构：AppNavbar"预约确认" → 三张白卡（圆角 24rpx、白底、阴影 `0 4rpx 20rpx rgba(201,166,107,0.08)`，L772-L781）：
1. **课程信息卡**：卡头（金渐变圆图标 48rpx `linear-gradient(135deg,#d4b896,#c9a66b)` + 标签 30rpx/600/`#5a4a3a` + 金色渐变短线）；正文列出课程名、日期、时间、教室、教师、"剩余 X/Y 人"，图标色 `#b8956a`，文字 `#8a7a6a`（26rpx）。
2. **使用会员卡卡**：已选卡行（卡名/剩余 N 次/适用课程）+ 右侧卡类型徽标 + 箭头，点击弹出选卡弹窗。
3. **注意事项卡**：◆ 金色菱形 `#c9a66b` + 条目（"开课前X分钟内不可取消预约"等）。

**卡类型徽标**（渐变浅底胶囊，L903-L936 与 L1288-L1320）：次卡 `type-count` → 底 `rgba(255,236,210,.6)→rgba(252,182,159,.6)`、字 `#c97a5e`；期卡 `type-period` → 底 `rgba(168,237,234,.6)→rgba(254,214,227,.6)`、字 `#6ba3a0`；无限卡 `type-unlimited` → 底 `rgba(210,153,194,.6)→rgba(254,249,215,.6)`、字 `#9b6b8a`。

**底部操作栏**（fixed，白底+上边框金 10% 透明，L968-L1017）：两按钮各占一半、高 88rpx、圆角 44rpx；`取消`（底 `#f5efe6`、字 `#8a7a6a`）；**`确认预约`**（渐变 `linear-gradient(180deg,#d4b896,#c9a66b)`、白字、阴影 `rgba(201,166,107,0.3)`；禁用态底 `#f5efe6` 字 `#c0b0a0`）。

**选卡底部弹窗**（L1020-L1320）：遮罩 `rgba(0,0,0,0.5)`；弹窗白底、顶部圆角 32rpx、max-height 70vh、上滑动画；标题"选择会员卡"+ 圆形关闭钮（底 `#f5efe6`、× `#8a7a6a`）；卡选项行（圆角 16rpx、边框 `2rpx solid #ebe5da`），**选中态**边框 `#c9a66b` + 背景 `rgba(201,166,107,0.08)` + 金色 radio（36rpx 圆、选中底 `#c9a66b`、白点 16rpx）；不可用卡点击弹 showModal 显示原因（未激活/已过期/已冻结/已作废/次卡已用完/不适用于此课程类型）；底部通栏"确定"按钮（样式同确认预约）。文案："暂无可用的会员卡"、"剩余 N 次"、"剩余 N 天"、"永久有效"、"适用：XX"、"适用全部课程"。

### 2.6 我的预约页（pages/student/bookings/index.vue）

- AppNavbar 标题**"预约记录"**；筛选胶囊 Tab：`全部 / 待上课 / 上课中 / 已完成`（L150-L155），激活态金渐变同上（L351-L355）。
- 预约卡片：白底、圆角 24rpx、阴影 `rgba(201,166,107,0.08)`、入场动画；内容：课程名（32rpx/600/`#5a4a3a`）+ 状态徽标 + 日期（"M月D日 HH:mm"）/教室/教师行（图标 `#b8956a`）。
- **状态徽标**：样式统一（底 `rgba(201,166,107,0.1)`、圆角 24rpx、文字 `#b8956a` 500 字重，L428-L441），前置 check-circle 图标；**文案映射**（getStatusText L256-L270）：1→"待上课"、2→"已取消"、3→"上课中"、4→"已完成"。（即当前真实实现中四种状态共用同一金色徽标样式，仅文案不同——原型还原时以此为准，不要擅自分配四色。）
- 取消操作：status=1 且可取消时显示通栏 **`取消预约`** 按钮（高 72rpx、圆角 36rpx、边框 `1rpx solid rgba(231,76,60,0.3)`、底 `rgba(231,76,60,0.08)`、字 `#e74c3c`，L459-L465）；不可取消时显示灰字"开课前X分钟内不可取消"（`#a09080`）。确认走 `uni.showModal`（"确认取消 / 确定要取消此预约吗？"）。

### 2.7 课程排期选择（pages/student/schedule/index.vue）

- 排期卡片 `schedule-card` 列表（时间段 + 课程 + 教室/教师/容量）。
- 按钮文案：可预约 → **"预约"**（金渐变 `linear-gradient(135deg,#d4b896 0%,#c9a66b 100%)`，L968、L1060）；已预约 → "已预约"（浅金渐变 `linear-gradient(135deg,#e8d5b7 0%,#d4b896 100%)`，L940/L1300）；不可预约 → "不可预约"。
- 业务提示文案："您需要先办理会员卡才能预约课程"（无卡引导）、"该课程已过期，无法预约"、"仅可预约两周内的课程"、取消时限提示同 2.6。

### 2.8 教师端小程序（pages/teacher/）

- 页面清单：courses（列表/编辑）、schedule（列表/编辑）、**students（学员名单，内含签到）**、profile（资料/编辑/设置）。
- **无独立签到页**；`pages/teacher/students/index.vue` 即名单页：统计栏（已签到/待签到）+ 学员行，`booking_status === 'booked'` 时显示 **"签到"** 按钮（class `action-btn checkin`，handleCheckIn），其余状态按钮显示状态文案（booked/checked_in/completed）。

---

## 3. 教师端 Web（apps/teacher-web，Vue3 + Element Plus）

- **主题：Element Plus 默认主题**（main.ts L4 直接引 `element-plus/dist/index.css`，无覆写 → 主色 `#409EFF`）；全局链接色 `#667eea`（styles/index.scss L19）。
- **无侧边栏布局**：页面自带顶栏（页面级 header：返回按钮 + 居中标题 + 右占位），移动风格，max-width 800px 居中。
- students/index.vue（排期名单+签到）规格：
  - 页面背景：`linear-gradient(180deg, #fef5f9 0%, #f0f2ff 30%, #f5f7fa 100%)`（L187）；页头白色毛玻璃 `rgba(255,255,255,0.85)` + blur(20px)，标题"**学员列表**"17px/700/`#1a1a2e`（L205-L209）。
  - 排期信息卡：紫渐变 `linear-gradient(135deg, #667eea, #764ba2)`、圆角 16px、白字、阴影 `rgba(102,126,234,0.25)`，行：课程/时间/教室（L212-L231）。
  - 统计栏：白卡圆角 16px，三项"已预约/已签到/未签到"，数字 24px/700（默认 `#667eea`、已签到 `#67c23a`、未签到 `#e6a23c`）（L233-L262）。
  - 名单为**卡片列表而非 el-table**：白卡圆角 16px，每行头像 44px + 姓名 15px/600/`#1a1a2e` + 手机号 12px/`#c0c4cc` + 状态 el-tag small + 操作。
  - 状态 tag 映射（L68-L73）：attended/completed → success（"已签到"/"已完成"）、cancelled → info（"已取消"）、confirmed → warning（"待签到"）。
  - 签到按钮：`size="small" type="primary" text`（文字按钮"签到"，仅 confirmed 状态显示）；签到成功 `ElMessage.success("XX 签到成功")`。
  - 空态 `el-empty description="暂无学员预约"`；错误态 `el-result icon="error"` + 重试。

---

## 4. 学员端 Web（apps/student-web）

**一句话结论：无任何会员卡相关页面，不参与原型。** 路由全量核对（`apps/student-web/src/router/index.ts`）：仅 login / register / courses / course-detail / course-schedule / my-bookings / profile 七个路由，无 membership 相关页面。

---

## 5. 原型还原注意事项（易错点）

1. admin-web 主色是 **Element Plus 默认 #409EFF**，但侧边栏/教师端强调色是**紫 #667eea**——两套色并存，不要混用。
2. miniapp 主色是**香槟金 #C9A66B**，与 Web 端完全不同；页面背景统一米白渐变（`#faf6f0 → #f5ede3/#f5efe6`）。
3. miniapp"我的预约"状态徽标真实实现是**统一金色样式+不同文案**，不是四色映射。
4. 小程序没有原生 tabBar（自定义组件），会员卡页用的是原生导航栏（标题"我的会员卡"）。
5. 卡类型文案统一为：count=次卡、period=期卡、unlimited=无限卡；admin 用 tag 色（primary/success/warning），miniapp 用浅渐变徽标（橙/青/紫）。
6. 教师端签到入口在"学员列表"页内（Web 与小程序一致），没有独立签到页。

---

## 6. 结构规格（DOM 层级 / 字段顺序 / 交互模式）—— 2026-10-15 补充

> 补充原因：第 2 节只提取了颜色/变量/尺寸，**漏了 DOM 结构与交互模式**，导致原型出现"配色像了、骨架不像"的结构级偏差（用户实测反馈）。本节为**结构级 ground truth**，逐条带 `文件:行号`；原型必须按此复刻，不得自行简化或改布局。
> 用户已确认原型定位：**严格复刻真实页面**；真实不存在的页面一律标「待新增」且灰置。

### 6.1 P-M1 我的会员卡（`pages/student/membership/index.vue`）

**页面骨架（自上而下）**：根 `view.membership_container` → ①顶部固定筛选 `view.filter-tabs` (L4-L19) → ②`scroll-view.cards-scroll` (L22)。

**① 顶部双胶囊 Tab（L4-L19）**：两枚 `.filter-tab`，文案严格为 `有效课卡 {validCards.length}` / `无效课卡 {invalidCards.length}`；激活态类 `tab-active`。

**② 分组规则（必须照搬，L755-L811）**：

| Tab | 成员 | 判定 |
|-----|------|------|
| 有效课卡 validCards | activeCards + usedUpCards + pendingCards + frozenCards | `status===1`（次卡需 `remaining_credits>0`）；已用完=`status===1 && count && remaining===0`；待激活=`status===0`；冻结=`status===3` |
| 无效课卡 invalidCards | expiredCards + voidedCards | 已过期=`status===2`；已作废=`status===6` |

> 关键：**冻结卡属于"有效"Tab**；**已过期/已作废属于"无效"Tab"**。

**③ 卡片 DOM 骨架**（`card-item card-{active|used-up|pending|frozen|expired|voided}`，L73-L480）：

```
.view.card-item.card-<状态>
 └ .card-content > .card-main
    ├ .card-header     : text.card-name(产品名) + .card-status-badge.status-<态>(.badge-dot + .badge-text)
    ├ .card-no-row     : text.card-no-label("卡号") + text.card-no-text(号码) + .copy-icon-btn(AppIcon copy)   ← 可复制
    └ .card-usage > .usage-main
         ├ .credits-display
         │    └ 次卡(count)  : .credits-remaining / .credits-separator("/") / .credits-total / .credits-unit("次")
         │    └ 期卡(period) : .credits-label("剩余") .credits-remaining .credits-unit("天")
         │    └ 无限卡(unlimited): AppIcon infinity + .usage-unlimited-text("不限次")
         ├ .usage-divider-line            ← 竖线分隔
         └ .usage-valid-range("有效期至 {YYYY-MM-DD}")
```

- 有效卡的有效期行文案：`有效期至 {{ formatDateShort(card.expire_at) }}`（L122-L124）
- PENDING 卡（L288-L365）：可激活时用 `.usage-with-activate`，**使用信息与「立即激活」按钮同一行**（`.card-usage.usage-inline` + `.activate-btn-inline`/`.activate-btn-text`）；无法激活时走 `v-else` 只显使用信息，并在卡片下方追加 **`.activation-warning-box`**（AppIcon warning + `.warning-title`「当前无法激活」+ `.warning-desc` 原因，L431-L445）
- 冻结卡（L448+）：`.card-frozen`，解冻按钮样式见 L1605-L1626

**④ 空状态（仅"有效"Tab 且 validCards.length===0，L26-L69）**：
`.empty-state` → `.empty-card-illustration`（`.card-3d > .card-face` AppIcon crown #c9a66b + `.card-shadow` + `.sparkles` 3 个 ✦ 星光）→ `.empty-title`「暂无有效会员卡」→ `.empty-desc`「您还没有领取或激活会员卡」→ `button.go-handle-btn`（AppIcon card + 「前往办理」+ `.btn-arrow`「›」）→ `.benefits-section`（`.benefits-title`「会员卡可以为您带来」+ `.benefits-grid` 四宫格：专属课程优惠 / 更多会员权益 / 优先预约课程 / 享受专属服务，每格 AppIcon + `.benefit-text`）

**⑤ 交互模式**：卡片**不可点击**（模板中无跳转 handler）；仅「立即激活」「提前解冻」「复制卡号」可操作。激活/解冻走 `uni.showModal` 二次确认。

**⑥ 字段命名（真实 DTO 为 snake_case，原型不得改写成 camelCase）**：`product_name`、`card_no`、`card_type`（`count`/`period`/`unlimited`）、`total_credits`、`remaining_credits`、`valid_from`、`expire_at`、`status`（0/1/2/3/6）。

### 6.2 P-M3 课程排期（`pages/student/schedule/index.vue`）

**页面骨架（L2-L140）**：`AppNavbar`（无标题，`#left` 插槽文案「排期列表」，L3-L7）→ `.main-content` → ①分类筛选栏 `scroll-view.filter-scroll > .filter-list > .filter-pill(.pill-active)`（L11-L23）→ ②日期选择栏 `scroll-view.date-scroll > .date-list > .date-pill`（`.pill-day-name` 星期 + `.pill-day-date` 日期）(L26-L39) → ③`scroll-view.schedule-scroll` 列表。

**排期卡骨架（左时间区 + 右内容区两栏，L60-L138）**：

```
.view.schedule-card
 ├ .schedule-time-section : .time-start / .time-divider / .time-end      ← 左侧时间竖排区
 └ .schedule-content
    ├ .schedule-top      : .course-type-tag(课程类型标签) + .course-name + AppIcon arrow-right
    ├ .schedule-info     : .info-item(location + 教室) / .info-item(user + 教师)
    └ .schedule-footer   : .capacity-info(AppIcon people + .capacity-text「{booked_count}/{capacity}人」)
                           + .btn-wrapper > button.book-btn(状态类见下) + .cancel-hint
```

- **容量口径**：`{booked_count}/{capacity}人`（L107-L109）——注意是"已约/总"，不是"剩余/总"
- 按钮状态类（L114-L122）：`disabled` / `booked` / `no-card` / `not-applicable` / `insufficient` / `weekly-limit`；文案 `schedule._btnText`、取消提示 `schedule._cancelHint`
- 空状态（L50-L58）：`.empty-illustration-img` 插画 + `.empty-title`「暂无排期」+ `.empty-desc`「您还没有相关的课程安排」
- 交互：`_isBooked ? handleBooking(id) : openCardSelector(id)`（L124-L128）——**已预约点按钮=跳预约记录；未预约=打开选卡弹窗**

### 6.3 P-M4 预约确认（`pages/student/booking-confirm/index.vue`）

**页面骨架（L2-L230）**：`AppNavbar` 标题「预约确认」→ `scroll-view.confirm-scroll` → `.confirm-content` → ①`.info-card` 课程信息卡 → ②`.use-card-card` 使用会员卡卡 → ③`.notice-card` 注意事项卡 → ④底部 `.action-bar`。

**三张卡统一 header 结构**（L19-L27 / L75-L83 / L117-L125）：
```
.card-header > .header-left > .header-icon(AppIcon, 白字) + .card-label(文字) + .header-line(装饰线)
```
- ① 课程信息卡 body（L28-L70）：`.course-name` + 5 行 `.info-row`（AppIcon + `.info-text`）：calendar→日期、clock→`{start}-{end}` 时间、location→教室、user→教师、people→`剩余 {capacity-booked_count}/{capacity} 人`
- ② 使用会员卡卡 body（L84-L113）：`.selected-card-info`（点击 `handleOpenCardSelector`）= `.card-details`（`.card-name` / `.card-remaining` / `.card-applicable`）+ `.card-right`（`.card-type-badge.type-{card_type}` + AppIcon arrow-right）
- ③ 注意事项卡（L126-L142）：3 条 `.notice-item` = `.notice-diamond`「◆」+ `.notice-text`（①开课前X分钟内不可取消预约 ②请准时到达教室，迟到可能影响上课 ③如需取消请提前在"我的预约"中操作）
- ④ 底部操作栏（L146-L156）：`button.action-btn.cancel-btn`「取消」+ `button.action-btn.confirm-btn`「确认预约」（`:disabled="!selectedCardId"`）

**选卡交互 = 底部弹窗（**非内联列表**，L158-L230）**：
```
.card-selector-mask(@tap 关闭) > .card-selector-popup(@tap.stop)
  ├ .selector-header : .selector-title「选择会员卡」+ .selector-close「×」
  ├ scroll-view.card-list-scroll
  │   └ .card-option(.card-selected) 
  │      ├ .card-option-left : .card-radio(.radio-checked > .radio-dot) + .card-option-info(.card-option-name / .card-option-remaining / .card-option-applicable)
  │      └ .card-option-type : .type-badge.type-{card_type}
  └ (空) .no-available-cards > .no-cards-text「暂无可用的会员卡」
  └ .selector-footer > button.footer-btn.confirm-btn-small「确定」
```
- 可用性判定在脚本 L271-L379：`isAvailable` / `unavailableReason` / `unavailableDetail`（按状态、次卡余额、课程类型、具体课程限制）

### 6.4 P-M6 我的预约（`pages/student/bookings/index.vue`）

**页面骨架（L2-L116）**：`AppNavbar` 标题「预约记录」`:show-back="true"` → `.main-content` → ①筛选 Tab `view.filter-tabs > .filter-tab(.filter-tab-active)` → ②`scroll-view.booking-list`。

**① 筛选 Tab 确切文案与状态码（L127-L155）**：`全部(all)` / `待上课(BOOKED=1)` / `上课中(CHECKED_IN=3)` / `已完成(COMPLETED=4)`；`CANCELLED=2` 仅在"全部"中可见。

**② 预约卡骨架（L35-L109）**：
```
.view.booking-card
 ├ .card-main > .card-info
 │   ├ .info-top   : text.course-name + .status-badge(.status-<类> : AppIcon check-circle #b8956a + .status-text)   ← 统一金色图标，非四色
 │   ├ .info-row   : AppIcon calendar(#b8956a) + .info-text(日期)      ← formatBookingDate(booking.start_at)
 │   ├ .info-row   : AppIcon location + .info-text(classroom_name)
 │   └ .info-row   : AppIcon user     + .info-text(teacher_name)
 └ .card-actions
     ├ status===1 且 canCancelBooking → button.cancel-btn「取消预约」
     └ status===1 且 !canCancelBooking → text.cancel-disabled「开课前{cancelMinutes}分钟内不可取消」
```
- `cancelMinutes` 来自租户配置 `booking_cancel_minutes`（默认 **90**，L138/L164-L166）
- 空状态（L28-L31）：AppIcon calendar-empty(#d0c0b0) + `.empty-text`「暂无预约记录」
- 字段命名：`course_name` / `start_at` / `classroom_name` / `teacher_name` / `display_status`

### 6.5 P-M8 首页·课程列表（`pages/student/courses/index.vue`）

**页面骨架（L2-L206）**：`AppNavbar`（`#left` = 地点选择器 `.location-selector`，非返回）→ `scroll-view.main-content` → ①Banner 轮播 → ②师资团队（`v-if` 有数据）→ ③推荐课程（`v-if` 有数据/加载中）→ ④舞蹈视频（`v-if` 有数据）→ `.bottom-spacer` → `HomeTabBar`。

**① Banner 轮播**：`swiper.banner-swiper`（`indicator-dots/autoplay/interval=4000/duration=500/circular`，`indicator-active-color=#c9a66b`）→ `swiper-item > .banner-slide`：`image.banner-cover-image` + `.banner-overlay`（深色渐变）+ `.banner-content > .banner-title`（44rpx/700）+ `.banner-subtitle`（26rpx）。
- 真实 5 张：让舞蹈成为生活的一部分 / 专业师资团队 / 多元化课程体系 / 优雅的艺术空间 / 开启你的舞蹈之旅。

**② 师资团队**：`.section-header > .section-title`（`.title-icon` + `.title-text`「师资团队」）→ `scroll-view.teachers-scroll(scroll-x) > .teachers-list > .teacher-item`（`.teacher-avatar`：有 avatar 用 image，否则 `.avatar-placeholder > .avatar-text`=昵称首字；`.teacher-info > .teacher-name` + `.teacher-specialty`）。

**③ 推荐课程**：`.section-header`：`.section-title`「推荐课程」+ `.section-more`（`.more-text`「全部课程」+ `.more-arrow`「›」）→ `.course-list > .course-item`（`slice(0,3)`）：`.course-image > .cover-image` + `.course-info > .course-name` + `.course-desc`。
- 空态 `AppEmpty icon="📚" title="暂无课程" description="当前还没有课程，请稍后再试"`；加载态 `AppLoading type="skeleton"`。

**④ 舞蹈视频**：`.videos-section > .section-header`「舞动 · 让生活更美好」→ `.video-list > .video-card`（`slice(0,3)`）：`.video-cover > .cover-image` + `.video-overlay`（`.play-button > .play-icon`「▶」 + `.video-duration`）+ `.video-info > .video-title` + `.video-desc`。

**尺寸换算（rpx→px ×0.5）**：`$radius-md 16rpx`→8px、`$radius-lg 20rpx`→10px、`$space-md 32rpx`→16px、`$space-lg 40rpx`→20px、`$space-xl 48rpx`→24px。

### 6.6 P-M9 我的·个人中心（`pages/student/profile/index.vue`）

**页面骨架（L2-L118）**：`AppNavbar`（`#left` = `.navbar-title`「我的」，非返回）→ `.profile-header` → `.content-area` → `HomeTabBar`。

**① 个人信息区 `.profile-header`**（L11-L42）：`.header-bg-decoration`（背景装饰）+ `.profile-content`：
- `.avatar-section > .avatar-placeholder > .avatar-text`（无 avatar 时显示昵称首字）
- `.user-info-section`：`.user-name`（昵称，兜底「学员」）+ `.user-role-row`（`.user-role`「学员」+ `.role-divider`「·」+ `.membership-level`=脱敏手机号）+ `.membership-badge`（`AppIcon crown #c9a66b` + `.badge-text`=会员等级）

**② 内容区 `.content-area`**：
- `.membership-card`「我的会员卡」`@tap=goToMembership`（→ `/pages/student/membership/index`）：`.card-bg-pattern` + `.card-content > .card-left`（`.card-icon-wrapper` crown `#c9a66b` + `.card-info > .card-title`「我的会员卡」+ `.card-desc`「查看会员权益 · 课程信息 · 剩余课时」）+ `AppIcon arrow-right #c9a66b`。
- `.menu-group > .menu-card`「预约记录」`@tap=goToBookings`（→ `/pages/student/bookings/index`）：`.menu-item > .menu-left`（`.menu-icon-wrapper` calendar `#8b7355` + `.menu-info > .menu-title`「预约记录」+ `.menu-desc`「查看我的课程预约与历史记录」）+ `AppIcon arrow-right #c9a66b`。
- `.menu-group`：`.menu-card`「解绑微信」（wechat 图标 `#8b7355`，`.menu-desc`「已绑定微信账号」）+ `.menu-card`「退出登录」（`.menu-icon-wrapper.logout-icon` logout `#e74c3c`，`.menu-desc`「安全退出当前账号」）。

**页面底渐变**：`linear-gradient(180deg,#fef6f0 0%,#faf5f0 50%,#f8f2ed 100%)`。

### 6.7 原型硬约束（严格复刻定位，逐条可验证）

1. P-M1 必须有**两个胶囊 Tab**（有效/无效）+ 分组渲染；**已作废卡必须可见**（在"无效"Tab），不得被过滤掉。
2. P-M1 卡片必须含**复制图标**与 `.usage-divider-line` 竖线；次卡余额格式为 `{remaining}/{total}次` 同排。
3. P-M1 卡片**不可点击**；激活按钮在 PENDING 卡**行内**（`.usage-with-activate`），不能激活时显示 `.activation-warning-box`。
4. P-M4 选卡必须是**底部弹窗**（含标题/×/radio 选项/类型 badge/「确定」），不是内联列表。
5. P-M6 必须有**四个筛选 Tab**，且取消受限时展示「开课前X分钟内不可取消」。
6. 真实不存在的页面（P-M2 卡详情、P-M5 预约结果、P-A5 admin 预约管理）必须在原型内标「待新增 · 真实项目不存在」并灰置入口。
7. **底部 TabBar 必须四 Tab 文案「首页 / 排期 / AI 助手 / 我的」**（顺序一致），用**线性 SVG 图标**（tab-home/tab-booking/tab-profile + `ai-robot`），**激活色 `#8b7355`**（非主色金），激活项带 **`.tab-indicator`** 底部指示条。**AI 助手与其它三个同级**，不得设计为悬浮按钮 / 底部弹窗 / 侧边抽屉 / 首页内嵌小窗口。
8. TabBar **仅在 P-M8/P-M3/P-M10/P-M9 四页显示**；会员卡（P-M1）、预约记录（P-M6）等 pushed 页**不显示 TabBar**，改以 `.stu-backbar` 返回条回到「我的」。
9. 必含 **P-M8 首页**（navbar 地点 + Banner + 师资 + 推荐课程 + 视频）与 **P-M9 我的**（navbar 我的 + 个人信息 + 我的会员卡→P-M1 + 预约记录→P-M6）两页；`goStu('P-M1')`/`goStu('P-M6')` 为真实可达跳转。
10. 必含 **P-M10 AI 助手一级 Tab 页**（规格见 §6.8）：顶部标题+会话状态、独立滚动对话区（空状态欢迎语 + 4 个常用问题、用户/AI 消息、加载中、错误态）、底部固定输入区（输入框+发送按钮+安全区）；常用问题点击须**真实产生对应对话**（非装饰按钮）；**不得伪造真实 AI 已接入**。

---

### 6.8 P-M10 AI 助手（一级 Tab 页，本次新增）

> 来源：本次产品需求《将学员小程序端 AI 助手改为一级 Tab 页面》。真实 miniapp 尚无该页面（AI 现为 `components/AiAssistant.vue` 悬浮窗），**原型为新建**；视觉沿用香槟金主题，结构参考真实 AiAssistant.vue 的欢迎区/快捷卡/消息气泡/输入区划分，但将其扩展为**占满整屏的独立页面**。

**页面骨架（三步式，自上而下）**：内容区切换为 `ai-mode`（`padding:0;overflow:hidden;display:flex;flex-direction:column`）后：

```
.stu-content.ai-mode
 └ .ai-page(flex:1,min-height:0,竖排,米白渐变底)
    ├ .ai-header            ← 顶部区域(固定,不占过多垂直空间)
    │   ├ .ai-hic(圆形金渐变机器人图标)
    │   ├ .ai-htxt : .ai-hname「AI 助手」+ .ai-hsub(.ai-dot 绿点 + 会话状态文案)
    │   └ .ai-clear「清空」(右对齐胶囊按钮)
    ├ .ai-msgs(flex:1,min-height:0,overflow-y:auto)   ← 对话区:占主要空间,独立滚动
    │   ├ 空状态 .ai-welcome : .ai-wbadge(.ai-wic 灯泡 +「您可以问我：」)
    │   │        + .ai-quick > .ai-qcard × 4(.ai-qic + .ai-qtext + .ai-qarrow「›」)
    │   ├ 用户消息 .ai-msg.user > .ai-bubble(右对齐,金渐变底白字)
    │   ├ AI 消息   .ai-msg.ai   > .ai-av(机器人头像) + .ai-bubble(白底左气泡)
    │   │            └ 错误态 .ai-bubble.err(浅红底) +「⚠️」前缀
    │   └ 加载中    .ai-msg.ai   > .ai-av + .ai-bubble > .ai-dots(3 点 aiDot 动画)
    └ .ai-input-area(flex-shrink:0)  ← 底部输入区:固定在 TabBar 之上,预留安全区
        ├ .ai-input-wrap(.ai-input 输入框 + 消息图标)
        └ .ai-send(圆形发送按钮;有输入时 .active 金渐变)
```

**四个常用问题（文案固定，须真实可点击产生对话）**：`如何预约课程？` / `我的课卡还剩多少次？` / `如何取消或改约课程？` / `我最近预约了哪些课程？`。

**交互与状态（可执行）**：
- `aiAsk(text)`：注入用户消息 → `STATE.aiLoading=true`（渲染 `.ai-dots`）→ 650ms 后 `aiResolve()` 给出模拟回复。重复/空输入被忽略。
- `aiReplyFor(text)` 按关键词返回模拟答案，并**引用原型内真实演示数据**（如次卡 `CARDS` 剩余次数、`CANCEL_MINUTES` 取消时限、`BOOKINGS` 最近 3 条预约），不做真实网络请求。
- 错误态由输入以「错误/异常/error/报错」开头触发（演示用），渲染 `.ai-bubble.err` + `⚠️`。
- `aiClear()`：清空 `STATE.aiMsgs` 回到空状态欢迎语。
- `scrollAiBottom()`：每次渲染后把 `.ai-msgs` 滚动到底（保证最新消息可见）。
- 会话状态如实标注：`智能课程助手 · 模拟对话（未接入真实 AI）`。

**视觉变量（沿用香槟金，禁用蓝紫）**：机器人头像/发送激活态金渐变 `linear-gradient(135deg,#d4b896,#c9a66b)`；常用问题图标 `#c9a66b`；正文 `#3a2c1e`/次级 `#5a4a38`；欢迎徽标底 `rgba(201,166,107,.14)` 字 `#8b7355`；页面底渐变 `linear-gradient(180deg,#faf6f0 0%,#f5ede3 100%)`。
