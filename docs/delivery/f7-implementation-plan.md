# F7.0 实施计划：后台管理端增强 + 小程序首页配置

> 日期：2026-10-26
> 风险等级：**L4**（跨模块 / 新模块 / DB 迁移 / 事务 / 并发发布）
> 规格冻结状态：**24 项决策全部已确认**（2026-10-19）
> 前置文档：
> - `docs/features/F7.0-admin-console-miniapp-home-prototype/screen-inventory.md`（16 页原型）
> - `docs/features/F7.0-admin-console-miniapp-home-prototype/solution-design.md`（技术方案）
> - `docs/features/F7.0-admin-console-miniapp-home-prototype/open-decisions.md`（24 项冻结决策）
> - `docs/features/F7.0-admin-console-miniapp-home-prototype/requirements-analysis.md`（Gap G1~G10）

---

## 一、Feature 拆分总览

按**后端基础先行、前端按依赖跟进、单向依赖不循环、每个子 Feature 可独立交付并具备冒烟路径**的原则，将 F7.0 拆为 6 个子 Feature：

| 子 Feature | 代号 | 端 | 核心交付 | 前置依赖 | 状态 |
|------------|------|----|----------|----------|------|
| DB Migration + Upload 模块 | F7.0.1 | api | 3 份迁移 + upload 四件套 | 无 | ✅ DONE（16a1720） |
| Classroom 扩展 | F7.0.2 | api + admin-web | 字段迁移 + admin-web 卡片/弹窗 | F7.0.1 | ✅ DONE（9f3e02b / c29341d） |
| User Avatar + Personal Profile | F7.0.3 | admin-web | 用户头像列/上传 + 右上角菜单 + 个人资料弹窗 | F7.0.1 | ✅ DONE（17e13e4） |
| Home Config 后端 | F7.0.4 | api | home-config 四件套 + draft/published 流程 | F7.0.1 | ✅ DONE（a89352a / 16dd2c5） |
| Home Config admin-web 前端 | F7.0.5 | admin-web | 模块列表 + 5 种配置抽屉 + 预览 + 发布 | F7.0.1、F7.0.4 | ⬜ TODO |
| Miniapp 首页改造 | F7.0.6 | miniapp | 从硬编码切到 published API + 降级逻辑 | F7.0.4 | ⬜ TODO |

**已完成部分的实现偏差备案**：
- 路由前缀采用 `/home-config/`（非方案文档的 `/miniapp-home/`），与项目 `/<snake_case>/` 模块风格一致。
- OSS SDK 采用 `alibabacloud-oss-v2`（原生 async，配 aiohttp），非 V1 `oss2` 的线程池包装。
- `modules[].type` 枚举以 solution-design.md payload 结构为准：`banner / teachers / courses / video / notice`。
- `GET /home-config/published` 在 Service 层把 `image_key` / `cover_key` 解析为完整 URL；draft 保持原始 object_key 供管理端编辑回填。
- 业务表图片字段统一存 `object_key`；前端拼 `/uploads/{object_key}`（admin-web 已加 `/uploads` dev 代理 + 该路径在租户中间件白名单内）。

**可并行的项**：F7.0.2、F7.0.3、F7.0.4 三者均可在 F7.0.1 完成后并行启动；F7.0.5 需等 F7.0.4 接口就绪，但 admin-web 模块列表的 UI 骨架可提前并行开发。

---

## 二、依赖图

```
                         ┌──→ F7.0.2 (Classroom 扩展)
                         │
  F7.0.1 (DB + Upload) ──┼──→ F7.0.3 (User Avatar + Profile)
                         │
                         └──→ F7.0.4 (Home Config 后端) ──→ F7.0.5 (Home Config admin-web 前端)
                                                                  │
                                                                  └──→ F7.0.6 (Miniapp 首页改造)
```

**并行窗口**：F7.0.1 完成后，F7.0.2 / F7.0.3 / F7.0.4 可三路并行，因为三者修改的文件集无重叠（分别是 classroom 模块、admin-web 用户页、新 home-config 模块）。

---

## 三、DB Migration 计划（F7.0.1 内的第一阶段）

**迁移生成位置**：`apps/api/alembic/versions/`（当前已有 33 份迁移，最新 head 需开发时通过 `alembic heads` 确认）。

### 迁移 1：扩展 classrooms 表

```sql
-- classrooms 新增 3 字段 + 唯一约束
ALTER TABLE classrooms ADD COLUMN code VARCHAR(50);       -- 教室编码，租户内唯一
ALTER TABLE classrooms ADD COLUMN location VARCHAR(200);  -- 教室位置
ALTER TABLE classrooms ADD COLUMN cover_image_url VARCHAR(500);  -- 封面 object_key

-- 先清理现有数据的 NULL code（或回填默认值 'R-001' 风格），再加约束
UPDATE classrooms SET code = 'R-' || LPAD(id::text, 3, '0') WHERE code IS NULL;

-- 替换原 uq_classrooms_tenant_name 为 tenant 内 code 唯一
ALTER TABLE classrooms ADD CONSTRAINT uq_classrooms_tenant_code UNIQUE (tenant_id, code);

-- 可选：原 uq_classrooms_tenant_name 是否保留？规格未明确删除，建议保留不冲突
```

**约束**：
- `code` 必填 + 租户内唯一（D-F7-C3）
- `cover_image_url` 可空（未设置封面时回落占位图，D-F7-E7）
- `location` 可空

### 迁移 2：新增 file_objects 表

```sql
CREATE TABLE file_objects (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL,
    object_key      VARCHAR(500) NOT NULL,     -- 如 't/1/avatar/u_1024_1697.jpg'
    mime            VARCHAR(50) NOT NULL,       -- 'image/jpeg'
    size            BIGINT NOT NULL,            -- 字节
    biz_type        VARCHAR(30) NOT NULL,       -- avatar | classroom_cover | banner | video_cover | notice
    uploader_id     BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    -- Tenant 隔离 + object_key 唯一（租户内不重复）
    CONSTRAINT uq_file_objects_tenant_key UNIQUE (tenant_id, object_key)
);
CREATE INDEX idx_file_objects_tenant_biz ON file_objects (tenant_id, biz_type);
```

### 迁移 3：新增 home_configs 表

```sql
CREATE TABLE home_configs (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     BIGINT NOT NULL,
    scope         VARCHAR(20) NOT NULL,        -- 'draft' | 'published'
    version       INTEGER NOT NULL DEFAULT 1,  -- draft 始终 1；published 每次发布递增
    payload       JSONB NOT NULL,              -- 完整首页配置
    published_at  TIMESTAMPTZ,                 -- 仅 published 记录有值
    operator_id   BIGINT,                      -- 发布操作人
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- 每租户 scope 唯一：一租户一份 draft + 一租户多份 published
    CONSTRAINT uq_home_configs_tenant_scope UNIQUE (tenant_id, scope, version)
);
-- 查询"最新 published"的常用索引
CREATE INDEX idx_home_configs_tenant_scope ON home_configs (tenant_id, scope);
```

