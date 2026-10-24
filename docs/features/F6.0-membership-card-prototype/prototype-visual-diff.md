# 原型视觉差异报告（Prototype Visual Diff）

> 日期：2026-10-16（v8：D1/D3/D4/D5/D9 决策固化；v7：管理端按真实 admin-web 语义对齐）
> 对比对象：v1 初版（凭空设计，备份文件已删除；其偏差值已在本报告第一节表格内逐条留档）→ `prototype/index.html`（v8，按真实源码还原 + 结构/导航对齐 + AI 助手一级 Tab 改造 + 管理端对齐 + 决策固化）
> 基准依据：`ui-visual-spec.md`（第 1-5 节颜色/变量；**第 6 节结构规格** —— v3 新增，逐条带 `文件:行号`）
> 方法：v1 偏差值（见下表）与本报告逐类核对 + 真实源码行号回溯；不含主观"看起来像"的判断。
>
> **v8 起因**：D1/D3/D4/D5/D9 决策已由产品负责人确认（2026-10-16），原型的"决策占位"黄色便签需落地为确定性交互。本次将 D1/D3/D5/D9 便签改为绿色「已确认」、移除演示用 `conflictSim` 模拟开关并改由真实重叠期卡 C8 驱动、`addDays` 改 UTC 基准、`doBooking` 补 `schedId/cardId`。**仅改原型 + 文档，未改真实业务代码**；视觉差异项无新增（本次为逻辑/标注层变更，不改页面观感）。
>
> **v7 起因**：管理端 P-A1/P-A2/P-A3/P-A4 此前部分沿用旧构思，与真实 `apps/admin-web/src/views/card-types/index.vue`、`views/membership/index.vue` 的列/枚举/弹窗/详情页不一致。本次按真实页面语义对齐管理端原型（列/枚举/弹窗/详情页），**视觉差异项相应更新**（如管理端状态文案由"使用中/已用尽"改为"正常"等）。
>
> **v4 起因**：用户实测反馈「学员端小程序底部菜单是**首页、排期、我的**，原型不完全匹配」。复盘确认原型 TabBar 采用了**废弃组件 `StudentTabBar.vue`** 的旧结构（文案"预约"、emoji 图标、激活色 `#c9a66b`、无指示条），与真实 `HomeTabBar.vue` 不一致，且**缺首页/我的两页**。用户确认修复范围 = 「全量复刻真实结构」。
>
> **v5 起因**：产品需求《将学员小程序端 AI 助手改为一级 Tab 页面》。原型的 AI 助手此前**不存在**（真实端为 `AiAssistant.vue` 悬浮 FAB + 蓝紫弹窗），故本次为**新增**：底部导航由三 Tab 扩为**四 Tab（含 AI 助手）**，并新增独立完整聊天页 P-M10（香槟金主题）。**仅改原型，未改真实业务代码**；真实端后续需同步改造（见 `ui-visual-spec.md` §2.3 备注）。
>
> **v3 起因**：用户实测反馈「学员小程序原型与真实"我的"页面不符合」。复盘确认 v2 只做到了**视觉层（颜色/变量）**对齐，而 `ui-visual-spec.md` 当时**漏掉了 DOM 结构与交互模式**，导致原型骨架与真实页面不同 —— 属**结构级偏差**。用户经确认选择「全量结构对齐」+「严格复刻真实页面」。
>
> **v2→v3 更正（本报告第一、二节的行文按 v2 当时状态保留，其中列出的类名在 v3 已被替换为真实类名）**：
> - v2 自造类名 `.mbadge` / `.stu-bal` / `.stu-radio` / `.legend` 均非真实 miniapp 类名，v3 已改用真实源码类名：`card-status-badge`+`badge-dot`（卡状态）、`credits-display`+`credits-remaining`（余额）、`card-selector-popup`（选卡底部弹窗）、`filter-tabs`+`tab-active`（双胶囊 Tab）。
> - 该问题同时也是 v2 验证脚本的**盲区**（断言绑定了自造类名，对结构偏差不敏感，见 `prototype-validation-report.md` 第 12 行"验证盲区修正"）。

