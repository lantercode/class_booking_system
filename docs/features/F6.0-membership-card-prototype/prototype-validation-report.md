# 原型验证报告（Prototype Validation Report）

> 日期：2026-10-19（v10：管理端侧栏图标与按钮风格对齐真实 admin-web；v9：D10 原型演示态补录；v8：D1/D3/D4/D5/D9 决策固化落地；v7：管理端按真实 admin-web 重做）
> 交付物：`prototype/index.html`（单文件 HTML，纯 vanilla JS，零外部依赖）
> 验证方式：**脚本化无头执行**，非静态截图、非"改完即通过"。
> 验证脚本：`verify-prototype.js`（已固化至本目录；提取内嵌 `<script>` 后 `new Function` 语法检查 + DOM stub 下逐流程执行断言）
>
> **v10 变更说明（2026-10-19，管理端侧栏图标 + 按钮风格对齐真实 admin-web）**：
> - 起因：产品要求 F6.0/F7.0 管理端原型的**左侧菜单图标与真实页面一致**，并**核对其按钮风格是否与实际真实页面一致**。
> - 图标：真实 admin-web 侧栏（`AdminLayout.vue`）用 `@element-plus/icons-vue` 图标组件，原型原用 emoji。本次新增 `ICON` 表 + `iconSvg(key)`，对菜单项内联**同源 Element Plus SVG path**（卡产品管理=`Collection`、会员卡管理=`CreditCard`、排期签到点名=`Calendar`、预约管理=`Ticket`、发卡弹窗=`CirclePlus`、卡详情流水=`Tickets`），替换原 emoji；「弹窗/详情」组同理使用 SVG 图标。logo 的 `✓` 符号**保留未改**（非菜单图标，最小改动）。
> - 按钮：核对真实 `apps/admin-web/src/styles/index.scss` —— `.btn-primary:hover` 补真实阴影+位移、新增 `.btn-primary:active` 复位；`.btn-danger` 由实心 `var(--red)` 改为真实**红色渐变**（`linear-gradient(135deg,#f56c6c,#e04040)`）+ 阴影 + hover 位移/透明度，与真实 `.el-button--danger` 一致。
> - 验证：**128 / 128 全部通过（退出码 0）**，原有 [A]–[L] 组**无回归**。
>
> **v9 变更说明（2026-10-19，D10 跨排期时间段冲突演示态）**：
> - 起因：F6.0 原型核查发现真实后端 `create_booking` 缺「跨排期时间段重叠」校验（立项为 **D10**）；本次**仅在原型补演示态**，后端未实现。
> - 原型：新增 `scheduleTimeConflict`（跨排期时间段重叠判断，与 D9 卡有效期重叠解耦）+ `submitBooking` 确认阶段拦截；新增演示排期 **S6**（10-10 19:30-20:30，与 S1 张小明已约时段重叠）。
> - 验证：新增 **[L] 跨排期时间段重叠冲突** 断言组（7 条）；断言总数 **121 → 128**；**原有 [A]–[K] 组 121 条无回归**。
> - 文档：新增 `D10-booking-time-conflict-validation.md` 立项文档；`open-decisions.md` D10 状态更新为「已立项 · 待开发」。
>
> **v8 变更说明（D1/D3/D4/D5/D9 决策固化）**：
> - 起因：产品负责人已确认 D1（扣次时机=预约预扣+排期 COMPLETED 确认）/ D3（失效替代=提示+换卡+人工）/ D4（有效期边界）/ D5（缺席自动消解）/ D9（期卡首发 PENDING，首次排期 COMPLETED 激活 + 预期有效期重叠预校验），需将原型对应"决策占位"便签落地为确定性交互。
> - 原型：D1/D3/D5/D9 便签由黄色「决策占位」改为绿色「已确认」（`confirmedNote`）；移除演示用 `conflictSim` 模拟开关，改由**真实演示重叠期卡 C8**（ACTIVE 期卡，与 C1 同产品 P2）驱动区间重叠拦截；`addDays` 改用 **UTC 基准**（修复本地时区导致的日期偏移，如 10-10+30 天应为 11-09）；`doBooking` 补 `schedId/cardId` 使 P-M5 结果页渲染真实预约结果（此前为空态）。
> - 文档：`open-decisions.md` 补确认日期（2026-10-16）与状态说明；`business-rules.md` 将 D1/D3/D4/D5/D9 迁入「一、已固化」并新增 **R-B7（期卡生命周期与预约校验）/ R-B8（卡失效替代策略）**、修订 R-B4；`interaction-spec.md` 状态说明同步。
> - 新增 **[J] 决策固化** 断言组（8 条）；断言总数 → **121**；**原有 [A]–[I]/[K] 组 113 条无回归**。
>
> **v7 变更说明（管理端按真实 admin-web 重做）**：
> - 起因：P-A1/P-A2/P-A3/P-A4 此前部分描述与真实 `apps/admin-web/src/views/card-types/index.vue`、`views/membership/index.vue` 的列/枚举/弹窗/详情页不一致；本次按真实页面重做管理端原型并同步文档。
> - P-A1 卡产品管理：工具栏「新增」「批量删除」；列 = 复选框·序号·产品名称·计费方式·包含次数·有效天数·价格(元)·适用课程类型·状态·操作；计费方式 `count=次卡(success)/period=期卡(warning)/unlimited=无限卡(info)`；适用课程类型 `regular=常规课(primary)/private=私教课(warning)/special=特色课(success)`（空值"不限"#909399）；行内操作 编辑/下架·上架/删除（仅"下架"态）；移除「每周使用上限」「状态」表单字段与「回收站」按钮（降级为"原型扩展"标注）。
> - P-A2 会员卡管理：工具栏「发放会员卡」「批量作废」；筛选 搜索框（placeholder"搜索学员或手机号"）+ 状态多选（未激活/正常/已过期/已冻结/已作废）；列 = 复选框·序号·会员卡号(可点击开详情)·产品名称·计费方式·学员·手机号·总次数·已用·剩余·状态·有效期·冻结信息·操作；管理端状态文案/色 = 未激活(info)/正常(success)/已过期(warning)/已冻结(danger)/已作废(info)（**与学员端"使用中/已用尽"刻意区分**）；冻结信息列仅存在冻结卡时显示「剩余 X 天解冻」。
> - 新增 4 个弹窗：冻结、批量作废、续卡提示、冻结到期-课程冲突（详见 `interaction-spec.md` P-A2）。
> - P-A3 发放弹窗：字段对齐（学员/产品/只读总次数·有效天数/无限卡 tag/生效时间/备注）；删除原「允许同产品重复发卡」复选框（改由续卡提示弹窗 409 驱动）。
> - P-A4 卡详情：改为 `el-descriptions` 两列 border 网格；保留使用流水表但标注为「原型扩展 · 真实详情弹窗不含流水（真实有 getTransactions 端点未接入）」。
> - 新增 **[K] 管理端结构对齐** 断言组（32 条）；断言总数 → **113**；**原有 [A]–[I] 组 81 条无回归**。
>
> **v5 变更说明（对应 AI 助手一级 Tab 改造）**：
> - 需求：《将学员小程序端 AI 助手改为一级 Tab 页面》。原型此前**无 AI 助手页**（真实端为 `components/AiAssistant.vue` 悬浮 FAB + 蓝紫弹窗），故本次为**新增**而非迁移。
> - 改动：底部导航由三 Tab 扩为**四 Tab「首页 / 排期 / AI 助手 / 我的」**（AI 项复用真实 `ai-robot` 线性图标，样式一致）；新增独立完整聊天页 **P-M10**（香槟金主题，非悬浮/弹窗/抽屉/内嵌小窗）；常用问题点击**真实产生模拟对话**；**如实标注"未接入真实 AI"，不伪造接入**。
> - 新增 **[I] AI 助手一级 Tab 页** 断言组（21 条），并将 [H] 组由三 Tab 改写为四 Tab 期望；断言总数 60 → **81**。
> - **仅改原型，未改真实业务代码**（首页/排期/我的/会员卡/预约流程未动）。
>
> **v4 变更说明（对应底部导航偏差修复）**：
> - 起因：用户实测反馈「学员端小程序原型底部菜单是**首页、排期、我的**，目前不是完全匹配的」。根因是原型 TabBar 用了废弃组件 `StudentTabBar.vue` 的旧结构（文案"预约"、emoji 图标、激活色主色金 `#c9a66b`、无指示条），且**缺首页/我的两页**。
> - 修复：以真实 `components/HomeTabBar.vue`（primary source；`StudentTabBar.vue` 经 Grep 确认**无任何页面引用**）为唯一 ground truth 重做 TabBar；新增 **P-M8 首页**（`pages/student/courses/index.vue`）与 **P-M9 我的**（`pages/student/profile/index.vue`）两页；TabBar **仅在三页显示**，pushed 页改用返回条回到「我的」。
> - 新增 **[H] 底部导航 + 首页/我的** 断言组（12 条），断言总数 48 → **60**。
>
> **v3 变更说明（对应结构级偏差修复）**：
> - 起因：用户实测反馈「学员小程序原型与真实"我的"页面不符合」。根因是 `ui-visual-spec.md` 只提取了颜色/变量，**漏了 DOM 结构与交互模式**。
> - 修复：先补齐 `ui-visual-spec.md` **第 6 节「结构规格（DOM 层级/字段顺序/交互模式）」**（逐条带 `文件:行号` 证据，作为唯一 ground truth），再按节重做 P-M1/P-M3/P-M4/P-M6 的 DOM。
> - 原型定位经用户确认 = **严格复刻真实页面**：真实不存在的页面一律加「待新增 · 真实项目不存在」标注并灰置入口。
> - **验证盲区修正**：v2 脚本中的 A4/A6/B2/F1 等断言绑定了 v1 自造的类名（`mbadge`/`stu-bal`/`stu-radio`），因而**对结构偏差完全不敏感**——它们持续 PASS，却无法发现原型骨架与真实页面不同（"假通过"）。v3 已把这些断言改绑真实源码中的类名，并新增 **[G] 结构对齐** 断言组，使结构偏差可被脚本捕获。