**注意**：`payload` JSONB 结构需预留 `schema_version` 字段（建议顶层 `{"schema_version": 1, "modules": [...]}`），为未来模块类型扩展或结构演进做兼容。读取时按 schema_version 做适配；写入时固定当前版本。

---

## 四、各子 Feature 详细计划

### F7.0.1 — DB Migration + Upload 模块

**Goal**：完成 DB 结构变更、upload 模块四件套落地、图片上传全链路可用。

**Scope**：
- 3 份 alembic 迁移文件
- `upload` 模块完整四件套：`router.py` / `service.py` / `repository.py` / `schemas.py` / `models.py`（models 原为空文件，本次补齐）
- OSS SDK 接入（阿里云 oss2）+ 开发期 LOCAL_UPLOAD_DIR 降级
- 上传四关校验：Authentication → Authorization → Tenant Validation → Input Validation
- 图片类型白名单 + 大小校验（≤5MB）+ 魔数校验
- file_objects 写入 + 租户隔离 key 前缀生成（`t/{tenant_id}/...`）
- 返回 `{object_key, url, mime, size}`（不含内部路径）

**Out of Scope**：视频上传（D-F7-D5 确认视频外链 URL，不做视频托管）、图片清理定时任务（后续独立任务）、病毒扫描。

**依赖**：无（所有其他子 Feature 依赖本 Feature）。

**Required Agents**：
- **database-engineer**（迁移 SQL、约束、索引、rollback）
- **backend-engineer**（upload 四件套、OSS 接入、四关校验）
- **architect**（方案复核、与 MCP Tool 边界确认）

**Tasks**：
1. **DB 迁移**（database-engineer）
   - `alembic revision` 生成 3 份迁移文件
   - classrooms 扩展：code/location/cover_image_url + 回填 + 唯一约束
   - file_objects 建表
   - home_configs 建表 + 索引
   - 编写 rollback（down_revision）逻辑，确保迁移可回滚
   - 在 staging 环境验证 up + down 均成功

2. **Upload Models**（backend-engineer）
   - 补齐 `modules/upload/models.py`：FileObject ORM 模型（TenantMixin + file_objects 表）
   - 确认 models 被 `app/models.py` 汇总导入（影响 Alembic autogenerate）

3. **Upload Repository**（backend-engineer）
   - `FileObjectRepository(TenantAwareRepository[FileObject])`
   - 方法：create、soft_delete、list_by_biz_type、find_by_object_key

4. **Upload Service**（backend-engineer）
   - `ImageUploadService`：
     - 四关校验（authz 用 `@require_permissions("upload:create")` 或直接在 service 里判断登录态即可，上传接口面向已登录用户，不区分角色）
     - 魔数校验（`imghdr` 或 `filetype` 库，不信任扩展名）
     - 大小校验（MAX_IMAGE_SIZE = 5MB）
     - key 生成：`t/{tenant_id}/{biz_type}/{uuid4}_{timestamp}.{ext}`
     - OSS 上传（生产）/ 本地落盘（开发期 LOCAL_UPLOAD_DIR）
     - 写入 FileObject
   - StorageBackend 策略：`STORAGE_BACKEND=local|oss`（从环境变量读），生产强制 oss，local 仅开发可用

5. **Upload Router**（backend-engineer）
   - `POST /api/v1/upload/image` → `upload_image(biz_type: str)`
   - 依赖 `get_current_user` + `db: AsyncSession` + 租户上下文
   - 权限：任何已登录用户可上传（F7.0.1 阶段先放开，后续可细粒度限制）
   - 响应：`{"object_key": "...", "url": "...", "mime": "...", "size": ...}`
   - 错误处理：类型错 / 大小错 / 上传失败 → 友好消息，不暴露内部路径

6. **Schemas**（backend-engineer）
   - `UploadImageResponse(object_key, url, mime, size)`
   - Upload 请求走 `UploadFile`（FastAPI 原生），不需单独 Request DTO

7. **配置与部署**（backend-engineer + 运维确认）
   - `.env.example` 新增：`STORAGE_BACKEND`、`OSS_BUCKET`、`OSS_ENDPOINT`、`OSS_ACCESS_KEY_ID`、`OSS_ACCESS_KEY_SECRET`、`OSS_REGION`、`LOCAL_UPLOAD_DIR`
   - docker-compose 开发环境挂载 `LOCAL_UPLOAD_DIR` 到容器
   - Nginx / StaticFiles 配置本地文件服务（开发期）

8. **OpenAPI 同步**
   - 确认 router 被主 app 注册
   - `pnpm gen:types` 生成 api-types

**开发期 vs 生产切换方案**：
- 环境变量 `STORAGE_BACKEND=local`：文件落盘到 `LOCAL_UPLOAD_DIR`，后端拼 URL 时返回 `/static/uploads/...`，Nginx 反代到本地目录
- 环境变量 `STORAGE_BACKEND=oss`（生产强制）：文件上传到阿里云 OSS，后端拼 URL 时返回 `https://{bucket}.{endpoint}/{object_key}`，或私有 bucket + 签名 URL
- 切换逻辑集中在 `UploadService` 内部，前端零感知

**验收概要**：
- [ ] `alembic upgrade head` 在 staging 成功
- [ ] 上传 2MB jpg → 返回 object_key + url 可访问
- [ ] 上传 6MB jpg → 返回 400 + "图片大小不能超过 5MB"
- [ ] 上传 .exe → 返回 400 + "不支持的文件类型"
- [ ] 未登录上传 → 401
- [ ] 两个租户上传同名文件 → object_key 不同（租户前缀隔离）
- [ ] file_objects 表正确记录
- [ ] 开发期 local 存储 + 生产 OSS 存储 均验证通过

**风险**：
- OSS SDK 异步兼容性：项目用 httpx/asyncio，确认 oss2 SDK 的 async 支持或用线程池包装
- 迁移 rollback：classrooms 新增字段后若需回滚，已回填的 code 数据如何处理（rollback 直接 drop column 即可，保留回填逻辑在 upgrade 里）
- STORAGE_BACKEND 在生产被误设为 local：启动时做校验，生产环境（可通过 ENV=prod 判断）若为 local 则 panic

---

### F7.0.2 — Classroom 扩展

**Goal**：classrooms 表扩展后，后端 DTO/Service/Router 同步更新 + admin-web 教室管理页升级为卡片视图（含封面/编码/位置）。

**Scope**：
- 后端：classroom 模块扩展（schemas + service + router + repository）
- admin-web：`views/classrooms/index.vue` 卡片视图 + 新增/编辑弹窗（封面上传 + 编码 + 位置）
- 教室编码唯一性校验（后端 service 层 + 前端弹窗内 debounce 校验）
- 封面图占位（未设置/加载失败 → 「暂无图片」）

