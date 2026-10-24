# F7.0 原型测试报告（Prototype Test Report）

> 日期：2026-10-19
> 被测对象：`docs/features/F7.0-admin-console-miniapp-home-prototype/prototype/index.html`
> 测试工具：`docs/features/F7.0-admin-console-miniapp-home-prototype/verify-prototype.js`（Node CommonJS）
> 测试性质：**可执行验证**（抽取内联脚本做语法检查 + DOM stub 下真实调用原型函数逐条断言），**非静态截图比对、非真实浏览器渲染验证**。

---

## 一、测试方法

| 步骤 | 内容 |
|------|------|
| 1 | 抽取 `index.html` 内联 `<script>`，用 `new Function(code)` 做语法检查（等价于浏览器能否解析） |
| 2 | 在 DOM stub（`document.getElementById` 返回轻量元素）下执行脚本，通过 `new Function(code + ';return {...}')()` 取回原型函数 |
| 3 | 逐条调用原型函数，断言**数据副作用**（STATE）与**渲染产物**（`innerHTML`）及**交付边界**（单脚本 / 无网络请求 / Mock 标注） |
| 4 | 汇总计数，存在任一 FAIL 则退出码为 1（可直接接入 CI） |

执行命令：

```bash
node docs/features/F7.0-admin-console-miniapp-home-prototype/verify-prototype.js
```

---

## 二、执行结果（实际执行）

```
[1] SYNTAX OK
...
================ 结果 ================
PASS: 106  FAIL: 0
EXIT=0
```

- **语法检查：通过**（单 `<script>` 块可解析）。
- **断言：106 / 106 全部通过**，退出码 **0**。

### 分组明细

| 组 | 覆盖范围 | 断言数 | 结果 |
|----|----------|--------|------|
| A | 用户管理（含头像）+ 上传全状态 + 校验 + 编辑取消不覆盖 | 21（A1–A20 + A16b） | 全部 PASS |
| B | 右上角用户菜单 + 个人资料（只读字段 / 校验 / 顶部同步） | 6（B1–B6） | 全部 PASS |
| C | 教室管理（**仅卡片视图** / **未设置封面 → 暂无图片占位** / 封面失效 → 占位 / 新增编辑 / **教室编码 + 唯一性校验** / 搜索空态 / **卡片「位置/设备」行内联线性 SVG 图标（非 emoji）** / **操作按钮无图标前缀**） | 16（C1–C11 + C2b/C6b/C8b/C10b/C10c） | 全部 PASS |
| D | 首页管理（5 模块 / 启停 / **拖动排序 + 排序字段** / 抽屉保存与必填校验 / **模块类型图标列 `.micon` 已删除**） | 20（D1–D15 + D6b–D6f） | 全部 PASS |
| E | 预览与发布（草稿/发布分离、失败保留旧版、降级、发布后改草稿不影响线上） | 11（E1–E11） | 全部 PASS |
| F | 异常状态（用户/教室/首页列表加载失败 + 重试恢复） | 6（F1–F6） | 全部 PASS |
| G | 交付边界（单脚本、无 fetch/XHR/axios、Mock 标注、D-F7 标记、无真实域名） | 7（G1–G7） | 全部 PASS |
| H | **外壳一致性（对齐 F6.0：顶栏 / 面板标题条 / 侧栏命名 / 旧壳已移除 / 侧栏范围与图标对齐真实 admin-web）** | 8（H1–H8） | 全部 PASS |
| I | **预览页复刻真实 miniapp 学员端首页（顶部导航 / F6.0 口径 4 Tab 底栏（AI 助手为第 3 个一级 Tab，无悬浮 FAB） / Banner 135° 遮罩 + 金色指示点 / 金色 section 图标 / 奶油渐变师资头像 / 左图右文课程卡 / 金色播放按钮 + 时长 / 暖奶油背景 / 侧栏图标改 HomeFilled）** | 11（I1–I11） | 全部 PASS |

> 计数：21 + 6 + 16 + 20 + 11 + 6 + 7 + 8 + 11 = **106**。

---

## 三、阶段 5 实际发现并修复的问题

以下问题在**首次运行验证脚本时被暴露**，已修复并**复测通过**：

| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| 1 | 原型 `renderAll()` | 关闭弹窗（用户/教室/个人资料/发布）后**遮罩 `#mask` 未隐藏、弹窗内容残留**（真机上表现为"取消/确定后弹窗不消失"） | 增加 `else` 分支清除 `modal-box` 与 `mask`；并把通用弹窗（退出确认）统一为 `STATE.modalOpen/modalHtml`，由 `renderAll` 统一渲染，避免"打开后又被 `renderAll` 冲掉" |
| 2 | 原型 `renderHeader()` | 顶栏下拉**仅在展开时**才出现在 DOM，入口文案不可稳定访问 | 改为**常驻渲染** `.dropdown`，用 `.dropdown.open` 控制显示 |
| 3 | `verify-prototype.js` | `text` 变量声明未使用（lint 告警） | 删除 |
| 4 | `verify-prototype.js` A15 | 新增用户用例**未填手机号/密码**，与"新增必填校验"矛盾导致断言失败 | 补齐 `phone/password/nickname` 后保存 |
| 5 | `verify-prototype.js` A16 | 断言把字符串与对象比较（无意义且会因前序失败崩溃） | 改为断言"弹窗已关闭 + 上传态已重置 + 遮罩已隐藏" |
| 6 | `verify-prototype.js` B4 | 用 `innerHTML` 判断遮罩是否显示（遮罩类名不在 innerHTML 内） | 改用 `$('mask').className` |
| 7 | `verify-prototype.js` C | `cf()`（教室表单 setter）**未从原型导出**，导致用例抛错 | 在导出清单中补 `cf` |

> 说明：#1、#2 是**原型真实缺陷**（影响浏览器中的实际交互）；#3–#7 是**验证脚本缺陷**（不影响原型，但会影响验证可信度）。两类均已修复。

---

## 四、未执行 / 未验证项（如实声明，不标记为通过）

| 项 | 状态 | 说明 |
|----|------|------|
| 真实浏览器像素级渲染走查 | **未执行** | 当前验证在 DOM stub 下进行，不覆盖真实排版/字体/裁切效果，建议人工在 Chrome 打开走查一次（`prototype/README.md` 方式 1/2） |
| 多浏览器 / 响应式（移动端适配） | **未执行** | 原型定位为桌面管理端 + 手机预览框，未做跨浏览器矩阵 |
| 与真实 API 的联通 | **不适用（明确未接通）** | 本阶段明确不接后端，Mock 数据不代表接口已实现 |
| Figma 导入结果的还原度 | **未执行** | 当前环境仅有 Figma 只读能力，无法写入/生成 Figma 文件；导入路径见 `figma-import-guide.md` |
| 无障碍（a11y）/ 键盘导航 | **未验证** | 原型未做 a11y 专项 |
| 上传大文件的真实内存/性能 | **未验证** | 原型用"模拟成功/失败"按钮推进，不做真实文件 IO |

---

## 五、已知问题与限制

1. 原型上传流程以**显式「模拟成功 / 模拟失败」按钮**推进状态（**刻意不使用 `setTimeout`**），以保证验证确定性与可重复性；真实实现需接入上传进度与真实失败重试。
2. 图片存储为**内联 SVG dataURI**，仅用于离线演示；真实实现须接入对象存储（推荐方案 B，见 `solution-design.md` 第四节）。
3. 用户新建后 `id` 使用 `Date.now()`，仅原型用途，不代表后端 ID 生成策略。
4. 分页、批量操作、搜索筛选为**交互占位**（与现有 admin-web 保持一致的真实字段已保留，未虚构字段）。
5. 首页配置的**草稿/发布**在原型中为内存态（`publishedVersion` 自增模拟），**未落库**；真实需按下节建议落库。

---

## 六、下一阶段正式开发建议顺序

> 原则：严格遵循项目既有分层（Router → Service → Repository → DB；MCP/AI → Service），先补齐"上传/存储"这一**跨 A/C/D 的共同底座**，再按"只读复用 → 写扩展 → 新模块"递增风险推进。