## 一、验证证据（实际执行输出）

执行命令：

```
# 在 F6.0 目录下执行(默认验证 prototype/index.html)
node verify-prototype.js
```

结果：**PASS 128 / FAIL 0**（`[1] SYNTAX OK`，退出码 0，可直接接入 CI）

| 分组 | 断言数 | 结果 | 覆盖内容 |
|------|-------|------|---------|
| [1] 语法 | 1 | OK | `<script>` 整体可被 JS 引擎解析 |
| [A] 跨端预约 | 6 | 全通过 | admin 侧边栏 logo/图标、会员卡列表渲染、miniapp 圆点徽标 `card-status-badge`、C2 初始剩余=7、金色大数字 `credits-display` |
| [B] 多卡切换+次卡预扣 | 9 | 全通过 | 进入 P-M4、选卡为**底部弹窗**(非内联 radio)、二次确认弹窗、`remaining 7→6`、`used 3→4`、CONSUME 流水、新增 BOOKED、跳 P-M5、PENDING 期卡可选 |
| [C] 取消回补 | 4 | 全通过 | 回补预览 `+1`、B1→CANCELLED、`remaining 7→8`、RESTORE 流水 |
| [D] 签到完成+拦截 | 6 | 全通过 | 教师端移动风卡片、已弃用 `el-table`、签到成功、重复签到被拒、COMPLETED、**计划卡已作废签到被拦截(D9)** |
| [E] 计划卡已作废警示 | 3 | 全通过 | 「计划卡已作废」警示条、换卡占位+联系机构、警示条加「待新增」标注 |
| [F] 失效徽标 | 5 | 全通过 | 有效 Tab 四类徽标 / 无效 Tab 两类徽标（**已作废卡在无效 Tab 可见**）、用尽样例、admin D3 占位、表格斑马纹 |
| [G] 结构对齐（v3 新增） | 15 | 全通过 | P-M1 双胶囊 Tab + 复制图标 + 竖线 + `remaining/total次` 同排 + 行内「立即激活」+ **卡片不可点击**；P-M3 分类筛选栏 + 日期栏 + 左时间竖排区/右内容区两栏 + 容量口径 `booked/capacity 人` + 已约按钮 `booked` 态与取消时限；P-M4 底部弹窗（标题/选项/确定）；P-M6 四筛选 Tab + 「开课前 90 分钟内不可取消」；P-M2/P-M5/P-A5「待新增 · 真实项目不存在」标注与入口灰置 |
| **[H] 底部导航 + 首页/我的**（v4 新增；v5 改为四 Tab 期望） | 12 | 全通过 | TabBar **四 Tab 文案 `首页/排期/AI 助手/我的`+顺序**、激活态色 `#8b7355`+`.tab-indicator`、**真实线性 SVG 图标**（path/circle）、仅四页显示（pushed 页 `hidden`）、Tab 点击切页与激活态转移；P-M8 首页（navbar 地点+Banner+师资+推荐课程+视频+「全部课程」入口）；P-M9 我的（navbar+个人信息+「我的会员卡」→P-M1+「预约记录」→P-M6）；pushed 页 `.stu-backbar` 返回条 |
| **[I] AI 助手一级 Tab 页**（v5 新增） | 21 | 全通过 | 顶部(标题「AI 助手」+会话状态)、**如实标注"模拟对话（未接入真实 AI）"**、独立滚动对话区+底部固定输入区、内容区 `ai-mode`、空态欢迎语+**4 个常用问题**（文案逐条校验）、**常用问题点击真实产生对话**、加载中 `.ai-dots`、模拟回复引用真实卡余额/取消时限/预约记录、错误态 `.ai-bubble.err`+⚠️、输入发送显示用户消息、多轮消息累积、清空回空态、**四 Tab 间切换高亮正确**、pushed 页仍不显示 TabBar |
| **[J] 决策固化**（v8 新增） | 8 | 全通过 | 源码不再含 `conflictSim` 模拟开关；P-M4 D9 便签为绿色「已确认」(`cnote`)且无模拟复选框；演示重叠期卡 **C8**(ACTIVE 期卡, 同产品 P2)；P-M4 期卡 C1 因预期有效期与 C8 重叠被拦截(`card-disabled`+「有效期重叠」)；`addDays` UTC 基准校验(10-10+30=11-09)；P-A2 D3 便签为绿色「已确认」；预约成功后 P-M5 渲染真实结果(补 `schedId/cardId`, 非空态)；未确认决策 D2 仍保留黄色「决策占位」 |
| **[K] 管理端结构对齐**（v7 新增） | 32 | 全通过 | P-A1 工具栏「新增/批量删除」、表头列与真实对齐、计费方式 tag `count=success/period=warning`、无限卡 `info`、适用课程类型 tag（常规 primary/私教 warning/特色 success、空"不限"）、行内 编辑/下架·上架/删除(仅下架)、新建弹窗字段(且删「每周使用上限」「状态」)、批量删除弹窗文案；P-A2 工具栏「发放会员卡/批量作废」、搜索框 placeholder、状态多选、表头列对齐、状态徽标「正常」(区别于学员端)、冻结信息列「剩余 X 天解冻」+冲突标记、计费方式 tag `count=primary/period=success`、无限卡 `warning`、行内 激活/冻结/强制解冻；冻结弹窗、详情弹窗 `el-descriptions`(desc-grid)字段完整+流水原型扩展标注、冻结卡追加字段、作废弹窗、批量作废弹窗、发放弹窗(P-A3)字段+删除「允许同产品重复发卡」、续卡提示弹窗、冻结到期-课程冲突弹窗 |
| **[L] 跨排期时间段重叠冲突**（v9 新增，D10） | 7 | 全通过 | 目标排期 S6(19:30-20:30) 与学员已约 B1 所在排期 S1(19:00-20:30) 时间重叠→确认阶段被拦截(不弹二次确认)、拦截文案含冲突课程名与两个时间段、无副作用(未生成预约/未扣次)；非冲突排期仍可正常二次确认并预约成功；**与 D9 卡有效期重叠解耦**(C1 于 S1 仍按卡冲突拦截、S6 不含卡冲突提示) |