**Out of Scope**：原 classrooms 的 `status` 字段保留但前端不再展示（规格 D-F7-C1 已删除 status 概念但不做 DB drop）；容纳人数 `capacity` 不引入。

**依赖**：F7.0.1（DB 迁移 + upload 接口）。

**Required Agents**：
- **backend-engineer**（classroom DTO 扩展 + 编码唯一性校验）
- **frontend-engineer**（admin-web 卡片视图 + 弹窗 + 封面上传组件）
- **architect**（复核 service 层编码唯一校验逻辑是否正确）

**Tasks**：
1. **后端 DTO 扩展**（backend-engineer）
   - `modules/classroom/schemas.py`
   - `ClassroomCreate` + `ClassroomUpdate` + `ClassroomResponse` 均新增 `code: str`（必填）、`location: str | None`、`cover_image_url: str | None`
   - `code` 长度 50、regex 校验（可选，如 `^R-\d+$` 或宽松）

2. **后端 Service 扩展**（backend-engineer）
   - `ClassroomService.create()`：先查 tenant 内 code 是否已存在，重复抛 `HTTPException 409`
   - `ClassroomService.update()`：同上（排除自身 id）
   - 封面图 URL 由 upload 返回的 object_key 直接存入 `cover_image_url`（后端拼 URL 逻辑在 upload response 中已处理）

3. **后端 Router 确认**（backend-engineer）
   - 现有 `POST /classrooms` / `PATCH /classrooms/{id}` 路由已存在（`modules/classroom/router.py`），只更新 DTO 即可
   - 权限：已带 `@require_permissions`，确认 scope 覆盖新增字段

4. **OpenAPI 同步** + `pnpm gen:types`

5. **admin-web 卡片视图**（frontend-engineer）
   - 修改 `apps/admin-web/src/views/classrooms/index.vue`
   - 卡片新增：封面图（16:9，`el-image fit="cover"` + `error` 事件处理 → 占位）、名称 + 教室编码 tag、位置、设备
   - 移除原状态 tag（`正常/维护中`），因为前端不再展示 status

6. **admin-web 弹窗扩展**（frontend-engineer）
   - 新增字段：教室编码（必填 `el-input` + debounce 唯一性校验调用）、位置、封面图上传（复用 Upload 组件 → 调 `POST /upload/image` → 拿 `url` 回显）
   - 编码唯一性校验：前端 `watch` code 变化 → debounce 300ms → 调后端新增的 `GET /classrooms?code=xxx` 或专门校验接口（如果后端没提供则先查 list 过滤）

7. **OpenAPI 同步** + `pnpm gen:types`

**验收概要**：
- [ ] 新增教室（编码 R-001）成功 → 列表卡片显示编码 tag + 封面 + 位置
- [ ] 新增教室（编码重复）→ 409 错误提示「教室编码已存在」
- [ ] 未设置封面的教室 → 卡片显示「暂无图片」占位
- [ ] 封面 URL 失效的教室 → `onerror` 回退占位
- [ ] 编辑教室上传新封面 → 保存后卡片立即刷新

**风险**：
- 编码唯一性并发：Service 层需在事务内做「查询 → 插入」，或用 DB 唯一约束兜底。本项目已有 `uq_classrooms_tenant_code` 约束，即使并发撞车 DB 也会拒绝，Service 捕获 IntegrityError 转成友好消息
- 教室卡片视图数据量：当前教室数量小（培训机构通常 < 20 间），卡片网格 + 分页 `el-pagination` 够用

---

### F7.0.3 — User Avatar + Personal Profile

**Goal**：用户管理列表加头像列 + 新增/编辑弹窗加头像上传 + 右上角下拉加「个人资料」 + 个人资料弹窗。

**Scope**：
- admin-web `views/users/index.vue`：列表加头像列、弹窗加头像上传区
- admin-web `layout/AdminLayout.vue`：右上角下拉新增「个人资料」项
- 新增 `views/profile/index.vue`（或弹窗组件）：头像 + 昵称可编辑、手机号/角色只读
- 保存成功后同步 `authStore.adminInfo` 刷新顶部显示

**Out of Scope**：修改密码入口（D-F7-B3 本阶段不放）、手机号自助修改（D-F7-B2 只读）

**依赖**：F7.0.1（upload 接口）。**后端 users 模块的 `avatar_url` 字段 + `PATCH /auth/me` 白名单已存在**，不需要后端改动，纯前端任务。

**Required Agents**：
- **frontend-engineer**（唯一，因为后端已齐备）
- **architect**（复核后端 DTO 是否已覆盖所有场景，本次已核对 `UserCreate/Update/Response` 均有 `avatar_url`，`PATCH /auth/me` 白名单含 `nickname + avatar_url`）

**Tasks**：
1. **用户列表头像列**（frontend-engineer）
   - 修改 `apps/admin-web/src/views/users/index.vue`
   - 表格第一列插入「头像」：`el-avatar :src="row.avatar_url" :size="32"`，无值用默认 icon `UserFilled`

2. **头像上传组件**（frontend-engineer）
   - 抽公共组件（如 `components/ImageUploader.vue`），被 users 弹窗、profile 弹窗、classroom 弹窗共用
   - 状态机：idle → preview → uploading → success；异常：format-error / size-error / upload-fail(retry)
   - 行为：点击选择 → `FileReader` 本地预览 → 调 `POST /upload/image` → 拿返回的 `url`/`object_key` → 设表单字段

3. **用户新增/编辑弹窗**（frontend-engineer）
   - 新增头像上传区组件
   - 新增场景：先上传 → 拿到 `avatar_url` → 随表单提交 `POST /users`
   - 编辑场景：上传即暂存组件内部，点「确定」才 `PATCH /users/{id}`（取消时不覆盖原头像）

4. **AdminLayout 右上角扩展**（frontend-engineer）
   - `apps/admin-web/src/layout/AdminLayout.vue`
   - 下拉菜单新增「个人资料」项（保留原「退出登录」）
   - 顶部头像改为动态：`:src="authStore.adminInfo?.avatar"`（当前是硬编码 icon）

5. **个人资料弹窗**（frontend-engineer）
   - 新建 `components/ProfileDialog.vue`（或独立页面）
   - 展示：头像（可点更换 → 调 upload）、昵称（`el-input`）、手机号（disabled）、角色（`el-tag` 只读）
   - 保存：`PATCH /auth/me` → 成功后调 `authStore.fetchAdminInfo()` 刷新 adminInfo → 顶部头像/昵称即时更新
   - 错误：`ElMessage.error` 行内提示，不关闭弹窗

6. **路由**：无需新增路由（个人资料用弹窗形式而非独立页面）

