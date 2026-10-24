# F7.0 技术方案设计（Solution Design）

> 日期：2026-10-19
> 范围：页面与模块设计 / 图片存储方案评审 / 首页配置与发布机制 / 后续 API 与数据模型建议
> 原则：**先核对现有接口（见 requirements-analysis.md 第 1 节），再决定「复用 / 扩展 / 新增」**；所有"新增"均标注为候选，本阶段不落地。

---

## 一、页面与模块设计总览

### 1.1 管理端信息架构（新增部分）

在现有 11 项一级导航基础上：

- **改造**「用户管理」：列表新增头像列；新增/编辑弹窗新增头像上传区。
- **改造**「教室管理」：**保持仅卡片视图**（不新增表格视图，`D-F7-C2`），卡片新增封面图/位置/教室编码；新增/编辑弹窗新增图片上传区；**移除容纳人数与维护/状态概念**。
- **新增**一级导航「小程序首页」（`/miniapp-home`，最终名待确认 D-F7-D1）→ 小程序首页模块配置。
- **改造**全局右上角用户区：下拉新增「个人资料」，弹窗复用 `GET/PATCH /auth/me`。

### 1.2 首页模块配置的模块类型（第一版固定 5 类，D-F7-D3）

| 类型 | key | 数据来源 | 现状对齐 |
|------|-----|----------|----------|
| Banner 轮播 | `banner` | 管理端配置（图片+文案+跳转） | 小程序现为**硬编码** |
| 师资团队 | `teachers` | 复用 `GET /teachers`（手动选择 N 位） | 小程序**已走真实 API** |
| 推荐课程 | `courses` | 复用 `GET /courses`（手动选择 N 门） | 小程序**已走真实 API** |
| 舞蹈视频 | `video` | 管理端配置（封面+地址） | 小程序现为**硬编码** |
| 公告/活动 | `notice` | 管理端配置（标题/内容/图/有效期） | 小程序**当前不存在** |

> 设计含义：`teachers`/`courses` 两个模块**不新增业务数据**，只增加"首页展示的选择与排序"（展示数量、勾选、顺序）；`banner`/`video`/`notice` 为**新增配置数据**。

### 1.3 模块配置项（最小集合，不堆无价值字段）

> **公共字段（所有模块）**：`sort`（排序值，1 最靠前，连续整数；模块列表通过**拖动排序**调整，放下后整体重写为 1..n，`D-F7-D2`）、`enabled`（启用/停用）。

- **banner**：图片*、标题*、副标题、跳转目标(枚举 D-F7-D6)、展示顺序(序号)、启用。
- **teachers**：模块标题、展示数量(1-12)、教师选择(多选，抄现有 teachers 数据)。
- **courses**：模块标题、展示数量(1-12)、课程选择(多选)、排序规则(手动顺序/最新)。
- **video**：模块标题、视频标题*、封面图*、视频地址*、跳转目标、启用。
- **notice**：模块标题、标题*、内容*、图片、有效期(起止)、展示状态。

> 排序落库建议：`sort_order`（int，租户内唯一连续）；拖拽后建议以 **单次批量接口** `PATCH /home/config/draft/reorder` 提交新顺序（见第四节候选接口），避免逐条请求与中间态。

---

## 二、页面清单（详见 screen-inventory.md）

P-F7-01 用户管理列表（含头像）/ P-F7-02 新增·编辑用户（头像上传）/ P-F7-03 右上角用户菜单 / P-F7-04 个人资料编辑弹窗 / P-F7-05 教室管理（**仅卡片视图**；原「表格视图 P-F7-06」已按 `D-F7-C2` 取消）/ P-F7-07 新增·编辑教室弹窗（含图片）/ P-F7-08 首页管理模块列表 / P-F7-09 Banner 配置 / P-F7-10 师资团队配置 / P-F7-11 推荐课程配置 / P-F7-12 舞蹈视频配置 / P-F7-13 公告·活动配置 / P-F7-14 小程序首页预览 / P-F7-15 发布确认与发布结果 / P-F7-16 异常状态集（空数据/加载失败/上传失败/发布失败）。

**页面查重结论**：上述页面中 **0 页与现有 admin-web 页面重复**（用户管理/教室管理为**在既有页上扩展**，其余为新增）；**与 F6.0 原型 0 重复**（F6.0 聚焦会员卡与预约，F7.0 聚焦用户头像/教室图片/首页配置）。P-F7-09~13 复用同一抽屉壳、仅内部表单不同 —— 不重复建页。