1. **决策冻结（前置）**：产品逐项确认 `open-decisions.md` 的 D-F7-A1…E7（尤其 **A1 存储方案、A2 存 key vs URL、C1 教室新增字段**）。未确认项不得进入编码。
2. **上传与存储底座（需求 A/C/D 共用）**：实现 `upload` 模块（`router/service/repository/schemas/models`）——`POST /api/v1/upload/image`（四关校验 + 类型/大小/租户前缀 + 写 OSS + 落 `file_objects`）+ 迁移；补齐 `FileObject` 模型与租户隔离；补清理策略。**先于所有图片相关 UI**。
3. **需求 B（最小改动、复用优先）**：后端 `GET/PATCH /auth/me` **已存在**，仅需前端接入个人资料弹窗（不改白名单、不放手机号）。风险最低，可先交付。
4. **需求 A 用户头像**：后端 `users.avatar_url` 已存在 → 仅需在用户列表/弹窗接入头像展示与上传组件（复用步骤 2 的上传接口与 `Uploader` 组件）。
5. **需求 C 教室图片（仅卡片视图）**：`classrooms` 需**新增字段**（`code/cover_image_url/location`，**不含 capacity/status**）+ 迁移 + DTO + 卡片视图渲染（**不新增表格视图，`D-F7-C2`**）。
6. **需求 D 首页管理**：新增后端模块（`home_configs` 草稿表 + 发布版本表，JSONB payload，`sort_order`）；前端一级导航 + 模块列表 + 右侧抽屉 + 5 类模块配置表单。
7. **需求 E 首页数据流**：`GET /miniapp/home/published`（租户隔离 + 鉴权）+ 发布原子事务 + 前端预览接口；改造小程序首页（`pages/student/courses/index.vue`）由静态硬编码改为读接口 + 分级降级 + 空/停用模块静默隐藏 + 图片 onerror 占位。
8. **回归与验收**：按 `prototype-acceptance.md` 执行页面/交互/异常验收；重点回归多租户隔离、上传鉴权、发布事务、401 刷新链路。

### 契约与影响面提醒（来自 `interaction-spec.md` 附录核对）

- 复用（✅ 已存在）：`GET/PATCH /auth/me`、`POST /auth/logout`、`users` CRUD、`classrooms` CRUD、`GET /teachers`、`GET /courses`。
- 需新增：`POST /upload/image`、`home_configs` 草稿/预览/**排序重排**/发布接口、`GET /miniapp/home/published`。
- 接口契约变更**必须同步评估 4 端**（admin / student / teacher / miniapp），并按 `packages/api-client` + `api-types` 生成流程交付。

---

## 七、变更记录