**验收概要**：
- [ ] 用户管理列表：每行有头像列（无值显示默认 icon）
- [ ] 新增用户：上传头像 → 提交 → 列表显示头像
- [ ] 编辑用户：换头像 → 取消 → 重新打开 → 原头像仍在
- [ ] 右上角头像：显示当前用户头像（首次登录后 `fetchAdminInfo` 已拉取）
- [ ] 个人资料：改昵称 → 保存 → 顶部昵称同步更新
- [ ] 个人资料：手机号不可编辑
- [ ] 个人资料：上传头像 → 保存 → 顶部头像同步更新

**风险**：
- `authStore.adminInfo?.avatar` 字段名：当前 store 里是 `avatar?`（optional），确认 upload 返回的 URL 直接赋值即可
- 多个弹窗共用 `ImageUploader` 组件时的取消语义：每个弹窗维护自己的暂存状态，关闭时不回写业务数据

---

### F7.0.4 — Home Config 后端模块

**Goal**：home-config 四件套落地，draft/published 分离机制、发布原子操作、版本快照、小程序读取接口、租户隔离。

**Scope**：
- `modules/home_config/` 四件套：models.py / repository.py / service.py / schemas.py / router.py（新增整个模块目录）
- 7 个后端接口（solution-design.md §6.1 编号 6~9 + 重排序）：
  - `GET /api/v1/home-config/draft`（新增）
  - `PUT /api/v1/home-config/draft`（新增）
  - `PATCH /api/v1/home-config/draft/reorder`（新增，批量重排序）
  - `GET /api/v1/home-config/preview`（新增，读 draft）
  - `POST /api/v1/home-config/publish`（新增，原子写 published 快照）
  - `GET /api/v1/home-config/published`（新增，小程序读已发布配置，TenantAware）
  - `GET /api/v1/home-config/default`（可选，首次无 draft 时返回默认 5 模块骨架）
- home_configs 表 Repository 继承 TenantAwareRepository
- 发布版本模型 + 乐观锁（version 字段）
- 并发发布保护（两人同时发布的场景）

**Out of Scope**：模块类型增删（固定 5 类）、自动推荐算法、视频文件托管。

**依赖**：F7.0.1（DB 迁移）。

**Required Agents**：
- **backend-engineer**（home-config 四件套、draft/published 逻辑、发布事务）
- **database-engineer**（home_configs 表已在 F7.0.1 迁移，复核 JSONB 结构设计）
- **architect**（发布并发保护方案、JSONB schema_version 兼容设计、与 miniapp 的数据契约）

**Tasks**：
1. **Models**（backend-engineer）
   - `HomeConfig` ORM 模型（TenantMixin + home_configs 表）
   - scope 枚举：DRAFT / PUBLISHED
   - payload 字段 JSONB

2. **Repository**（backend-engineer）
   - `HomeConfigRepository(TenantAwareRepository[HomeConfig])`
   - 方法：
     - `get_by_scope(scope)` — 按 scope 查当前租户配置
     - `get_latest_published()` — 查当前租户 version 最大的 published
     - `upsert_draft(payload)` — draft upsert
     - `create_published_snapshot(payload, operator_id)` — 新建 published 记录，version = max_version + 1
     - `reorder_modules(module_type_to_sort: dict)` — 在 JSONB 内更新 sort 值（或由 service 层先解析再整体写入）

3. **Service**（backend-engineer）
   - `HomeConfigService`：
     - **draft 逻辑**：读 → 写 → 重排序。draft 始终 1 份，PUT 整体覆盖。PATCH reorder 解析 payload → 重写 modules 的 sort 字段为 1..n → PUT 回整份 draft
     - **publish 逻辑**（核心事务）：
       ```
       1. BEGIN TRANSACTION
       2. READ draft payload (tenant 内唯一)
       3. 校验 payload 结构（schema_version 可识别、必填模块字段齐全）
       4. 查当前 max published version → new_version = max + 1
       5. INSERT published record (scope=PUBLISHED, version=new_version, payload=draft_payload, published_at=NOW(), operator_id)
       6. COMMIT
       7. 乐观锁：若步骤 5 因 UNIQUE(tenant_id, scope, version) 冲突失败 → 说明并发发布 → 回滚 → 返回 409 + "有人先发布了，请刷新后重试"
       ```
     - **preview 逻辑**：直接返回 draft payload，标注 `is_preview=true`，前端按需区分
     - **published 读取**：TenantAware + 取 version 最大的 published

4. **Schemas**（backend-engineer）
   - `HomeConfigDraftPayload`：`schema_version: int` + `modules: list[ModuleConfig]`
   - `ModuleConfig`（Union，按 type 区分）：
     - `BannerModuleConfig`：type/banner/items[]
     - `TeachersModuleConfig`：type/teachers/limit/teacher_ids[]
     - `CoursesModuleConfig`：type/courses/limit/course_ids[]/sort_rule
     - `VideoModuleConfig`：type/video/items[]
     - `NoticeModuleConfig`：type/notice/title/content/image_key/valid_from/valid_to/enabled
   - `PublishResponse(version, published_at)`
   - `PublishedHomeConfig(payload, version, published_at)`（给小程序的响应）

5. **Router**（backend-engineer）
   - 注册 `/api/v1/home-config/` 前缀路由
   - 依赖 `get_current_user` + `TenantContext`
   - 权限：
     - draft/preview/publish：需要 `require_permissions("home-config:write")`（管理员角色）
     - published：需要 `get_current_user`（小程序已登录学员可访问，D-F7-E6）
   - **⚠️ 注意路由前缀**：solution-design.md §6.1 用的 `/miniapp-home/`，但实际命名应保持与现有模块一致的 snake_case 风格。建议实际路径 `/home-config/`，前端 miniapp 调用时按实际路径配置。**这是一个需要在开发前统一的命名决策点**。

6. **JSONB schema_version 兼容设计**
   - 每次 PUT draft 时写入顶层 `schema_version: 1`
   - GET 时检查 schema_version，若 < 当前版本号则做迁移适配（预留钩子函数 `_migrate_payload(old_payload)`）
   - 发布时同样检查，只发布当前版本的 payload

7. **OpenAPI 同步** + `pnpm gen:types`

**验收概要**：
- [ ] `PUT /home-config/draft` 写入 5 模块 → `GET /home-config/draft` 返回相同 payload
- [ ] `PATCH /home-config/draft/reorder` 传 `{"banner":2, "teachers":1}` → draft 内 teachers.sort=1, banner.sort=2
- [ ] `GET /home-config/preview` 返回 draft payload + `is_preview: true`
- [ ] `POST /home-config/publish` → published 新增记录（version=1），draft 不变
- [ ] 再次 publish → published version=2，version=1 记录仍保留
- [ ] `GET /home-config/published` 小程序端调 → 返回 version=2 的 payload
- [ ] 两个租户：tenant A 的 draft 与 tenant B 完全隔离，互不影响
- [ ] 并发 publish（两个管理员同时发布）→ 一个成功 version=N，另一个 409