> 该脚本通过真实调用页面内函数（`resetData / goStu / stuTab / selectSched / pickBookCard / submitBooking / doBooking / openCancelModal / doCancel / tchCheckIn / tchComplete / renderTeacher`）并断言数据副作用（卡余额、流水类型、预约状态、TabBar 显隐类）与 DOM 结构标记，因此验证的是**行为 + 结构**而非文本。**原有 [A]–[I] 组 81 条断言无回归**（v7 新增 [K] 组 32 条；v8 新增 [J] 组 8 条；v9 新增 [L] 组 7 条，合计 128）。

## 二、复用了哪些真实页面

以下页面的**结构、字段、文案、交互**均来自真实源码（逐文件阅读，见 `existing-page-mapping.md`），原型为"复现/升级"，不是新设计：

| 原型页面 | 真实来源 | 复用内容 |
|---------|---------|---------|
| P-A1 卡产品管理 | `apps/admin-web/src/views/card-types/index.vue` `/card-types` | 列清单、计费方式标签、上下架/编辑/删除 |
| P-A2 会员卡管理列表 | `apps/admin-web/src/views/membership/index.vue` `/membership` | 列清单（卡号/产品/计费/学员/次数/状态/有效期/冻结信息）、搜索+状态筛选、批量作废 |
| P-A3 发卡弹窗 | 同上（发放 dialog L207-L297） | 学员远程搜索+产品联动+生效日期+续卡冲突 409 处理 |
| P-A4 卡详情弹窗（升级） | 同上（详情 dialog L299-L361） | 基本信息 descriptions + **新增流水区块**（`GET /membership/transactions`） |
| **P-M8 首页·课程列表**（v4 新增） | `apps/miniapp/src/pages/student/courses/index.vue` | **navbar 地点选择器、Banner 轮播（overlay+标题/副标题+dots）、师资团队横滑、推荐课程（image+name+desc+「全部课程」入口）、舞蹈视频（cover+play+duration）** |
| **P-M9 我的·个人中心**（v4 新增） | `apps/miniapp/src/pages/student/profile/index.vue` | **navbar「我的」、个人信息区（头像占位/昵称/角色·手机号/crown 会员徽章）、「我的会员卡」入口卡（→membership）、「预约记录」菜单（→bookings）、解绑微信/退出登录** |
| **底部 TabBar**（v4 重做；v5 扩为四 Tab） | `apps/miniapp/src/components/HomeTabBar.vue` + `static/icons/icon-map.ts` | **`tab-home/tab-booking/tab-profile` 线性 SVG、激活色 `#8b7355`/非激活 `#999`、`.tab-indicator` 指示条、样式与显隐规则**；**v5 按产品需求新增第 4 个「AI 助手」Tab**（复用真实 `ai-robot` 图标，样式一致）——**此四 Tab 为原型有意超出真实端**（真实 `HomeTabBar.vue` 仍为三 Tab，尚未改造） |
| **P-M10 AI 助手**（v5 新增） | `apps/miniapp/src/components/AiAssistant.vue`（结构参考）+ `static/icons/icon-map.ts` | **欢迎区（badge「您可以问我：」+快捷卡）、用户/AI 消息气泡、加载中三点、底部输入区（输入框+发送）等结构**；图标取真实 `ai-robot/message/send/lightbulb/calendar/edit/clipboard`；**但升级为一级整页**且**配色改为香槟金**（真实为蓝紫 `#667eea→#764ba2` 弹窗），属**有意差异**（用户明确指令） |
| P-M1 我的会员卡 | `apps/miniapp/src/pages/student/membership/index.vue` | **双胶囊 Tab（有效/无效课卡+计数）、卡面头（名称+圆点徽标 `card-status-badge`）、卡号行（复制图标+竖线）、余额 `.credits-display`（remaining/total 同排）、待激活行内「立即激活」+冲突警告框、卡片不可点击** |
| P-M3 课程排期 | `apps/miniapp/src/pages/student/schedule/index.vue` | **分类筛选栏 + 日期栏、两栏排期卡（左时间竖排区/右内容区）、容量口径 `{booked}/{capacity}人`、预约按钮状态类（booked/disabled/no-card/not-applicable/insufficient/weekly-limit）+ 取消时限** |
| P-M4 预约确认 | `apps/miniapp/src/pages/student/booking-confirm/index.vue` | 课程信息卡+选卡区+注意事项+**底部弹窗选卡（非内联列表）**+确认/取消栏 |
| P-M6 我的预约 | `apps/miniapp/src/pages/student/bookings/index.vue` | 筛选 Tab、预约卡片、取消按钮与开课前 X 分钟限制、状态徽标 |
| P-T1 学员列表/签到 | `apps/teacher-web/src/views/students/index.vue` `/students/:scheduleId` | 排期信息卡+统计栏+学员卡片列表+签到按钮（`bookingApi.checkIn`） |