## 一、结构性差异（v1 视觉方向错误 → v2 已修正）

| # | 区域 | v1（错误） | v2（修正后） | 真实源码证据 | 状态 |
|---|------|-----------|-------------|-------------|------|
| 1 | admin 侧边栏底色 | `#f5f7fa` 浅色（v1 原值） | `#1a1a2e` 深色，宽 200px | `AdminLayout.vue` L19-L22 | 已对齐 |
| 2 | admin Logo 区 | 无 logo，仅文字分组 | 60px 高 logo 区：36px 紫渐变圆角图标（`linear-gradient(135deg,#667eea,#764ba2)`）+「约课管理」白字 15px/700 | `AdminLayout.vue` L189-L215 | 已对齐 |
| 3 | admin 菜单项 | 深色文字、无图标、无激活态 | 文字 `#a0a0b8`；激活态白字+`linear-gradient(90deg,rgba(102,126,234,.3),transparent)`+左侧 3px `#667eea` 边框；每项带 `.ni` 图标 | `AdminLayout.vue` L228-L231 | 已对齐 |
| 4 | admin 主按钮 | 纯色 `background:var(--blue)` | 渐变 `linear-gradient(135deg,#409eff,#3a8ee6)` + `box-shadow:0 2px 8px rgba(64,158,255,.3)`、无边框 | `styles/index.scss` L39-L57 | 已对齐 |
| 5 | admin 表格 | 无外边框、无表头底色、无斑马纹 | 外边框 `1px solid #ebeef5`+圆角 8px；表头 `#f5f7fa`/文字 `#303133`；`tbody tr:nth-child(even)` 斑马纹 `#fafafa` | `styles/index.scss` L79-L132 | 已对齐 |
| 6 | 学员端主色 | 微信绿 `#07c160`（v1 原值） | 香槟金 `#C9A66B`（含 `--gold-d:#B8956A`、`--gold-l:#DBC18A`、金色渐变） | `_variables.scss` L14-L16 | 已对齐 |
| 7 | 学员端页面底 | 纯灰 `#f5f7fa`（v1 原值） | `linear-gradient(180deg,#faf6f0 0%,#f5ede3 100%)` | `membership/index.vue` L984 | 已对齐 |
| 8 | 学员卡面 | 单一白卡（v1 原值） | 5 类状态变体：`.card-active`（金渐变 `#fdf6e9→#f0d9a8`+金边框）／`.card-pending`、`.card-used-up`（`#faf8f5→#f7f3ed`）／`.card-frozen`（蓝灰 `#f5f7fa→#eef1f5`）／`.card-expired`、`.card-voided`（灰+`opacity:.65`） | `membership/index.vue` L1051-L1083 | 已对齐 |
| 9 | 学员主按钮 | 微信绿实心（v1 原值） | 金渐变 `linear-gradient(135deg,#d4b896,#c9a66b)` + 金阴影；outline 金描边；新增 `.stu-mini-btn`（卡片内小按钮，金/红/灰三态） | `membership/index.vue` L1569-L1590 | 已对齐 |
| 10 | 状态徽标 | 复用后台 `badge()`（EP 四色） | 新增 `.mbadge`（圆点+浅底，6 态）与 `.mbk`（预约状态统一金色底+文案：待上课/上课中/已完成/已取消） | `membership/index.vue` L1119-L1210 | 已对齐 |
| 11 | 余额展示 | 纯文本「剩余 N/M 次」 | 金色大数字 `.stu-bal`（26px/700/`#c9a66b`；用尽转 `#ef5350`）+ `/ 总数` 小字 + 右侧「有效期至」（`.bal-row`） | `membership/index.vue` L1045-L1084（真实 56rpx） | 已对齐（等比缩放） |
| 12 | 教师端 | 桌面侧边栏 + `el-table` 表格（v1 原值） | 无侧边栏、移动风：紫渐变信息卡 `.tch-head` + 白卡统计栏 `.tch-stat`（已预约/已签到/未签到）+ 卡片列表 `.tch-row`（头像/姓名/卡号+状态/签到时间/操作） | `teacher-web/src/views/students/index.vue` L187、L212-L231 | 已对齐 |