**风险**：
- **路由命名不一致**：solution-design.md 用 `/miniapp-home/`，实际注册时需与项目现有模块（classroom, course, membership）保持 `/api/v1/<module-name>/` 风格。建议开发前统一为 `/home-config/`。
- **JSONB 解析/校验开销**：每次 publish 需解析完整 payload 做结构校验，当前 5 模块规模可接受（payload 预期 < 10KB）。
- **并发发布的乐观锁边界**：version 自增靠 DB UNIQUE 约束兜底，高并发下可能有多次冲突，但发布是低频操作，409 重试 1~2 次即可。

---

### F7.0.5 — Home Config admin-web 前端

**Goal**：admin-web 新增「小程序首页」一级导航，实现模块列表 + 5 种配置抽屉 + 预览 + 发布。

**Scope**：
- admin-web 左侧导航新增「小程序首页」项（路由 `/home-config`）
- 模块列表页：拖拽排序（HTML5 原生 drag 或 vuedraggable）、启用开关、编辑入口、状态徽标（草稿未发布 / 已发布 / 有未发布变更）
- 5 种模块配置共用抽屉壳，内部表单随 type 切换：
  - banner：图片上传 + 标题 + 副标题 + 跳转目标（枚举：课程详情 / 课程列表 / 视频 / 无跳转）
  - teachers：模块标题 + 展示数量（1-12）+ 教师多选（数据源 `GET /teachers`）
  - courses：模块标题 + 展示数量 + 课程多选 + 排序规则（手动顺序 / 最新）
  - video：模块标题 + 视频标题 + 封面图上传 + 视频地址 URL + 跳转目标
  - notice：模块标题 + 标题 + 内容 + 图片（可选）+ 有效期（起止 datetime）+ 启用
- 预览页：手机壳内复刻 miniapp 学员端首页（定位导航栏 / Banner / 师资 / 课程 / 视频 / TabBar），读 draft 实时渲染
- 发布确认弹窗 + 发布结果（成功 / 失败保留旧版）

**Out of Scope**：自由拖拽搭建器（固定 5 模块，D-F7-D3）。

**依赖**：F7.0.1（upload 接口）、F7.0.4（home-config 后端接口）。**F7.0.5 的 UI 骨架可在 F7.0.4 接口就绪前并行开发（用 Mock 数据），但完整联调需等 F7.0.4 完成**。

**Required Agents**：
- **frontend-engineer**（admin-web 全部新增页面）
- **architect**（手机壳预览复刻 miniapp 首页的实现方案）

**Tasks**：
1. **路由与导航**（frontend-engineer）
   - `router/index.ts` 新增 `/home-config` 路由 → 组件 `views/home-config/index.vue`
   - `AdminLayout.vue` 左侧导航插入「小程序首页」项（位置：排在现有业务域导航之后，或按产品最终确认的顺序）
   - 面包屑：「小程序首页」

2. **模块列表页**（frontend-engineer）
   - 加载：`GET /home-config/draft` → 渲染模块列表
   - 状态徽标：
     - 草稿未发布：无 published 记录 → 徽标「从未发布」
     - 有未发布变更：draft.updated_at > published.updated_at → 徽标「有未发布变更」
     - 已发布：draft.updated_at <= published.updated_at → 徽标「最新已发布 vN」
   - 拖拽排序：HTML5 `draggable` + dragstart/dragover/drop → 放下后重写 sort 值为 1..n → `PATCH /home-config/draft/reorder`
   - 启用开关：`el-switch @change → PUT /home-config/draft`（整体覆盖）
   - 编辑按钮 → 打开对应类型的配置抽屉

3. **配置抽屉壳**（frontend-engineer）
   - 公共 `el-drawer`（size 560px），内部 `<component :is="formComponent" />` 按 module.type 动态渲染
   - 底部按钮：「保存草稿」→ PUT draft 整体覆盖；「取消」→ 关闭不保存

4. **5 种表单组件**（frontend-engineer）
   - `BannerForm.vue`：BannerItems 数组（每项含图片上传 + 标题 + 副标题 + 跳转目标下拉）
   - `TeachersForm.vue`：教师多选（数据源 `teacherApi.list()`）+ 展示数量
   - `CoursesForm.vue`：课程多选 + 展示数量 + 排序规则
   - `VideoForm.vue`：视频标题 + 封面上传 + 视频地址 input + 跳转目标
   - `NoticeForm.vue`：标题 + 内容（el-input type=textarea）+ 图片上传（可选）+ 有效期（el-date-picker daterange）+ 启用开关

5. **预览页（手机壳内复刻 miniapp 首页）**（frontend-engineer）
   - 新页面 `/home-config/preview`（或弹窗形式）
   - 手机壳：375×667 灰色圆角边框 + 顶部状态栏
   - 内部复刻 `apps/miniapp/src/pages/student/courses/index.vue` 的模板结构：
     - AppNavbar（自定义导航栏 + 定位选择器）
     - Banner swiper
     - Teachers 横向滚动列表
     - Courses 网格
     - Videos 区域
     - HomeTabBar（4 Tab：首页/排期/AI 助手/我的）
   - 数据来源：`GET /home-config/preview`（读 draft），按 module.enabled 和 module.sort 渲染
   - 模块隐藏：enabled=false 或 items 为空 → 整个 section 不渲染（D-F7-E4 静默隐藏）
   - 图片占位：`onerror` → 统一占位图（D-F7-E7）

6. **发布确认与发布结果**（frontend-engineer）
   - 工具栏「发布」按钮 → `ElMessageBox.confirm`（二次确认 + 列出将发布的模块清单）
   - 确认后 `POST /home-config/publish` → 成功（显示 version + published_at）/ 失败（显示错误原因，提示保留旧版）
   - 成功后刷新 draft 状态徽标

**验收概要**：
- [ ] 左侧导航出现「小程序首页」
- [ ] 模块列表：拖拽 banners 到排序第 2 → 刷新 → teachers 排第 1，banners 排第 2
- [ ] 编辑 banner 抽屉：上传图片 → 保存草稿 → 模块列表 banner 模块摘要更新
- [ ] 启用 notice 模块 → 发布 → 小程序端 GET published 能看到 notice
- [ ] notice 模块停用 → 发布 → 小程序端渲染时 notice 区块不出现（静默隐藏）
- [ ] 预览：手机壳内渲染效果与真实 miniapp 学员端首页视觉一致
- [ ] 发布：成功后徽标显示「最新已发布 v3」
- [ ] 并发发布（两个浏览器同时点发布）→ 一个成功，一个提示「有人先发布了，请刷新后重试」

**风险**：
- **拖拽排序实现**：HTML5 原生 drag 在 el-table/el-row 混合场景下体验一般，建议引入 `vuedraggable@next`（vuedraggable）简化实现。需在 admin-web `package.json` 新增依赖。
- **预览的双端同步**：admin-web 预览复刻 miniapp 首页 UI 需与 miniapp `pages/student/courses/index.vue` 模板保持一致，避免视觉偏差。后续若 miniapp 改布局（如新增 Tab），admin-web 预览需同步更新。