## 三、哪些部分只是视觉模拟（非真实能力）

| 项 | 说明 |
|---|------|
| 所有数据 | 内存 mock（`BASE_CARDS/BASE_TXNS/BASE_BOOKINGS/S1_ROSTER` 等常量），不连后端、不发 HTTP |
| 「激活/解冻/签到/完成/预约/取消」 | 仅改内存状态 + `toast`，不调用任何 API |
| 小程序原生导航栏 | 用伪状态栏 + 标题栏模拟，非真实小程序渲染；pushed 页返回用 `.stu-backbar` 复现（真实为原生返回） |
| rpx→px | 尺寸已等比换算，非真实 rpx 体系 |
| TabBar 图标 | **已换为真实线性 SVG**（从 `static/icons/icon-map.ts` 复刻，非 emoji）；但图标/封面图仍为内联 SVG/CSS 渐变，非真实图片资源 |
| **AI 助手对话（P-M10）** | **纯本地模拟**：关键词匹配 `aiReplyFor` + 650ms 延时，**不调用任何 AI 接口**；顶部已如实标注「模拟对话（未接入真实 AI）」，**不伪造真实接入** |
| 未复刻的真实页 | 首页「全部课程/课程详情」「视频播放」「解绑微信/退出登录」真实存在，原型以 `toast` 占位提示，未做完整页面 |
| 无头验证 | 通过 DOM stub 断言数据副作用与结构标记，**未做真实浏览器渲染截图**（无浏览器依赖，属环境限制，已显式声明） |