---

## 三、页面与模块设计（要点）

### 3.1 用户管理（P-F7-01/02）

- 列表：在原 9 列前插入「头像」列（`el-avatar :src="row.avatar_url"`，无值回退默认头像）。其余列/筛选/分页/操作**原样保留**。
- 弹窗：新增与编辑共用「头像上传区」组件。上传区状态机：`idle → preview → uploading → success`，异常分支 `format-error / size-error / upload-fail(retry)`。新增场景：先上传得 `avatar_url` 再提交；编辑场景：上传即暂存，点「确定」才随 PATCH 提交（**取消不覆盖原头像**）。

### 3.2 个人资料（P-F7-03/04）

- 下拉：`个人资料` + `退出登录`（沿用现有退出确认）。
- 弹窗：头像(可换) + 昵称(可编辑) + 手机号(只读) + 角色(只读 tag)。保存 → 成功后同步刷新 `adminInfo`（顶部头像/昵称即时更新）。保存失败 → 行内/`ElMessage` 错误，不关闭弹窗。

### 3.3 教室管理（P-F7-05/07）

- 视图形态：**仅卡片网格**，**无表格视图、无视图切换控件**（D-F7-C2）。
- 卡片：封面图(16:9，**未设置封面 / 失效时统一回落「暂无图片」占位，不绘制默认封面**) / 名称 + 教室编码 tag / 位置 / 设备 / 操作。
- 弹窗：教室编码*(必填、唯一) + 教室名称* + 封面图上传 + 位置 + 设备；`code` 保存时做唯一性校验（重复 → 「教室编码已存在」）；`location` 标「待评审」。
- 字段说明：新增 `code`（教室编码，租户内唯一）/ `location` / `cover_image_url`；**已删除 `capacity`（容纳人数）与 `status`（维护状态）**。
- 状态：loading / empty / 搜索无结果 / 加载失败(el-result 重试) / **未设置封面(「暂无图片」占位)** / 图片加载失败(占位)。

### 3.4 首页管理（P-F7-08~13）

- 模块列表：每行 = 拖拽手柄（`⠿`，HTML5 `draggable`）/ 排序值徽标（1 最靠前）/ 模块名称+摘要 / 启用开关 / 编辑 / 状态徽标(草稿未发布/已发布)。排序通过拖动完成（`D-F7-D2`），无独立上移·下移按钮。
- 编辑：**右侧抽屉**（`el-drawer` size≈560px），内部按模块类型渲染不同表单；底部「保存草稿」「取消」。
- 顶部工具栏：「预览小程序首页」「发布」。

### 3.5 预览与发布（P-F7-14/15）

- 预览：**手机壳内复刻真实小程序学员端首页**（`apps/miniapp` Home，含顶部定位导航栏 / Banner / 师资 / 课程 / 视频），底部 TabBar 采用 **F6.0 学员端原型口径 4 Tab（首页/排期/AI 助手/我的，AI 为第 3 个一级 Tab，无悬浮 FAB）**，按草稿实时渲染 5 模块（顺序/启用生效）；标注「原型模拟数据」。
- 发布：二次确认弹窗（列出将发布的变更摘要）→ 模拟成功/失败两种结果（失败保留旧版本提示）。

---

## 四、图片上传与存储技术方案（A / B / C 对比）

### 4.1 三方案对比

| 维度 | **A. 本地文件存储** | **B. 阿里云 OSS 对象存储** | **C. 客户端受控临时凭证直传** |
|------|--------------------|---------------------------|------------------------------|
| 开发成本 | 低（后端写本地目录 + 静态托管） | 中（接入 OSS SDK、bucket 策略、签名 URL） | 高（预签名接口 + 四端各自直传与重试） |
| 生产可靠性 | 低（依赖单机磁盘） | **高**（多副本/冗余，官方 SLA） | 高（同 B 存储，风险在前端） |
| ECS 磁盘占用 | 高（图片视频堆积占磁盘） | **零**（存 OSS） | 零 |
| 容器重建后文件持久性 | **差**（容器重建/多副本 → 文件丢失） | **好**（与容器无关） | 好 |
| 公网访问与 CDN | 需 Nginx 反代，扩 CDN 麻烦 | **原生支持 CDN 加速** | 同 B |
| 上传安全 | 差（易被上传可执行文件/穿透） | 好（后端统一校验类型/大小） | **较弱**（凭证虽受控，但校验分散在前端，可绕过） |
| 多租户隔离 | 需自建目录约定 | **可用 key 前缀 `t/{tenant_id}/` 隔离** | 同 B |
| 文件访问权限 | 需自建鉴权 | 支持私有 bucket + 签名 URL / 或公开读 | 同 B |
| 费用与运维复杂度 | 磁盘/备份成本 + 运维高 | 按量计费（存储+流量）+ 运维低 | 同 B（+前端复杂度） |