---

### F7.0.6 — Miniapp 首页改造

**Goal**：小程序学员端首页从硬编码 banners/videos 切到 `GET /home-config/published`，实现分级降级逻辑 + 公告/活动新模块。

**Scope**：
- 修改 `apps/miniapp/src/pages/student/courses/index.vue`：
  - 移除 `const banners = ref([...])` 硬编码（L252+）
  - 移除 `const videos = ref([...])` 硬编码（L225+）
  - 新增 `const homeConfig = ref(null)` + `loadPublishedHomeConfig()` 调 `GET /home-config/published`
  - 按 module.type / enabled / sort 动态渲染各模块 section
  - teachers / courses 仍走各自的真实 API（复用现有逻辑），但数量限制按 config 里的 limit 字段过滤
  - banner / video / notice 数据来自 published payload
- 分级降级逻辑（D-F7-E3）：
  - home-config 接口失败 → teachers/courses 继续走真实 API（不受影响）
  - banner/video/notice 模块用本地缓存副本（`uni.setStorageSync`），无缓存则静默隐藏
  - 模块 enabled=false 或 items 为空 → 整个 section 不渲染
- 公告/活动新模块 section 渲染（之前不存在）

**Out of Scope**：自由搭建器、视频文件托管、游客访问。

**依赖**：F7.0.4（home-config 后端 published 接口）。**miniapp 改造的静态清理（移除硬编码）可在 F7.0.4 就绪前先做，但接真实 API 联调需等 F7.0.4 完成**。

**Required Agents**：
- **frontend-engineer**（miniapp 端改造）
- **architect**（降级逻辑设计与实现方案复核）

**Tasks**：
1. **API 层新增**（frontend-engineer）
   - `apps/miniapp/src/api/index.ts` 新增 `homeApi.getPublishedHomeConfig()` → `GET /home-config/published`

2. **静态硬编码清理**（frontend-engineer）
   - 移除 `pages/student/courses/index.vue` L252+ `const banners = ref([...])`
   - 移除 L225+ `const videos = ref([...])`

3. **动态数据加载**（frontend-engineer）
   - `onLoad` / `onShow` 中：
     ```
     try {
       homeConfig.value = await homeApi.getPublishedHomeConfig()
       uni.setStorageSync('homeConfigCache', homeConfig.value)  // 缓存
     } catch (e) {
       homeConfig.value = uni.getStorageSync('homeConfigCache')  // 降级用缓存
     }
     ```
   - 模块渲染：遍历 `homeConfig.modules` → 按 `sort` 排序 → `v-if="enabled && items.length > 0"` 渲染

4. **Banner section 改造**（frontend-engineer）
   - `v-for="item in bannerModule.items"` → `imageUrl = item.image_key → 后端拼好的 url 或前端按 key 调 url`（取决于后端 published 接口返回的是 object_key 还是完整 url）
   - **⚠️ 约定**：`GET /home-config/published` 返回的 payload 中图片字段（image_key / cover_key）应是**后端拼好的完整可访问 URL**，而不是原始 object_key。这样 miniapp 不需要关心存储细节。这个约定需在 F7.0.4 的 Service 层实现。

5. **Teachers / Courses section 改造**（frontend-engineer）
   - 继续走 `teacherApi.list()` / `studentApi.getCourses()`
   - 按 config 里的 `teacher_ids` / `course_ids` 过滤 + `limit` 截取
   - 若接口失败 → 静默隐藏该 section（或退回全量展示，按产品确认）

6. **Video section 改造**（frontend-engineer）
   - 数据来自 `videoModule.items`（title + cover_key + video_url）
   - cover_key 由后端拼成完整 URL

7. **Notice section 新增**（frontend-engineer）
   - 条件渲染：notice module 存在 + enabled + content 非空
   - 展示：标题 + 内容（可展开/折叠）+ 图片（可选）+ 有效期（`valid_from ≤ now ≤ valid_to` 时才展示）

8. **降级逻辑收尾**（frontend-engineer）
   - home-config 接口 5xx 或超时 → banners/videos/notice 用缓存；teachers/courses 继续各自真实 API
   - home-config 接口 4xx（租户隔离问题等）→ 用缓存或静默隐藏
   - 模块 enabled=false 或 items 为空 → 整个 section 不渲染（D-F7-E4）

**验收概要**：
- [ ] 首页正常加载：5 模块按 sort 顺序渲染
- [ ] banner 图片从后端 published 读取，不是硬编码 unsplash
- [ ] video 数据来自后端，不是硬编码
- [ ] 管理员停用 banner → 发布 → miniapp 下次刷新 banner section 消失
- [ ] 管理员禁用 notice 但开启 banners → 发布 → miniapp 有 banner 无 notice
- [ ] home-config 接口 mock 失败 → banner/video/notice 用上次缓存，teachers/courses 正常展示
- [ ] 图片加载失败 → `onerror` 回退占位图
- [ ] 模块 enabled=false → 整个 section 不渲染（不出现空壳）

**风险**：
- **miniapp API 层命名**：当前 miniapp 有独立的 `apps/miniapp/src/api/index.ts`，不走 `packages/api-client`。新增 homeApi 需在该文件内扩展，与 Web 三端分离（符合 project_rules.md 的「两套 HTTP 客户端」规定）。
- **图片 URL 约定**：miniapp 的 image 组件需要完整可访问 URL。`GET /home-config/published` 返回 payload 时，后端 Service 层需将 object_key 拼成完整 URL 后再返回（与 upload 接口返回 url 的逻辑一致），而不是返回原始 object_key。这个约定必须在 F7.0.4 Service 实现时明确。
- **uni.setStorageSync 缓存容量**：小程序本地存储上限 10MB，home-config payload 预期 < 10KB，完全够。

---

## 五、Agent 分配矩阵

| 子 Feature | architect | backend-engineer | database-engineer | frontend-engineer | 说明 |
|------------|:---------:|:----------------:|:-----------------:|:-----------------:|------|
| **F7.0.1** DB + Upload | 复核方案 | upload 四件套 | 3 份迁移 SQL | — | 迁移是关键，database-engineer 需验证 up/down |
| **F7.0.2** Classroom 扩展 | 复核编码唯一逻辑 | classroom DTO/service/router | 迁移已在 F7.0.1 | admin-web 卡片+弹窗 | 依赖 F7.0.1 upload 接口 |
| **F7.0.3** User Avatar + Profile | 复核后端 DTO 覆盖 | —（后端已齐备） | — | admin-web 用户+布局+弹窗 | 纯前端，后端 avatar_url/PATCH /auth/me 已存在 |
| **F7.0.4** Home Config 后端 | 发布并发+JSONB 兼容 | home-config 四件套 | 迁移已在 F7.0.1 | — | 核心事务逻辑 |
| **F7.0.5** Home Config admin-web 前端 | 预览复刻方案 | — | — | admin-web 全部新增页 | 依赖 F7.0.4 接口 |
| **F7.0.6** Miniapp 首页改造 | 降级逻辑设计 | — | — | miniapp 端改造 | 依赖 F7.0.4 接口 |