## 二、受原型形态限制、未逐像素还原的部分（明确列出，不冒充一致）

| 项 | 真实表现 | 原型处理 | 原因 |
|---|---------|---------|------|
| 1 | 小程序原生导航栏（`navigationBarBackgroundColor:#ffffff`，标题「我的会员卡」） | 用原型顶部伪状态栏（9:41/5G）+ `.page-title` 标题替代 | 单文件 HTML 无法渲染小程序原生导航栏 |
| 2 | 底部 TabBar（`HomeTabBar.vue`，高 100rpx） | **v4 已按真实实现**（三 Tab「首页/排期/我的」+ 线性 SVG 图标 + 激活色 `#8b7355`/非激活 `#999` + `.tab-indicator` 指示条）；**v5 按产品需求扩为四 Tab「首页/排期/AI 助手/我的」**，AI 项复用真实 `ai-robot` 线性图标、样式与其余三项完全一致 → **此四 Tab 为原型有意超出真实端**（真实 `HomeTabBar.vue` 仍为三 Tab，尚未改造） | v3 曾用 emoji 图标（🏠📋👤）+ 金色激活色 + 旧文案，与真实不一致 |
| 3 | rpx 尺寸体系（20rpx 圆角、56rpx 数字） | 换算为 px（10px 圆角、26px 数字），手机框固定 375px | 原型为固定宽度预演，非自适应 |
| 4 | DIN 数字字体（卡面余额） | 系统字体栈 | 未内嵌字体文件 |
| 5 | admin 顶栏（折叠按钮/面包屑/头像下拉，60px） | 未渲染，仅保留侧边栏+内容区 | 原型聚焦会员卡链路，非全局布局 |
| 6 | 小程序「有效/无效」双 Tab 胶囊筛选（L999-L1027） | v2 用 `.legend` 徽标行替代；**v3 已按真实实现**：`.filter-tabs` 双胶囊 Tab（`tab-active` 金渐变）+ 计数文案「有效课卡 N / 无效课卡 N」 | v2 缺失真实结构，v3 补齐 |

## 三、仍沿用 Element Plus 风格的部分（有意，非缺陷）

- 教师端名单卡片内的预约状态/卡状态标签仍用 `.badge`（EP 四色）——`teacher-web` 为桌面 Web（Element Plus），**不应用小程序金色徽标**；仅在学员小程序面板使用 `card-status-badge`（圆点+浅底胶囊）/ 金色图标+文案的预约状态徽标。
- admin 面板全部标签/按钮/表格均按 EP 规范，未引入金色。

## 四、结构级差异（v2 视觉对齐但结构偏差 → v3 已修正）

> v2 只比对了"颜色/变量/外观"，**未比对 DOM 层级、字段顺序、交互模式**，因而下列偏差在 v2 未被发现。v3 依据 `ui-visual-spec.md` 第 6 节逐条修正：