### 4.2 结合当前部署的推荐

**推荐：方案 B（阿里云 OSS）+ 后端中转上传**（D-F7-A1/A3）。理由：

1. 项目部署为 Docker + Compose + Nginx + ECS，**本地方案在容器重建/横向扩容时丢文件**，是硬伤。
2. 项目已明确"后续图片存储评估阿里云 OSS"（任务书背景），B 与之契合。
3. 后端中转符合项目「后端是唯一权威方 / 分层」规则：类型、大小、租户前缀、鉴权集中在 FastAPI，Web 三端共用 `api-client` 零改造。
4. 方案 C（直传）虽省带宽，但需 **admin-web / student-web / teacher-web / miniapp 四端**各实现直传+重试+校验，成本与安全面大，**不建议第一阶段**。

**开发期降级**：本地可用 `LOCAL_UPLOAD_DIR` 落盘 + Nginx/StaticFiles 托管（仅开发），通过配置项 `STORAGE_BACKEND=local|oss` 切换，**生产强制 OSS**。

### 4.3 数据库存储建议（D-F7-A2）

- 业务表（`users.avatar_url`、未来 `classrooms.cover_image_url`）存 **`object_key`**（如 `t/1/avatar/u_1024_1697.jpg`），由后端按环境拼成 URL；**不存完整域名 URL**（换 CDN 不必刷库）。
- 另建**文件记录表 `file_objects`**：`id / tenant_id / object_key / mime / size / biz_type(avatar|classroom|banner|video_cover|notice) / uploader_id / created_at / deleted_at`，用于审计、清理与"孤儿文件"回收。
- 清理策略：软删除业务记录时，异步任务扫描 `file_objects` 中无引用者 → 删除 OSS 对象（延迟回收，避免误删）。

### 4.4 上传约束（D-F7-A4）

- 类型白名单 `image/jpeg,image/png,image/webp`（按魔数校验，不只看扩展名）。
- 大小：图片 ≤ 5MB；头像 ≥200×200 方形。
- 服务端重命名（不信任客户端文件名）；禁止可执行扩展名；限制单租户上传频率。
- 返回：`{ object_key, url, mime, size }`（最小化，不含内部路径）。

---

## 五、首页配置与发布机制（需求 E）

### 5.1 数据流

```
管理端编辑(草稿) → 保存草稿(PUT draft) → 预览(GET preview, 读草稿)
   → 发布(POST publish, 原子写 published 快照) → 成功/失败(保留旧版本)
   → 小程序 GET /miniapp-home/published (按 tenant 隔离) → 按 module_type/order/enabled 渲染
```

### 5.2 关键机制

| 问题 | 方案 |
|------|------|
| 草稿与已发布分离 | 两份数据：`draft`（可随时改）+ `published`（发布快照，带 version） |
| 预览看未发布修改 | 预览接口读 **draft**，标注"预览态"，与线上无关 |
| 发布失败保留旧版本 | 发布为原子操作：校验通过才覆盖 `published`；失败返回错误且 `published` 不变 |
| 小程序请求失败降级 | 分级降级（D-F7-E3）：`teachers/courses` 回落真实 API；`banner/video/notice` 用本地缓存，无缓存则隐藏 |
| 模块为空/停用 | 静默隐藏该模块（D-F7-E4），不渲染空壳 |
| 图片失效 | 统一占位图 + `onerror` 回退（D-F7-E7） |
| 租户上下文 | `GET /miniapp-home/published` 强制 `x-tenant-slug` + `TenantAwareRepository`（D-F7-E5） |
| 跨租户隔离 | 所有首页配置表均含 `tenant_id`，自动注入过滤 |
| 改草稿不影响线上 | 读写作用域分离：draft 接口只改 draft；published 只在发布时更新 |

### 5.3 发布版本模型

`published` 每次发布生成一个**不可变快照**（`version` 自增 + `published_at` + `operator_id`），小程序只读**最新版本**；便于回溯与"发布失败保留旧版本"。