## 四、哪些页面仍需新增（现状后端/前端均不存在）

来自 `existing-page-mapping.md` 第 4 类，原型中以**构思稿**呈现、非复用现有页面：

| 页面 | 现状 | 原型处理 |
|------|------|---------|
| P-A5 预约管理列表 | admin 路由全量核对**无任何预约管理页** | 原型内新增该页（含"计划卡失效"警示条 + D3 占位） |
| P-M2 卡详情+使用记录 | miniapp 无卡详情页/无流水 UI | 原型内新增，标「**待新增 · 真实项目不存在**」；**无入口**（真实页面 M1 卡片不可点击，v3 已移除卡片点击跳转，仅保留按需预览控件） |
| P-M5 预约结果页 | 真实仅 `uni.showToast('预约成功')` 后返回，无结果页 | 原型内新增结果页 |
| 核销记录查询 | 全端无查询界面 | admin 挂 P-A4 流水区块；学员侧挂 P-M2 使用记录 |
| P-A6 排期签到点名(admin) | admin 无此页 | 原型内新增，与教师端签到共享数据 |

> 缺口项：P-A4 卡详情弹窗真实只有静态 `el-descriptions`、**无流水区**（`existing-page-mapping.md` 第 3 类），原型已补流水区块。

## 五、哪些流程已经打通（脚本可复现）