| # | 区域 | v2（结构偏差） | v3（按真实复刻） | 真实源码证据 |
|---|------|--------------|----------------|-------------|
| 1 | P-M1 顶部 | 无筛选（用 `.legend` 徽标行说明） | `.filter-tabs` 双胶囊 Tab +「有效课卡 N / 无效课卡 N」计数 | `membership/index.vue` L4-L19 |
| 2 | P-M1 卡面头 | 名称 + `.mbadge` 标签并列 | `.card-header`（名称）+ `.card-status-badge`（`.badge-dot`+`.badge-text`） | `membership/index.vue` L82-L89 |
| 3 | P-M1 卡号行 | 无复制入口 | `.card-no-row`（`card-no-label`/`card-no-text`/`copy-icon-btn`）+ `.usage-divider-line` 竖线 | `membership/index.vue` L93-L106 |
| 4 | P-M1 余额 | `.stu-bal` 纯文本「剩余 N/M 次」 | `.credits-display`（`.credits-remaining` + `.credits-separator` + `.credits-total` + `.credits-unit`）同排 | `membership/index.vue` L109-L126 |
| 5 | P-M1 待激活 | 底部按钮 | **行内** `.usage-with-activate` + `.activate-btn-inline`「立即激活」；冲突时弹「无法激活」警告框 | `membership/index.vue` L286-L365、L844-L864 |
| 6 | P-M1 点击 | 点击卡片跳 P-M2 详情 | **卡片不可点击**（真实无此入口）；P-M2 改标「待新增 · 真实项目不存在」 | `membership/index.vue` 无卡片 click handler |
| 7 | P-M3 顶部 | 无筛选/无日期 | `.filter-scroll`（`.filter-pill` 分类）+ `.date-scroll`（`.date-pill` 日期，含 `pill-day-name`/`pill-day-date`） | `schedule/index.vue` L2-L140 |
| 8 | P-M3 排期卡 | 左侧通栏色带 + 横线分隔 | **两栏**：`.schedule-time-section`（50px 圆角小方块，`time-start`/`time-divider` **竖线** `/time-end`）+ `.schedule-content` | `schedule/index.vue` L1087-L1148 |
| 9 | P-M3 容量 | 「剩余 N 个名额」 | `.capacity-text` 口径 `{booked}/{capacity}人` | `schedule/index.vue` L107-L109 |
| 10 | P-M3 按钮 | 文案近似 | `.book-btn` 状态类 `booked`/`disabled`/`no-card`/`not-applicable`/`insufficient`/`weekly-limit` + `.cancel-hint` 取消时限 | `schedule/index.vue` L114-L128 |
| 11 | P-M4 选卡 | 内联 `.stu-radio` 列表 | **底部弹窗** `.card-selector-popup`（标题「选择会员卡」/×/卡选项/确定） | `booking-confirm/index.vue` L158-L230 |
| 12 | P-M6 Tab | 缺筛选 | 四 Tab「全部/待上课/上课中/已完成」+「开课前 90 分钟内不可取消」 | `bookings/index.vue` L127-L155、L138/L164-L166 |
| 13 | 待新增页 | 与真实页无区分 | P-M2/P-M5/P-A5 加「待新增 · 真实项目不存在」标注（`.pending-banner`）并灰置入口 | `existing-page-mapping.md` 第 4 类 |

## 五、底部导航级差异（v3 → v4 已修正）

> v3 已完成 P-M1/M3/M4/M6 的结构对齐，但**底部 TabBar 仍沿用废弃组件 `StudentTabBar.vue` 的旧结构**，且缺「首页/我的」两页 —— 这些偏差在 v3 未被 [G] 组断言覆盖。v4 依据真实 `components/HomeTabBar.vue` + `pages/student/courses|profile/index.vue` 逐条修正：

| # | 区域 | v3（偏差） | v4（按真实复刻） | 真实源码证据 |
|---|------|-----------|----------------|-------------|
| 1 | TabBar 组件来源 | 依据 `StudentTabBar.vue`（**实际无任何页面引用的废弃文件**） | 改依据 `HomeTabBar.vue`（真实页面唯一引用） | Grep：`courses/schedule/profile` 均 `import HomeTabBar` |
| 2 | TabBar 文案 | 「预约」（旧） | 「**首页 / 排期 / 我的**」 | `HomeTabBar.vue` tabs 定义 |
| 3 | TabBar 图标 | emoji（🏠📋👤） | 真实**线性 SVG**：`tab-home`/`tab-booking`/`tab-profile` | `static/icons/icon-map.ts` |
| 4 | TabBar 激活色 | 主色金 `#c9a66b` | **`#8b7355`（棕）**；非激活 `#999` | `HomeTabBar.vue` `.tab-text.active` |
| 5 | TabBar 指示条 | 无 | `.tab-indicator`（`linear-gradient(90deg,#c9a66b,#d9a7b0)`，仅激活项） | `HomeTabBar.vue` |
| 6 | TabBar 显示范围 | 全页显示 | **仅 P-M8/P-M3/P-M9 显示**；P-M1/P-M6 等 pushed 页 `hidden` | 真实仅三页挂 `HomeTabBar` |
| 7 | 首页页 | **缺失** | 新增 **P-M8**（navbar 地点+Banner+师资+推荐课程+视频） | `courses/index.vue` L2-L206 |
| 8 | 我的页 | **缺失**（仅会员卡列表） | 新增 **P-M9**（navbar 我的+个人信息+我的会员卡→membership+预约记录→bookings） | `profile/index.vue` L2-L118 |
| 9 | 默认进入页 | P-M1 会员卡 | **P-M8 首页**（真实首屏） | `pages.json` 首页路由 |
| 10 | pushed 页返回 | 无返回入口 | `.stu-backbar` 返回条（→「我的」），对应真实 native 返回 | `pages.json` `navigationBarTitleText` 默认带返回 |