---

## 六、后续正式实现所需的候选接口与数据模型建议

> ⚠️ 均为**设计候选**，非已实现。表内「性质」列区分复用/扩展/新增；实现前须再次核对现网路由。

### 6.1 候选接口

| # | 接口 | 方法 | 性质 | 说明 |
|---|------|------|------|------|
| 1 | `/api/v1/upload/image` | POST | **新增** | 上传图片，返回 `{object_key,url}`；四关校验 + 类型/大小校验 |
| 2 | `/api/v1/users/{id}` | PATCH | **复用** | `UserUpdate` 已含 `avatar_url`，头像保存直接复用 |
| 3 | `/api/v1/users/` | POST | **复用** | `UserCreate` 已含 `avatar_url` |
| 4 | `/api/v1/auth/me` | GET / PATCH | **复用** | 个人资料读取/更新（白名单 nickname+avatar） |
| 5 | `/api/v1/classrooms` | POST/PATCH | **扩展** | 需新增 `cover_image_url/location/code` 字段（D-F7-C1、D-F7-C3；**不含 capacity**），`code` 需租户内唯一约束 |
| 6 | `/api/v1/miniapp-home/draft` | GET / PUT | **新增** | 读取/保存草稿 |
| 6.1 | `/api/v1/miniapp-home/draft/reorder` | PATCH | **新增** | 拖动排序后**批量提交**模块新顺序（`sort_order` 重写为 1..n，`D-F7-D2`） |
| 7 | `/api/v1/miniapp-home/preview` | GET | **新增** | 预览（读草稿，原型用 Mock） |
| 8 | `/api/v1/miniapp-home/publish` | POST | **新增** | 发布（原子写 published 快照） |
| 9 | `/api/v1/miniapp-home/published` | GET | **新增** | 小程序读取已发布配置（租户隔离） |
| 10 | `/api/v1/teachers`、`/api/v1/courses` | GET | **复用** | 师资/课程模块"内容选择"数据源 |

### 6.2 候选数据模型

```text
file_objects (新增)
  id, tenant_id, object_key, mime, size, biz_type, uploader_id, created_at, deleted_at

home_configs (新增)   —— 草稿与发布快照分离
  id, tenant_id, scope('draft'|'published'), version, payload(JSONB),
  published_at, operator_id, created_at, updated_at
  UNIQUE(tenant_id, scope)        # draft 唯一；published 取 version 最大者

  payload 结构（示意）：
  {
    "modules": [
      {"type":"banner","enabled":true,"sort":1,"title":"",
       "items":[{"image_key":"...","title":"...","subtitle":"...","link_type":"course_detail","link_id":12}]},
      {"type":"teachers","enabled":true,"sort":2,"title":"师资团队","limit":6,"teacher_ids":[3,5]},
      {"type":"courses","enabled":true,"sort":3,"title":"推荐课程","limit":4,"course_ids":[8,9],"sort_rule":"manual"},
      {"type":"video","enabled":true,"sort":4,"title":"舞动 · 让生活更美好",
       "items":[{"title":"...","cover_key":"...","video_url":"...","link_type":"none"}]},
      {"type":"notice","enabled":false,"sort":5,"title":"公告","content":"...","image_key":null,
       "valid_from":null,"valid_to":null}
    ]
  }
```

- 首页配置**只存引用的 key/id**，不冗余业务数据：`teacher_ids/course_ids` 引用真实教师/课程；小程序端由后端组装（或小程序分别调 `/teachers`、`/courses` 拼装）。
- 所有表带 `tenant_id`，Repository 继承 `TenantAwareRepository`。

### 6.3 需要评审的边界

- 上传接口的**频率限制**与**病毒/魔数校验**。
- 首页 `payload` 用 JSONB 还是独立子表（本方案推荐 JSONB，结构变更灵活，代价是查询能力弱）。
- 发布**并发**（两人同时发布）：建议以 `version` 乐观锁。
- 图片**清理**任务与租户上下文（定时任务须 `set_tenant_id`）。

---

## 七、交付与验证

- 原型：`prototype/index.html`（单文件，Mock，可交互，全跳转）。
- 检查脚本：`verify-prototype.js`（Node，DOM stub 下真实调用原型函数断言，退出码 0/1）。
- 本阶段**不**改 DB / 不装依赖 / 不建云凭证 / 不改部署配置。