---

## 六、实施顺序建议

```
Week 1 ── F7.0.1 (DB Migration + Upload 模块)  【database + backend 协作】
         │
         ├─── F7.0.2 (Classroom 扩展)          【backend + frontend 并行】
Week 2 ── ├─── F7.0.3 (User Avatar + Profile)  【frontend 单域】
         └─── F7.0.4 (Home Config 后端)        【backend 单域】
                │
Week 3 ── F7.0.5 (Home Config admin-web 前端)  【frontend 联调 F7.0.4】
         │
Week 4 ── F7.0.6 (Miniapp 首页改造)            【frontend 联调 F7.0.4】
         │
         └─── 冒烟测试 + 全链路联调
```

**并行窗口**（Week 2）：F7.0.2 / F7.0.3 / F7.0.4 三路并行执行，因为修改的文件集完全无重叠：
- F7.0.2 → `modules/classroom/*` + `views/classrooms/index.vue`
- F7.0.3 → `views/users/index.vue` + `layout/AdminLayout.vue` + 新建 profile 相关组件
- F7.0.4 → 新建 `modules/home_config/*`（整个新目录）

**不建议并行的项**：F7.0.5 和 F7.0.6 虽然文件集不重叠，但都依赖 F7.0.4 的接口就绪才能联调。F7.0.5 可先写 UI 骨架（Mock 数据），但完整联调需等 F7.0.4 完成。

---

## 七、验收清单（端到端冒烟路径）

### 冒烟路径 1：上传全链路

```
[F7.0.1]
  1. curl -X POST /api/v1/upload/image -F "file=@avatar.jpg" -F "biz_type=avatar"
     → 返回 {object_key: "t/1/avatar/u_5_1729999999.jpg", url: "https://oss...", mime, size}
  2. DB: SELECT * FROM file_objects → 有对应记录，tenant_id 正确
  3. DB: SELECT object_key FROM file_objects WHERE biz_type='avatar' AND tenant_id=1 → 正确
  4. 访问返回的 url → 浏览器/小程序可看到图片
  5. 上传 6MB 文件 → 400 "图片大小不能超过 5MB"
  6. 上传 .exe → 400 "不支持的文件类型"
```

### 冒烟路径 2：教室扩展

```
[F7.0.1 → F7.0.2]
  1. admin-web → 教室管理 → 新增
     - 填 code=R-101, name=爵士厅, 上传封面, location=3 楼
     - POST /classrooms → 201
  2. 教室管理列表 → 卡片显示封面 + 编码 tag「R-101」+ 位置
  3. 再新增 code=R-101 → 409 "教室编码已存在"
  4. DB: SELECT code, location, cover_image_url FROM classrooms → 字段正确存在
  5. 卡片封面为空 → 显示「暂无图片」占位
```

### 冒烟路径 3：用户头像 + 个人资料

```
[F7.0.1 → F7.0.3]
  1. admin-web → 用户管理 → 新增
     - 上传头像 → 提交 → 列表头像列显示刚上传的图
  2. 右上角头像 → 下拉「个人资料」→ 弹窗
     - 改昵称 → 保存 → 顶部昵称即时更新
     - 换头像 → 保存 → 顶部头像即时更新
     - 手机号 disabled 不可编辑
```

### 冒烟路径 4：首页配置 → 发布 → 小程序渲染（主链路）

```
[F7.0.1 → F7.0.4 → F7.0.5 → F7.0.6]  核心冒烟路径
  1. admin-web → 小程序首页 → 模块列表
     - 默认 5 模块骨架（GET /home-config/draft 返回空/默认 → PUT 写入）
  2. 编辑 banner → 上传 3 张 banner 图 + 标题 → 保存草稿
  3. 编辑 teachers → 勾选 6 位老师 → 保存草稿
  4. 编辑 courses → 勾选 4 门课程 → 保存草稿
  5. 编辑 video → 上传封面 + 填视频 URL → 保存草稿
  6. 编辑 notice → 写标题 + 内容 → 启用 → 保存草稿
  7. 拖拽排序 teachers 到第 1 位 → PATCH reorder → sort 更新为 teachers=1, banner=2, courses=3, video=4, notice=5
  8. 预览 → 手机壳内渲染 5 模块，顺序正确
  9. 发布 → POST /home-config/publish → 成功 → version=1
  10. miniapp → 学员端首页 → 加载 home-config
      - teachers 排第 1（横向滚动 6 人）
      - banner 排第 2（swiper 3 张）
      - courses 排第 3（4 门）
      - video 排第 4（封面 + 标题 + 外链）
      - notice 排第 5（标题 + 内容）
  11. admin-web → 停用 notice → 发布 version=2
      - miniapp 下次刷新 → notice section 消失（静默隐藏）
  12. miniapp → 断网 mock home-config 失败
      - banner/video/notice 用上次缓存
      - teachers/courses 各自真实 API 仍可能成功（视 mock 粒度）
```

### 冒烟路径 5：租户隔离

```
[F7.0.2 + F7.0.4]
  1. 租户 A（tenant_id=1）创建教室 code=R-001 → 成功
  2. 租户 B（tenant_id=2）创建教室 code=R-001 → 也成功（租户内唯一，跨租户不冲突）
  3. 租户 A 写 draft → 发布 version=1
  4. 租户 B 写 draft（独立的 5 模块，完全不同内容）→ 发布 version=1
  5. 租户 A 的 miniapp → GET /home-config/published → 返回租户 A 的配置
  6. 租户 B 的 miniapp → GET /home-config/published → 返回租户 B 的配置
```

---

## 八、硬约束与必须遵守的规则

### 分层红线（从 project_rules.md）

```
Router → Service → Repository → DB          ✅ 必须遵守
HTTP /ai/chat → AgentRuntime → MCP Tool → Service → Repository → DB  ✅ 必须遵守

禁止:
  Router → DB
  MCP Tool → Repository / DB
  前端 → DB / Redis / 绕过 HTTP API
```

### 安全红线

- **四关校验顺序**：Authentication → Authorization → Tenant Validation → Input Validation（MCP Tool 和 upload 接口均须遵守）
- **密钥不硬编码**：OSS_ACCESS_KEY 只能来自 `.env.*`，禁止 commit 进仓库
- **响应不泄露内部信息**：错误消息不得包含主机名/SQL/堆栈
- **PATCH /auth/me 白名单**：仅 nickname + avatar_url，不得扩大范围（已冻结 D-F7-B1/B2）