## 六、AI 助手一级 Tab 级差异（v4 → v5 已新增）

> v5 为产品需求新增项（非"修正历史偏差"）：真实端 AI 现为悬浮弹窗，原型按需求将其升级为一级 Tab 页。

| # | 区域 | v4（旧） | v5（本次） | 依据 |
|---|------|---------|-----------|------|
| 1 | 底部 Tab 数量 | 三 Tab（无 AI） | **四 Tab「首页 / 排期 / AI 助手 / 我的」**，AI 位介于「排期」与「我的」之间 | 产品需求 |
| 2 | AI 助手形态 | 原型无此页 | **独立一级页 P-M10**（非悬浮按钮/底部弹窗/侧边抽屉/内嵌小窗） | 产品需求 |
| 3 | AI 页配色 | —（真实端为蓝紫 `#667eea→#764ba2`） | **沿用香槟金**（机器人头像/发送激活 `linear-gradient(135deg,#d4b896,#c9a66b)`；图标 `#c9a66b`），**不采用蓝紫** | 用户明确指令 |
| 4 | AI 页布局 | — | 三步式：顶部(标题「AI 助手」+ 会话状态) / 对话区(占主要空间、独立滚动) / 底部固定输入区(输入框+发送+安全区) | 产品需求 |
| 5 | 常用问题 | — | 4 项固定文案（如何预约课程？/ 我的课卡还剩多少次？/ 如何取消或改约课程？/ 我最近预约了哪些课程？），**点击真实产生对话**（非装饰按钮） | 产品需求 |
| 6 | 状态覆盖 | — | 空态(欢迎语) / 用户消息 / AI 回复 / 加载中(`.ai-dots`) / 错误态(`.ai-bubble.err` + ⚠️) | 产品需求 |
| 7 | 真实接入声明 | — | 顶部**如实标注「模拟对话（未接入真实 AI）」**，不伪造已接入 | 用户明确指令 |
| 8 | 业务回归 | — | 首页/排期/我的/会员卡/预约流程**均未改动**（仍可切换、TabBar 显隐规则不变） | 项目约定 |

## 七、管理端页面对齐级差异（v5 → v7 已修正）

> 管理端（admin-web）此前 P-A1/P-A2/P-A3/P-A4 部分沿用旧构思，未按真实页面语义核对；v7 依据 `views/card-types/index.vue`、`views/membership/index.vue` 逐条对齐：