| 流程 | 脚本断言 | 状态 |
|------|---------|------|
| A 跨端预约（admin 查看 → miniapp 我的卡 → 排期 → 选卡 → 结果） | A1-A6 | 已打通 |
| B 多卡切换 / PENDING 期卡可选 / 次卡预扣 | B1-B9 | 已打通 |
| C 取消回补（预览 +1 → 确认 → 余额 +1 → RESTORE 流水） | C1-C4 | 已打通 |
| D 签到/完成/重复拒绝 + **计划卡非 ACTIVE 签到拦截(D9)** | D1-D6 | 已打通 |
| E 计划卡已作废 → 三层兜底（换卡占位/联系机构/提示） | E1-E3 | 已打通 |
| F 失效徽标（用尽/过期/冻结/作废）+ admin 作废影响面占位 | F1-F5 | 已打通 |
| G 结构对齐（P-M1/M3/M4/M6 DOM 与真实页面同构） | G1-G15 | 已打通 |
| H 底部导航（**四 Tab 首页/排期/AI 助手/我的** 切页+显隐范围）+ 首页/我的两页与「我的→会员卡/预约记录」跳转 | H1-H12 | 已打通 |
| I AI 助手一级 Tab 页（空态/常用问题→模拟对话/加载中/错误态/输入发送/多轮滚动/清空 + 四 Tab 切换高亮） | I1-I21 | 已打通（模拟对话，未接真实 AI） |
| J 决策固化（D1/D3/D4/D5/D9：便签转绿 + 去 conflictSim + C8 重叠卡 + addDays UTC + doBooking 补字段） | J1–J8 | 已打通 |
| K 管理端结构对齐（P-A1 卡产品 / P-A2 会员卡 / P-A3 发放 / P-A4 详情 对齐真实 admin-web） | K1–K29（含 K3b/K5b/K16b，共 32 条） | 已打通 |

