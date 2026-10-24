# F7.0 Figma 导入说明（Figma Import Guide）

> 日期：2026-10-19
> 适用范围：仅 F7.0 原型（`prototype/index.html`，P-F7-01 ~ P-F7-16）。

## 一、重要前提（务必先读）

1. **HTML 不能无损转换为"完全可编辑"的 Figma 设计文件。** 任何"一键导入"都会把布局扁平化为图片或绝对定位图层，丢失 Auto Layout、Component/Variant、Variables 与语义命名。因此本指南给出的路径是**"参照原型在 Figma 中重建"**，不是格式转换。
2. **当前环境只有 Figma 只读能力**（`get_figma_data` 读取结构、`download_figma_images` 导出图片），**无写入 / 创建 / 连线能力**，无法由本 Agent 直接生成 Figma 文件。Figma 文件需由**拥有编辑权限的设计师在 Figma 桌面端手动重建**。
3. **Figma 免费版存在 3 个 Page 硬上限**：重建时请把全部 Frame 归并到 **≤3 个 Page**，避免触发限制。

## 二、建议的 Figma 文件结构（≤3 Page）

| Page | 内容 | 说明 |
|------|------|------|
| **Page 1 · Admin（后台）** | P-F7-01/02、P-F7-05（仅卡片视图）/07、P-F7-08~13（含右侧抽屉态）、P-F7-15 | 后台管理端全部 Frame |
| **Page 2 · Global & Profile** | P-F7-03 下拉态、P-F7-04 个人资料弹窗、P-F7-16 异常态合集 | 全局组件与跨页异常态 |
| **Page 3 · Miniapp Preview** | P-F7-14 小程序首页预览（草稿态 / 发布后态） | 学员端首页最终组合 |

> 若只需 2 个 Page，可把 Page 2 的「个人资料弹窗」并入 Page 1、异常态并入各主 Frame 的 Variant。

## 三、适合重建为 Frame / Component 的页面

**建议建为独立 Frame（含交互热点）：**

- P-F7-01 用户管理列表（含头像列）
- P-F7-05 教室管理（**仅卡片视图**；原 P-F7-06 表格视图已按 `D-F7-C2` 取消，不绘制）
- P-F7-08 首页管理模块列表
- P-F7-14 小程序首页预览
- P-F7-15 发布确认弹窗

**建议建为 Component / Variant（便于复用）：**

- `Button / Primary · Default · Small`（对应原型 `.btn / .btn.primary / .btn.sm`）
- `Input / Default · Readonly · Error`（对应 `.input / .input.readonly / .err`）
- `Tag / Pending(待评审) · New(NEW) · Status(启用/停用)`
- `Avatar / Image · Placeholder(.ph)`（头像缺省态）
- `Uploader / Idle · Preview · Uploading · Fail · Success`（**核心复用组件**，被用户弹窗 / 教室弹窗 / 个人资料 / 模块抽屉共用）
- `Modal / User · Classroom · Profile · Publish`
- `Drawer / Module Config`（5 类模块配置共用一个 Drawer 壳，内容用 Variant 区分）
- `ModuleRow / Enabled · Disabled · First · Last`

## 四、交互热点与 Flow starting point 设置

1. **每个入口控件都要画成可点击热点**（真实按钮/行/开关，不要另贴一层"热点面板"覆盖在页面上，以免与原 UI 重叠）。
2. **Flow starting point** 建议设 3 个，覆盖任务书「五-4 原型交互关系」的三条主链路：
   - `Flow 1 · 用户头像`：P-F7-01 → P-F7-02（上传态 Variant）→ 保存 → 回 P-F7-01
   - `Flow 2 · 个人资料`：任意页顶部用户区 → P-F7-03 下拉 → P-F7-04 → 保存 → 顶部头像/昵称同步
   - `Flow 3 · 首页配置`：P-F7-08 → P-F7-09~13 抽屉 → 保存草稿 → P-F7-14 预览 → 返回编辑 → P-F7-15 发布确认 → 成功/失败 → 回 P-F7-08
3. **连线规则**：
   - 抽屉/弹窗态与列表态**放在同一 Frame 的 Variant 内**，在 Variant 之间连线，避免跨页连线。
   - 异常态（上传失败 / 发布失败 / 空数据 / 图片失效）用 Variant 表达，不要各画一张孤立 Frame。
4. **Flow starting point 数量**：免费版对 Flow 数量有上限，若受限，把 3 条 Flow 收敛为 1 条主 Flow（首页配置），其余用 Variant 内连线表达。

## 五、视觉还原要点（与原型/真实端保持一致）

- **后台主题与 F6.0 原型口径一致**（F6.0 已确立为原型视觉基准，F7.0 原型 CSS 已对齐）：侧边栏 `#1a1a2e`、激活渐变 `#667eea → #764ba2`、主区背景 `#f0f2f5`、Element Plus 主色 `#409eff`、按钮圆角 4px、卡片/弹窗圆角 8px、表格表头 `#f5f7fa`。**不要**套用小程序香槟金主题。
- **小程序预览（P-F7-14）用香槟金主题**：主色 `#C9A66B` / 激活 `#8b7355`；其视觉基准为**项目现有小程序首页**（`apps/miniapp/src/pages/student/courses/index.vue`：Banner 轮播 / 师资横向滚动 / 推荐课程 / 舞蹈视频）；**底部 TabBar 按 F6.0 学员端原型口径绘制 4 Tab（首页/排期/AI 助手/我的，AI 为第 3 个一级 Tab，无悬浮 FAB）**，与真实端当前「3 Tab + AI 悬浮入口」的差异需在 Figma 中显式标注；**当前真实端无公告模块**（原型中的公告模块属新增，需在 Figma 中显式标注差异）。
- **占位图与裁切比例**：头像方形；banner / 视频封面 / 教室封面 16:9；图片失效统一回退占位（不出现破图）。
- **待确认便签**：`待评审 / 待确认 D-F7-xx` 黄色便签保留，作为设计-研发对齐的显式标记（对应 `open-decisions.md`）。

## 六、不建议的做法

- 不要把 HTML 渲染结果整页截图后贴进 Figma 当作 Frame（不可编辑、不可复用）。
- 不要跨 Page 连线（免费版限制 + 维护困难）。
- 不要为博取原型"丰富度"而添加无业务价值的配置项或装饰性 Frame。