| # | 区域 | v5（旧） | v7（按真实复刻） | 真实源码证据 |
|---|------|---------|----------------|-------------|
| 1 | P-A1 工具栏 | 含"回收站/恢复"等旧构思 | 仅「新增」「批量删除」 | card-types/index.vue L6-15 |
| 2 | P-A1 新建/编辑弹窗字段 | 含「每周使用上限」「状态」 | 产品名称 / 计费方式(仅次卡·期卡) / 包含次数 / 有效天数 / 价格(元) / 适用课程类型 / 描述 | card-types/index.vue L118-162 |
| 3 | P-A1 计费方式 tag | 未区分页面，沿用会员卡端口径 | `count=success / period=warning / unlimited=info` | card-types/index.vue L276-280 |
| 4 | P-A1 适用课程类型 tag | 未明确 | `regular=primary / private=warning / special=success`，空"不限"`#909399` | card-types/index.vue L57-66、L295-302 |
| 5 | P-A1 行内操作 | 含"回收站/恢复" | 编辑 / 下架·上架 / 删除（仅"下架"态） | card-types/index.vue L74-97 |
| 6 | P-A2 工具栏 | — | 「发放会员卡」「批量作废」 | membership/index.vue L6-14 |
| 7 | P-A2 状态文案 | 学员端口径"使用中/已用尽" | 管理端口径「未激活(info)/正常(success)/已过期(warning)/已冻结(danger)/已作废(info)」 | membership/index.vue L1074-1094 |
| 8 | P-A2 计费方式 tag | 沿用学员端浅渐变徽标口径 | `count=primary / period=success / unlimited=warning` | membership/index.vue L1101-1109 |
| 9 | P-A2 筛选 | — | 搜索框(240px)+状态多选（未激活/正常/已过期/已冻结/已作废） | membership/index.vue L18-48 |
| 10 | P-A2 行内操作 | 含"延期"等旧构思 | 激活 / 冻结 / 强制解冻·提前解冻 / 作废 | membership/index.vue L156-192 |
| 11 | 新增弹窗 | 无 | 冻结 / 批量作废 / 续卡提示 / 冻结到期-课程冲突 | membership/index.vue L363-566 |
| 12 | P-A3 发放弹窗 | 含「允许同产品重复发卡」开关 | 对齐真实字段（学员/产品/只读次数·天数/无限卡 tag/生效时间/备注），删除该开关 | membership/index.vue L214-292 |
| 13 | P-A4 详情 | 自造详情布局 | `el-descriptions :column="2" border` 两列网格；流水标为"原型扩展" | membership/index.vue L299-361 |

## 八、结论

- v1 的 3 处"方向性错误"（admin 侧边栏、小程序主色、教师端形态）已在 v2 全部修正，且每处均可回溯到真实源码行号。
- v2 的视觉基准来自 `ui-visual-spec.md`，新增的 CSS 类均有对应真实实现。
- **v3 补齐 v2 遗漏的结构层**：第四节列出的 13 处 DOM/交互偏差已按 `ui-visual-spec.md` 第 6 节（带 `文件:行号` 证据）逐条修正，并新增 [G] 结构对齐断言组（15 条）纳入脚本验证。
- **v4 补齐 v3 遗漏的底部导航层**：第五节列出的 10 处 TabBar/页面偏差已按 `HomeTabBar.vue` 与 `courses|profile/index.vue` 修正（新增 P-M8/P-M9 两页），并新增 [H] 断言组（12 条）。
- **v5 为产品需求新增 AI 助手一级 Tab**：第六节列出 8 项改动（新增 P-M10 聊天页 + TabBar 扩为四 Tab），并新增 [I] 断言组（21 条）；断言总数 60 → **81**（全部 PASS / EXIT=0）。
- **v8 决策固化（逻辑/标注层，不改页面观感）**：D1/D3/D5/D9 便签由黄色「决策占位」转绿色「已确认」；移除演示用 `conflictSim` 模拟开关，改由真实重叠期卡 C8 驱动区间重叠拦截；`addDays` 改 UTC 基准；`doBooking` 补 `schedId/cardId` 使 P-M5 渲染真实结果。新增 [J] 断言组（8 条）；断言总数 → **121**（[A]–[I]/[K] 113 条无回归，全部 PASS / EXIT=0）。本节无新增视觉差异项。
- **v7 按真实 admin-web 对齐管理端**：第七节列出 13 处 P-A1/P-A2/P-A3/P-A4 的列/枚举/弹窗/详情页对齐（含管理端状态文案由"使用中/已用尽"改为"正常"等），并新增 [K] 断言组（32 条）；断言总数 → **113**（[A]–[I] 81 条无回归，全部 PASS / EXIT=0）。
- 未还原项已在上表（第二节）逐条声明，**不以"外观相似"冒充一致**；**也未以"颜色对了"冒充结构一致**；AI 助手明确标注"未接入真实 AI"，**不伪造已接入**。