## 六、业务规则确认状态（已固化=确定性交互 / 待确认=黄色便签占位）

**已确认（2026-10-16，原型为绿色「已确认」便签并画成确定性交互）**：

| 决策 | 内容 | 固化落点 |
|------|------|---------|
| D1 | 扣次时机 = 预约预扣 + 排期 COMPLETED 确认（签到不扣次） | P-M5 结果页、P-T1、P-M7（见 `business-rules.md` R-B4） |
| D3 | 卡失效替代 = 提示 + 自助换卡 + 人工兜底三层；冻结/作废前展示"该卡 N 个有效预约受影响" | P-A2、P-A5、P-M6（R-B8） |
| D4 | 有效期边界：`expire_at` 当天 23:59:59 前可约可签；PENDING 卡生效日前不可约 | P-M3、P-M4（R-B7） |
| D5 | 缺席自动消解（课开即扣，NO_SHOW 仅记录） | P-A5、P-T1（R-B7） |
| D9 | 期卡发卡 PENDING → 预约不扣次+预期有效期重叠预校验 → 排期 COMPLETED 激活写有效期；PENDING 90 天无 COMPLETED 自动作废；freeze 对 PENDING 拒绝 | P-M4、P-M1、P-M5、P-A6、P-T1（R-B7） |

**仍待确认（原型保留黄色「决策占位」便签，不画成定论）**：

| 决策 | 内容 | 原型占位位置 |
|------|------|------------|
| D2 | 用尽表达（现为徽标，不新增状态） | P-M1、P-A1、P-A2 |
| D6 | 多卡默认推荐策略（先过期优先，现默认选第一张可用卡） | P-M4 |
| D7 | 改期/改派（**待开发原子端点**，按钮灰置） | P-M6、P-A5 |
| D8 | 退款（**依赖 F6.1**，按钮灰置） | P-A4 |

> D1/D3/D4/D5/D9 已在 `open-decisions.md` 记录确认（2026-10-16）并固化为 `business-rules.md` R-B4/R-B7/R-B8；D2/D6/D7/D8 仍为占位，原型未将其画成确定交互。

## 七、一致性红线自检（对照 `prototype-acceptance.md` 第三节）

| 红线 | 自检结果 |
|------|---------|
| 不得把"预约成功"画成"签到成功/已核销" | 通过：P-M5 文案为"已预扣 1 次"（次卡）/"首次上课后激活"（期卡），签到独立在 P-T1 |
| 不得出现后端不存在的 API 被画成可用且无标注 | 通过：D3/D7/D8 相关按钮均灰置或标注"待开发/占位" |
| 学员端不得展示 operator/幂等键/内部堆栈 | 通过：P-M2 使用记录仅展示类型/时间/关联课程/变动数 |
| 未确认决策不得画成确定交互 | 通过：D2/D6/D7/D8 为黄色「决策占位」；D1/D3/D4/D5/D9 已确认（绿色「已确认」便签 + 确定性交互） |
| 不得暗示前端传 tenant_id/user_id | 通过：原型无任何身份参数传递表达 |

## 八、结论与残余风险