| 日期 | 变更 | 影响文件 | 复测 |
|------|------|----------|------|
| 2026-10-19 | 首页模块排序交互由「上下移动按钮」改为**排序字段 `sort` + 拖动排序**（`D-F7-D2` 产品确认） | `prototype/index.html`（模块行改为拖拽手柄 + 排序值徽标；新增 `reorderHomeModule` / 拖动事件处理器）、`verify-prototype.js`（新增 D6b–D6f 共 5 条断言）、`open-decisions.md`、`solution-design.md`、`interaction-spec.md`、`entity-state-model.md`、`requirements-analysis.md`、`prototype-acceptance.md`、`prototype/README.md` | 82 / 82 PASS（退出码 0）|
| 2026-10-19 | **原型 CSS 主题风格对齐 F6.0**（产品要求 F7.0 与已交付的 F6.0 保持一致）：`<style>` 逐项对齐到 F6.0 口径 —— 补 `--gold-l/--gold-grad/--gold-grad-btn`；按钮圆角 4px/内边距 7px 14px/字号 13px/hover 色块、`.btn.primary` 改蓝色渐变；表格表头 `#f5f7fa`+斑马纹；弹窗圆角 8px/遮罩居中；输入框圆角 4px/字号 13px；标签变体边框色；卡片/`.mod-row` 圆角 8px；toast 改深色 `#1f2937`；侧边栏 hover/active 文字色与加粗 | `prototype/index.html`（仅改 CSS；HTML/JS/Mock 与类名不变）、`prototype/README.md` | 82 / 82 PASS（退出码 0）；F6.0 文件未被修改（mtime 10-18） |
| 2026-10-19 | **教室管理需求变更 + 界面布局全量对齐 F6.0**：教室删除「容纳人数/capacity」与「状态/维护」概念（状态列、维护按钮、`toggleClassroomStatus`、种子 `status` 一并移除），新增「教室编码 `code`」（必填、租户内唯一，保存做唯一性校验拦截重复，`D-F7-C1`/`D-F7-C3` 产品确认）；同时 F7.0 界面**刻意保留的布局尺寸差异**全量对齐 F6.0（侧边栏 220→200px、顶栏 60→48px、内容区 padding 24→14px、`.page-head h2` 20→15px、工具栏 gap 12→8px/margin 16→12px/输入框 padding、弹窗 padding 与宽度 520→480px 等） | `prototype/index.html`（教室数据结构/渲染/校验 + CSS 尺寸值）、`verify-prototype.js`（C 组断言 11→16 条）、`open-decisions.md`、`solution-design.md`、`screen-inventory.md`、`interaction-spec.md`、`entity-state-model.md`、`requirements-analysis.md`、`prototype-acceptance.md`、`prototype/README.md` | 87 / 87 PASS（退出码 0）；F6.0 文件未被修改 |
| 2026-10-19 | **原型样式按组件语义逐条对齐 F6.0 实际取值（CSS-only 自证）**：仅改 `prototype/index.html` 的 `<style>`，不重命名选择器、不动 HTML 结构/class 名/JS/Mock。用一次性 `node -e` 脚本（剥离 CSS 注释后解析选择器→声明、规范化排序比对，F6 声明 → F7 声明 → 一致）对 **81 对映射**逐条自证：**完全一致 72 对、口径超集 9 对、结构/无基准 0 对、不一致 0 对**；另确认 **F7 专有类 93 个**（`.app-shell`/`.dropdown`/`.drawer*`/`.switch*`/`.multi*`/`.mod-row*`/`.uploader*`/`.phone*` 等）在 F6 中确无对应基准（0 例外）。口径超集 9 对：`:root`（增 `--sidebar`）、`.menu .ni`、`.rcard`、`.modal .mh`、`.field`、`.empty .et`、`.ph-banner`、`.ph-row`、`.legend`（均在 F6 声明基础上追加 F7 结构必需属性，F6 属性集 ⊆ F7）。 | `prototype/index.html`（仅 `<style>`）、`prototype-test-report.md`（本变更记录） | 87 / 87 PASS（退出码 0）；F6.0 文件未被修改（只读参考） |
| 2026-10-19 | **外壳结构统一到 F6.0（决定性收敛）**：产品确认"统一外壳"方案。F7.0 弃用原「全屏 `.app-shell`（`.sidebar`/`.header`/`.content`）」，改用 F6.0 完全一致的页面骨架 —— `#topbar`（品牌 + `.view-tabs` 视图切换）→ `#stage` → `.panel#admin-panel`（`.page-title` 标题条，含 `.pid`「ADMIN」编号徽标 + `#admin-ptitle` 当前页标题 + 右侧 `.pt-right` 操作区与用户菜单）→ `.admin-body`（`.admin-side` 深色侧栏 + `.admin-main` 主区）。CSS 外壳段**逐字采用 F6.0 声明**（`#topbar`/`.view-tabs`/`#stage`/`.panel`/`.page-title`/`.admin-body`/`.admin-side`/`.admin-main`）；侧栏导航改用 F6.0 命名 `.admin-side .nav-item`；各页面原 `.page-head`（标题 + 操作按钮）**移除**，操作按钮改由 `#admin-actions` 注入面板标题条右区（消除"双标题条"差异）。旧壳类名 `.app-shell`/`.sidebar`/`.menu`/`.header`/`.crumb`/`.content`/`.page-head`/`#crumb-title` 全部清除。 | `prototype/index.html`（外壳 CSS + body 结构 + `renderAdminSide`/`renderAdminPage`/4 个页面函数 + 新增 `renderTopbar`/`goAdminEdit`）、`verify-prototype.js`（C1 改指 `admin-actions`；新增 H 组外壳断言 6 条）、`prototype-test-report.md` | 93 / 93 PASS（退出码 0）；F6.0 文件未被修改 |
| 2026-10-19 | **三合一变更（C1 教室仅卡片 / C2 侧栏范围与图标对齐真实 / C3 按钮风格对齐真实）**：① **C1** 教室管理移除表格视图与「表格⇄卡片」切换（删 `STATE.classroomView`、`toggleClassroomView`、`.seg` 三段 CSS，`renderClassroomsPage` 无条件渲染卡片，`D-F7-C2` 固化）；② **C2** 侧栏由 11 项裁剪为本次范围内 3 项（用户管理/教室管理/小程序首页），图标改内联 Element Plus 同源 SVG path（`user`/`officeBuilding`/`cellphone`，取自 `@element-plus/icons-vue` 编译产物），替换原 emoji；③ **C3** 按钮补齐真实 admin-web 规范：`.page-title .btn`（radius 8px / font-weight 500 / transition .2s）+ `.btn.primary:hover`（`box-shadow 0 4px 12px rgba(64,158,255,.4)` + `translateY(-1px)`）+ `.btn.primary:active`（复位）。 | `prototype/index.html`（教室渲染/CSS/侧栏 MENU+ICON+iconSvg/按钮样式）、`verify-prototype.js`（C 组重写 6 条、H 组新增 H7/H8）、`open-decisions.md`、`screen-inventory.md`、`interaction-spec.md`、`prototype-acceptance.md`、`requirements-analysis.md`、`solution-design.md`、`entity-state-model.md`、`figma-import-guide.md`、`prototype/README.md`、`prototype-test-report.md`（本报告） | 95 / 95 PASS（退出码 0）；F6.0 文件未被修改（其侧栏图标同批对齐真实、128/128 PASS） |
| 2026-10-19 | **原型优化（侧栏图标 + 预览页复刻真实小程序首页）**：① 侧栏「小程序首页」图标由生硬的手机矩形 `cellphone` 改为更贴合语境、更柔和、且同属 Element Plus 体系的 `HomeFilled`（首页图标，path 取自 `@element-plus/icons-vue` 编译产物，与真实 admin-web 图标风格一致）；② **P-F7-14 预览页**由简化占位重写为**复刻真实小程序学员端首页**（`apps/miniapp/src/pages/student/courses/index.vue` + `HomeTabBar`/`AppNavbar`/`AiAssistant`）：暖奶油背景 `linear-gradient(180deg,#faf6f0,#f5ede3)`、顶部导航栏（定位图标 + 机构名 + 下拉）、Banner `135deg` 深→浅遮罩 + 金色指示点、section 标题金色线性图标、师资奶油渐变圆形头像（`#f5e6d3→#e8d5c4`）+ 姓名/专长两行、推荐课程改左图右文横向卡片、视频卡金色圆形播放按钮 + 时长胶囊、底部 3 Tab 栏（首页/排期/我的，激活 `#8b7355`）、AI 悬浮入口；同时保留草稿标注 / 空模块静默隐藏（`D-F7-E4`）/ 图片失效占位（`D-F7-E7`）/ 接口失败降级（`D-F7-E3`）逻辑。旧占位类名 `.ph-banner`/`.ph-sec`/`.ph-row`/`.ph-card`/`.ph-teacher` 全部弃用，新增 `.m-*` 命名（对齐真实 miniapp 线性图标 stroke 风格）。 | `prototype/index.html`（侧栏 `ICON`/`MENU` + 新增 `MINI`/`miniIcon` + 预览 CSS 与 `renderPreviewPage` 重写）、`verify-prototype.js`（新增 I 组 11 条断言）、`prototype/README.md`、`interaction-spec.md`、`screen-inventory.md`、`prototype-acceptance.md`、`solution-design.md`、`prototype-test-report.md`（本报告） | 106 / 106 PASS（退出码 0）；F6.0 文件未被修改 |
| 2026-10-19 | **预览页 AI 助手入口调整（对齐 F6.0）**：用户指出 F6.0 已将 AI 助手从悬浮入口移入底部菜单栏；据此将 P-F7-14 预览页的 AI 助手入口由**悬浮 FAB（`.m-fab`）**改为**底部 TabBar 第 3 个一级 Tab「AI 助手」**，底部 TabBar 由 3 Tab（首页/排期/我的）改为 **4 Tab（首页/排期/AI 助手/我的）**，与 F6.0 学员端原型 `TAB_DEFS`（`首页/排期/AI 助手/我的`，AI 为第 3 个，激活 `#8b7355`）逐字一致；同时删除 `.m-fab` 全部 HTML 与 CSS。差异备案：真实 `apps/miniapp` 当前为 3 Tab + `AiAssistant.vue` 悬浮入口，原型/预览以 F6.0 口径为准，差异不静默取舍。 | `prototype/index.html`（TabBar HTML 改 4 Tab + 删除 `.m-fab` CSS/HTML + legend 说明）、`verify-prototype.js`（I3/I4/I5 调整，移除 FAB 断言）、`prototype/README.md`、`prototype-test-report.md`（本报告）、`interaction-spec.md`、`screen-inventory.md`、`prototype-acceptance.md`、`solution-design.md`、`figma-import-guide.md` | 106 / 106 PASS（退出码 0）；F6.0 文件未被修改 |
| 2026-10-19 | **教室管理默认封面图**：用户要求「教室管理封面图在未设置时默认一张符合页面风格且具吸引力的图」。据此新增 `roomDefaultCover()`（内联 SVG dataURI：香槟金渐变 `#e8d1a6→#c9a66b→#8b7355` + 镜面墙 4 块 + 把杆 + 地板反射 + 柔光/光斑 + 简笔舞者剪影，与页面香槟金主题一致），登记为 `IMG.ROOM_DEFAULT`；`renderClassroomsPage` 卡片封面改 `coverTag(r.cover || 'ROOM_DEFAULT', ...)`——**未设置封面（`cover===''`）不再显示「暂无图片」占位，而是渲染默认封面图**；仅**图片失效**（`BROKEN`，`cover==='BROKEN'`）保留占位演示（`D-F7-E7`）。 | `prototype/index.html`（新增 `roomDefaultCover()` + `IMG.ROOM_DEFAULT` + 卡片封面回落逻辑）、`verify-prototype.js`（C4 断言由「无封面→暂无图片占位」改写为「未设置封面→默认封面图，非占位」）、`prototype/README.md`、`interaction-spec.md`、`screen-inventory.md`、`prototype-acceptance.md`、`solution-design.md`、`entity-state-model.md`、`prototype-test-report.md`（本报告） | 106 / 106 PASS（退出码 0）；F6.0 文件未被修改 |
| 2026-10-19 | **默认封面图改版（写实舞者）**：用户反馈上一版默认封面中的舞者「太 AI（简笔火柴人）」，要求更真实。据此**重绘 `roomDefaultCover()`**：删除原「圆头 + 等宽线条」火柴人，改为**写实比例芭蕾舞者剪影**（发髻 + 头 + 颈 + 束腰躯干 + 扁平 tutu 舞裙（含顶缘微光）+ 双足并拢足尖 + 双臂上扬开位 + 手），并以 `rdDancer` 渐变赋予体积感；场景同步升级为更写实的舞蹈教室（镜面墙分区 + 把杆带支架 + 透视木地板 + 顶部反光 + 地面光池 + 景深投影），舞者整体施加 `feGaussianBlur 0.8` 轻微景深柔化以弱化「矢量图标感」。渲染产物经本地 `qlmanage` 转 PNG 二次目视校验（含从 `index.html` 实际提取的 dataURI 解码渲染），确认形态自然。 | `prototype/index.html`（仅重写 `roomDefaultCover()` + 其 defs）、`prototype/README.md`、`prototype-test-report.md`（本报告） | 106 / 106 PASS（退出码 0）；F6.0 文件未被修改 |
| 2026-10-19 | **教室占位封面去除叠加文案**：用户要求去掉默认图中的文案。教室占位封面 `ROOM1`/`ROOM2` 原由 `gradCover(a,b,label)` 叠加「舞蹈教室 A/B」文字；据此将 `gradCover` 改为**无 label 时不绘制 `<text>`**，并令 `ROOM1`/`ROOM2` 仅保留渐变、**不叠加任何文案**。`ROOM_DEFAULT`（写实舞者默认封面）本就无文字、保持不变；小程序预览的 Banner/视频封面（`BANNER1/2`、`VIDEO1`，非教室占位图）按原样保留其内容标题文案。 | `prototype/index.html`（`gradCover` 条件渲染 + `IMG.ROOM1/ROOM2` 去 label）、`prototype/README.md`、`prototype-test-report.md`（本报告） | 106 / 106 PASS（退出码 0）；F6.0 文件未被修改 |
| 2026-10-19 | **回退默认封面图 + 上传区改 Element 原生样式**：用户反馈①「图一这些操作没有啥用处，直接使用 Element UI 的样式就可以了」——上传区空闲态的「选择图片 / 演示： / 选 .txt / 选大图」调试按钮行全部移除，仅保留 Element Plus 原生虚线「＋ 选择图片」框 + 格式/大小提示文案；②「图二红框内容，没有图片时展示暂无图片，不需要绘制」——**删除 `roomDefaultCover()` 与 `IMG.ROOM_DEFAULT`**，`renderClassroomsPage` 卡片封面改回 `coverTag(r.cover, ...)`，教室**未设置封面**（`cover===''`）与**图片失效**（`BROKEN`）统一显示「暂无图片」占位；教室占位封面 `ROOM1`/`ROOM2`（仅渐变、无文案）保留。 | `prototype/index.html`（删 `roomDefaultCover()` + `IMG.ROOM_DEFAULT` + 卡片回落改回 `r.cover` + `renderUploader` 空闲态去调试按钮）、`verify-prototype.js`（C4 改写回「未设置封面→暂无图片占位」；A7 增补「无演示调试按钮」校验）、`prototype/README.md`、`open-decisions.md`、`entity-state-model.md`、`interaction-spec.md`、`screen-inventory.md`、`prototype-acceptance.md`、`solution-design.md`、`requirements-analysis.md`、`prototype-test-report.md`（本报告） | 106 / 106 PASS（退出码 0）；F6.0 文件未被修改 |
| 2026-10-19 | **操作按钮去图标前缀 + 卡片图标改线性 SVG + 删除模块类型图标列**：用户反馈①「图一：新增等按钮的前面的图标不需要」——`#admin-actions` 内操作按钮统一改**纯文字、去图标前缀**（用户管理「新增」、教室管理「新增」、首页管理「预览小程序首页 / 发布」、预览页「返回编辑 / 模拟接口失败·恢复正常」的 `＋ / 👁 / 🚀 / ← / ✅ / ⚠` 前缀全部移除）；②「红框前面的图标需要修改来贴近原有页面主题」——教室卡片「位置/设备」行的 `📍 / 🎛` emoji 改为**内联线性 SVG 图标**（`miniIcon('location')` / `miniIcon('equip')`，`stroke="currentColor"`，颜色回落 `--text-3`，与页面香槟金主题一致）；③「图二：红框中的内容删除」——首页管理模块行的**模块类型图标列 `.micon` 整段删除**（含对应 CSS 规则），模块行仅保留 排序值徽标 + 名称/摘要 + 启用开关 + 编辑。 | `prototype/index.html`（3 处 `ADMIN_ACTIONS` 去前缀 + `MINI.equip` 新增 + `miniIcon` 用于卡片 + 删 `.micon` 列与 CSS）、`verify-prototype.js`（C1/C6/D6b/H4 断言改写：锁「无 ＋ 前缀」「无 📍/🎛」「无 micon」）、`prototype/README.md`、`prototype-test-report.md`（本报告） | 106 / 106 PASS（退出码 0）；F6.0 文件未被修改 |

> 自证口径：F6/F7 的 `<style>` 先剥离 `/* ... */` 注释，再按 `选择器{声明}` 解析并规范化（去空白、`;` 分割、排序）后做集合比对；排除项仅「F7 专有类（无 F6 基准）」与「口径超集（F6 ⊆ F7）」，**逐字不一致数为 0**。

> 实现要点：拖拽使用 HTML5 原生 `dragstart/dragover/drop/dragend`（无需引入拖拽库）；**拖拽过程中不整页重渲染**（避免打断原生 drag），放下后由 `reorderHomeModule()` 统一重排并把排序值重写为连续 1..n；越界自动钳制。`moveHomeModule()` 保留为程序化兜底（底层复用同一重排逻辑）。

---

## 八、边界合规声明

- 本阶段**未修改**任何正式业务代码 / 数据库模型与迁移 / 真实 API / 登录·权限·租户隔离逻辑。
- **未覆盖** F6.0 及其它已有原型文件；F7.0 原型为**独立新建**。
- **未安装**任何依赖；**未接入**真实 OSS；**未创建**任何云凭证；**未修改**部署配置。
- 所有测试结果均来自**实际执行**的 `verify-prototype.js`；未执行的测试项已在第四节如实标注。