### 租户隔离红线

- Repository 必须继承 `TenantAwareRepository`（`core/base_repository.py:396`）
- 禁止在业务表查询中手动拼 tenant_id（会与 ORM 自动注入对抗）
- 绝不信任请求体里的 tenant_id

### 前端红线

- 前端禁止调用后端不存在的端点（候选接口开发前须逐一对齐）
- Web 三端走 `packages/api-client`，miniapp 走 `apps/miniapp/src/api/index.ts`，**不得新增第三套请求层**
- 接口契约变更必须同步评估 4 端影响面

---

## 九、附录：候选接口与现有接口对照

| # | 接口 | 方法 | 性质 | 子 Feature | 备注 |
|---|------|------|------|-----------|------|
| 1 | `/api/v1/upload/image` | POST | **新增** | F7.0.1 | 四关校验 + 类型/大小校验 |
| 2 | `/api/v1/users/{id}` | PATCH | **复用** | F7.0.3 | `UserUpdate` 已含 `avatar_url` |
| 3 | `/api/v1/users/` | POST | **复用** | F7.0.3 | `UserCreate` 已含 `avatar_url` |
| 4 | `/api/v1/auth/me` | GET / PATCH | **复用** | F7.0.3 | 白名单 nickname+avatar |
| 5 | `/api/v1/classrooms` | POST / PATCH | **扩展** | F7.0.2 | 新增 code/location/cover_image_url |
| 6 | `/api/v1/home-config/draft` | GET / PUT | **新增** | F7.0.4 | 整份 draft 读写 |
| 6.1 | `/api/v1/home-config/draft/reorder` | PATCH | **新增** | F7.0.4 | 批量重排序 |
| 7 | `/api/v1/home-config/preview` | GET | **新增** | F7.0.4 | 读 draft + 标注 is_preview |
| 8 | `/api/v1/home-config/publish` | POST | **新增** | F7.0.4 | 原子写 published 快照 |
| 9 | `/api/v1/home-config/published` | GET | **新增** | F7.0.4 | 小程序读已发布配置 |
| 10 | `/api/v1/teachers`、`/api/v1/courses` | GET | **复用** | F7.0.4 + F7.0.6 | 师资/课程数据源 |

**⚠️ 路由命名提醒**：solution-design.md 中接口 6~9 用 `/miniapp-home/` 前缀，但项目现有模块风格为 `/api/v1/<snake_case>/`（classroom, course, membership）。开发前须统一决定：
- 选项 A：保持 `/home-config/`（推荐，与现有模块命名一致）
- 选项 B：保持 `/miniapp-home/`（与 miniapp 语义更贴近但与项目风格不一致）

此决策不影响业务逻辑，仅影响路由注册位置和前端调用路径。

---

## 十、附录：JSONB payload schema_version 设计

home_configs.payload 顶层预留 schema_version：

```json
{
  "schema_version": 1,
  "modules": [
    {
      "type": "banner",
      "enabled": true,
      "sort": 1,
      "title": "Banner 轮播",
      "items": [
        {"image_key": "t/1/banner/xxx.jpg", "title": "...", "subtitle": "...", "link_type": "course_detail", "link_id": 12}
      ]
    },
    {
      "type": "teachers",
      "enabled": true,
      "sort": 2,
      "title": "师资团队",
      "limit": 6,
      "teacher_ids": [3, 5, 7, 8, 12, 15]
    },
    {
      "type": "courses",
      "enabled": true,
      "sort": 3,
      "title": "推荐课程",
      "limit": 4,
      "course_ids": [8, 9, 11, 14],
      "sort_rule": "manual"
    },
    {
      "type": "video",
      "enabled": true,
      "sort": 4,
      "title": "舞动 · 让生活更美好",
      "items": [
        {"title": "...", "cover_key": "t/1/video_cover/xxx.jpg", "video_url": "https://...", "link_type": "none"}
      ]
    },
    {
      "type": "notice",
      "enabled": false,
      "sort": 5,
      "title": "公告",
      "content": "...",
      "image_key": null,
      "valid_from": "2026-11-01T00:00:00Z",
      "valid_to": "2026-12-31T23:59:59Z"
    }
  ]
}
```

**版本兼容钩子**（Service 层）：

```python
async def _migrate_payload_if_needed(self, payload: dict) -> dict:
    """schema_version 迁移钩子，目前无迁移逻辑，预留 schema_version=2 时扩展"""
    current_version = payload.get("schema_version", 1)
    target_version = 1
    if current_version < target_version:
        # 未来版本迁移逻辑
        pass
    payload["schema_version"] = target_version
    return payload
```

**未来扩展**：当新增模块类型（如「会员权益」section）或调整现有模块结构（如 banner 支持多图切换间隔配置）时，schema_version 递增 + 在 migrate 钩子中补默认值，保证旧版 draft 数据可读。

---

## 十一、附录：开发期 vs 生产 Upload 切换方案

```
# .env 配置示例

# 开发期
STORAGE_BACKEND=local
LOCAL_UPLOAD_DIR=/Users/dev/uploads
# OSS 相关变量开发期可留空

# 生产（强制 OSS）
STORAGE_BACKEND=oss
OSS_BUCKET=dance-saas-prod
OSS_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
OSS_ACCESS_KEY_ID=AK_xxx
OSS_ACCESS_KEY_SECRET=SK_xxx
OSS_REGION=cn-hangzhou
```

**启动校验**（在 FastAPI lifespan 或 upload service 初始化时）：

```python
import os
env = os.getenv("ENVIRONMENT", "development")
storage_backend = os.getenv("STORAGE_BACKEND", "local")

if env == "production" and storage_backend != "oss":
    raise RuntimeError(
        f"PRODUCTION environment requires STORAGE_BACKEND=oss, got {storage_backend}"
    )
```

**UploadService 内部策略模式**：

```python
class UploadService:
    def __init__(self, storage_backend: str):
        if storage_backend == "local":
            self._storage = LocalStorageBackend(LOCAL_UPLOAD_DIR)
        elif storage_backend == "oss":
            self._storage = OssStorageBackend(bucket=..., endpoint=..., access_key=...)
        else:
            raise ValueError(f"Unknown storage backend: {storage_backend}")

    async def upload(self, ...) -> str:
        object_key = self._generate_object_key(tenant_id, biz_type)
        await self._storage.put(file_content, object_key)
        url = self._storage.public_url(object_key)  # 统一返回完整可访问 URL
        return FileObject(object_key=object_key, url=url, ...)
```

**前端零感知**：无论后端用 local 还是 oss，`POST /upload/image` 返回的 `url` 字段都是浏览器/小程序可直接访问的完整 URL，前端不需要关心存储细节。

---

*文档结束。实施前请确认：路由命名（`/home-config/` vs `/miniapp-home/`）、OSS SDK async 兼容、迁移 head revision。*