- **结论**：v8 原型在 v7 基础上**将 D1/D3/D4/D5/D9 决策固化落地**，完成**视觉层 + 结构层 + 底部导航（四 Tab）/首页/我的 + AI 助手页 + 管理端 + 决策固化**对齐，**121 项断言全部通过**（v7 为 113、v5 为 81、v4 为 60、v3 为 48、v2 为 33）；11 条流程可脚本复现；真实页面复用关系、视觉模拟范围、待新增页面、决策确认状态均已显式声明。
- **决策固化（v8 新增）**：D1/D3/D4/D5/D9 由产品负责人确认（2026-10-16）后，原型对应便签由黄色「决策占位」转绿色「已确认」并画成确定性交互；移除演示用 `conflictSim` 模拟开关，改由**真实演示重叠期卡 C8** 驱动区间重叠拦截；`addDays` 改 UTC 基准；`doBooking` 补 `schedId/cardId` 使 P-M5 渲染真实结果。文档侧 `open-decisions.md` 补确认日期、`business-rules.md` 新增 R-B7/R-B8 并修订 R-B4。新增 **[J] 断言组（8 条）**覆盖，**[A]–[I]/[K] 组 113 条无回归**。
- **管理端对齐（v7 新增）**：P-A1/P-A2/P-A3/P-A4 按真实 `apps/admin-web/src/views/card-types/index.vue`、`views/membership/index.vue` 重做（列/枚举/弹窗/详情页）——P-A1 计费方式 tag 用 `success/warning/info`、P-A2 用 `primary/success/warning`；管理端状态文案为「未激活/正常/已过期/已冻结/已作废」（区别于学员端「使用中/已用尽」）；P-A4 改为 `el-descriptions` 两列网格、流水为原型扩展。新增 **[K] 断言组（32 条）**覆盖，**[A]–[I] 组 81 条无回归**。
- **AI 助手一级 Tab（v5 新增）**：原型的 AI 助手此前**不存在**（真实端为 `AiAssistant.vue` 悬浮弹窗）。按产品需求：底部导航由三 Tab 扩为**四 Tab「首页/排期/AI 助手/我的」**（AI 项复用真实 `ai-robot` 图标）；新增独立完整聊天页 **P-M10**（香槟金主题三步式布局：顶部标题/会话状态 + 独立滚动对话区 + 底部固定输入区）；常用问题点击**真实产生模拟对话**（含加载中 `ai-dots` 与错误态 `ai-bubble.err`）。新增 **[I] 断言组（21 条）**覆盖。
- **底部导航对齐（v4 新增）**：原型原用废弃组件 `StudentTabBar.vue` 结构（文案"预约"、emoji 图标、激活色 `#c9a66b`、无指示条），与真实 `HomeTabBar.vue` 不一致。v4 以 `HomeTabBar.vue` 为 ground truth 重做 TabBar（三 Tab 首页/排期/我的、线性 SVG、激活 `#8b7355`、`.tab-indicator`），新增 **P-M8 首页**与 **P-M9 我的**两页，并新增 **[H] 断言组（12 条）**覆盖 TabBar 与两页 DOM/跳转。
- **结构对齐（v3 新增）**：v2 只对齐了颜色/变量，漏了 DOM 结构与交互模式（`ui-visual-spec.md` 第 6 节即为此补充）。v3 按该节逐条重建 P-M1/P-M3/P-M4/P-M6，并新增 **[G] 结构对齐断言组（15 条）**：
  - 断言改绑**真实源码类名**（`card-status-badge`/`credits-display`/`card-selector-popup`/`filter-tabs` 等），不再绑定 v2 自造类名，从而消除 v2 的"**假通过**"盲区。
  - 覆盖：双胶囊 Tab、复制图标+竖线、`remaining/total次` 同排、行内激活、**卡片不可点击**、分类/日期双栏、排期卡两栏、容量口径 `booked/capacity 人`、按钮状态类、底部选卡弹窗、四筛选 Tab、90 分钟取消时限、待新增页标注与入口灰置。
- **残余风险（需知悉）**：
  1. 未做真实浏览器渲染验证（无浏览器/无头环境），视觉最终效果仍建议人工走查一次。
  2. 原型数据为 mock，**不代表后端真实接口行为**；接入 `/api/v1/*` 后需重新验证。
  3. P-A5/P-M2/P-M5/核销查询 为原型构思稿，尚无对应后端端点与真实页面，落地前需走 `feature-delivery-lifecycle`。
  4. [G]/[H]/[I]/[K] 组校验的是"DOM 类名/字段/结构标记存在"，**不等价于像素级视觉一致**；结构对齐后的最终观感仍建议对照真实小程序/管理后台人工比对一次（可用微信开发者工具打开 `apps/miniapp`、浏览器打开 `apps/admin-web`）。
  5. v4 未复刻的真实子页（首页「全部课程/课程详情」、视频播放、解绑微信/退出登录）以 `toast` 占位；如需完整复刻需另建子页面。
  6. **AI 助手为模拟对话，未接入真实 AI**：原型仅按关键词返回本地模拟文案（不调用 `/api/v1/ai/*`）；且原型配色为**香槟金**，与真实 `AiAssistant.vue` 的**蓝紫**不同——真实端后续改造（TabBar 增 AI 项 + AI 页整页化）需另立任务，不得以本原型冒充真实端已完成。
