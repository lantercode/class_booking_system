# OSS 文件上传系统接入 —— 第一阶段只读审计报告

> 审计日期：2026-10-27
> 审计范围：`apps/api`、`apps/admin-web`、`apps/student-web`、`apps/teacher-web`、`apps/miniapp`、`packages/api-client`、`infra/`、`.github/workflows/`、`docs/`
> 审计方式：只读。未修改任何代码、未安装依赖、未执行迁移、未操作阿里云资源。
> 风险分级：**L4**（跨模块 + 存储基础设施 + 多端 + 权限/租户）

---

## 1. 仓库结构与入口

| 项 | 位置 |
|---|---|
| Monorepo | `pnpm-workspace.yaml`：`apps/*` + `packages/*` |
| 后端入口 | [main.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/main.py)（`app/main.py`，lifespan 管理 Redis/定时任务/OSS 客户端） |
| 后端目录 | `apps/api/src/app/{core,modules,ai,middleware,deps,shared}` |
| 迁移 | `apps/api/alembic/versions/`（共 40+ 个版本，命名 `<hash>_<desc>.py`） |
| 管理端 | `apps/admin-web`（Vue3 + Element Plus + Pinia） |
| 学员端 Web | `apps/student-web` |
| 教师端 Web | `apps/teacher-web` |
| 小程序 | `apps/miniapp`（uni-app / mp-weixin，**npm 非 pnpm**） |
| 共享包 | `packages/api-client`（axios + 401 refresh + `x-tenant-slug`）、`packages/api-types`（OpenAPI 生成） |
| 部署 | `infra/docker/docker-compose.yml`（dev）、`docker-compose.prod.yml`（prod）、`infra/nginx/`、`apps/api/Dockerfile` |
| CI | `.github/workflows/ci.yml`、`deploy.yml` |

---

## 2. 图片相关数据模型（现状）

| 业务对象 | 字段 | 定义位置 | 语义注释 | 实际存入值 |
|---|---|---|---|---|
| 用户头像 | `users.avatar_url` `String(500)` | [user/models.py#L39](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/user/models.py#L39) | 无注释 | **混用**：admin-web 个人资料存 object_key；用户管理页存完整 URL |
| 微信账号头像 | `wechat_accounts.avatar_url` `String(255)` | [auth/models.py#L87](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/auth/models.py#L87) | 无 | 微信同步，**与 users.avatar_url 无同步逻辑** |
| 教师头像 | **无独立字段** | `teacher_profiles` 表无头像列 | — | 由 `users.avatar_url` 借读：[teacher/service.py#L50](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/teacher/service.py#L50)、L81、L144 |
| 课程封面 | `courses.cover_url` `String(500)` | [course/models.py#L146](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/course/models.py#L146) | **"封面图URL"** | 无上传入口，仅能由接口直接传字符串 |
| 教室封面 | `classrooms.cover_image_url` `String(500)` | [course/models.py#L25](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/course/models.py#L25) | **"封面 object_key"** | admin-web 存 object_key ✅ |

**结构性发现**：`Classroom` 模型定义在 `course/models.py`，而 `modules/classroom/` 目录**没有 models.py**（只有 router/service/repository/schemas）。修改教室封面字段时须注意模型归属不在 classroom 模块内。

---

## 3. 文件元数据表 `file_objects`

- 模型：[upload/models.py#L17-L49](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/upload/models.py#L17-L49)
- 迁移：[e5f6a7b8c9d0_create_file_objects_table.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/alembic/versions/e5f6a7b8c9d0_create_file_objects_table.py)
- 字段：`id`、`tenant_id`(FK tenants.id)、`object_key String(500)`、`mime`、`size`、`biz_type`、`uploader_id`、`created_at`、`deleted_at`
- 约束：`uq_file_objects_tenant_key (tenant_id, object_key)`、索引 `idx_file_objects_tenant_biz (tenant_id, biz_type)`

**结论**：**已有可复用的文件元数据表，无需新建表，无需新增迁移**（若仅补 `original_name`/`status` 则属可选增强，非必需）。

**缺口**：
- `deleted_at` 字段存在但**全项目无人写入**——没有删除接口，软删除形同虚设。
- 无 `original_name`（原始文件名）、无 `ref_count`/引用关系表。
- 业务表与文件的关联仅靠字符串 `object_key`，无外键、无唯一引用校验。

---

## 4. 上传链路现状（存在两套并存实现）

### 4.1 新体系（应作为唯一演进方向）

| 组件 | 位置 | 说明 |
|---|---|---|
| Router | [upload/router.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/upload/router.py) | `POST /api/v1/upload/image`（L23-62）+ `GET /api/v1/upload/url/{object_key}`（L65-96） |
| Service | [upload/service.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/upload/service.py) | 校验（MIME/扩展名/大小/魔数）→ 生成 key → local/oss 存储 → 写审计表 → 生成 URL |
| Repository | `upload/repository.py` | `FileObjectRepository`，继承 `TenantAwareRepository` |
| Schemas | [upload/schemas.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/upload/schemas.py) | `biz_type` 正则限定 `avatar\|classroom_cover\|banner\|video_cover\|notice` |
| OSS 客户端 | [core/oss_client.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/core/oss_client.py) | AsyncClient 单例 + `EcsRoleCredentialsProvider` + `presign_object_url` + `resolve_object_url` |

**能力清单**：5MB 上限、`image/jpeg|png|webp` 白名单、魔数校验、object_key = `t/{tenant_id}/{biz_type}/{uuid}.{ext}`、私有桶预签名（上限 7 天）、lifespan 释放客户端。

**权限现状（关键缺口）**：
```python
@require_roles("admin", "super_admin")   # upload/router.py L33
```
→ **教师、学员无法上传头像**。而旧 `/common/upload/image` 允许 `admin/super_admin/teacher/student`。

### 4.2 旧体系（技术债，必须清理）

| 组件 | 位置 | 问题 |
|---|---|---|
| Router | [common/router.py#L49-L104](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/common/router.py#L49-L104) | `POST /api/v1/common/upload/image`，2MB 上限、允许 GIF |
| Service | [core/oss/service.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/core/oss/service.py) | `AliyunOSSService` 依赖 `oss2` —— **该包未安装**（`pyproject.toml`/`uv.lock` 均无） |
| 工厂 | `get_oss_service()` L263-L294 | 读取 `OSS_PROVIDER` / `ALIYUN_OSS_*` —— **Settings 中根本不存在这些字段**，`getattr` 静默回落 `provider="local"` |
| 实际行为 | — | 落到 `LocalStorageService(storage_path="./uploads", base_url="http://localhost:8000/uploads")`，即**容器 cwd 下 `./uploads`**；返回**硬编码绝对 URL** |

### 4.3 其他现存缺口

- **无删除接口**：`file_objects` 无删除、无 `delete_object` 调用方（`core/oss/service.py` 有实现但未被路由使用）。
- **无图片解码校验**：只验魔数，未用 PIL 解码；**Pillow 未安装**，无法做尺寸/像素炸弹防护。
- **头像更新无归属校验**：`auth/service.py#L63` 只白名单 `nickname, avatar_url`，`user/service.py#L323` 直接写字段，**不校验该 object_key 是否由本人上传、是否属于本租户**。
- **无引用计数**：替换头像后旧对象不清理，也不判断是否被他人引用。

---

## 5. 认证 / 授权 / 租户

| 能力 | 位置 |
|---|---|
| `get_current_user` / `get_optional_user` | `app/deps/auth.py`（含 Redis 黑名单校验） |
| `require_roles` / `require_permissions` | `app/core/rbac.py`（权限缓存 `perms:{tenant_id}:{user_id}`，TTL 300s） |
| 租户上下文 | `app/core/tenant_context.py`；中间件 `app/middleware/tenant_middleware.py` |
| ORM 自动注入 | `app/core/tenant_query.py` `do_orm_execute` |
| `TenantAwareRepository` | `app/shared/base_repository.py` |
| `SKIP_TENANT_PATHS` | `tenant_middleware.py`，含 `/uploads`、`/health`、文档、登录注册等 |

**结论**：三层租户隔离完整可用，`/upload/url` 已做 `t/{tenant_id}/` 前缀校验（跨租户 403），这是可复用的正确模式。

---

## 6. 前端现状（4 端矩阵）

### 6.1 上传调用点（全部走 `commonApi.uploadImage` → `/api/v1/upload/image`）

| 端 | 页面 | 位置 | 存入业务字段的值 | 判定 |
|---|---|---|---|---|
| admin-web | 个人资料弹窗 | [AdminLayout.vue#L219-L231](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/layout/AdminLayout.vue#L219-L231) | `object_key` | ✅ 正确 |
| admin-web | 用户管理-编辑 | [students/index.vue#L383](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/students/index.vue#L383) | `res.data.url`（完整/相对 URL） | ❌ 错误 |
| admin-web | 教师管理-编辑 | [teachers/index.vue#L393](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/teachers/index.vue#L393) | `res.data.url` | ❌ 错误 |
| admin-web | 教室管理-封面 | [classrooms/index.vue#L298](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/classrooms/index.vue#L298) | `object_key` | ✅ 正确 |
| student-web | 个人资料 | `views/profile/index.vue` | 无上传入口 | — |
| teacher-web | 个人资料 | `views/profile/index.vue` | 无上传入口 | — |
| miniapp | 教师资料编辑 | [edit.vue#L114](file:///Users/lixiang/Desktop/class_booking_system/apps/miniapp/src/pages/teacher/profile/edit.vue#L114) | 仅 `uni.showToast('头像上传功能开发中')` | ❌ 未实现 |

> **这是 `D-F7.0-1` 技术债的准确根因**：两处存 URL、两处存 key，语义分裂。

### 6.2 展示端 URL 解析

| 端 | 解析函数 | 行为 |
|---|---|---|
| admin-web | [auth.ts#L20-L25](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/stores/auth.ts#L20-L25) `resolveAvatarUrl` | `object_key` → `/uploads/${key}`；已是 URL/绝对路径则原样 |
| admin-web | [classrooms/index.vue#L225-L230](file:///Users/lixiang/Desktop/class_booking_system/apps/admin-web/src/views/classrooms/index.vue#L225-L230) `resolveCoverUrl` | 同上 |
| student-web | `userStore.userInfo?.avatar` **直接绑定** | ❌ 无解析，本地模式下 object_key 直接当 src → 图片 404 |
| teacher-web | `authStore.teacherInfo?.avatar` **直接绑定** | ❌ 同上 |
| miniapp | `AppAvatar.vue` 支持 `src`，但页面多用文字首字母占位 | 无解析逻辑 |

### 6.3 API 层

- `packages/api-client/src/common.ts`：仅 1 个上传方法（FormData + `biz_type`），**无进度回调**、无删除方法。
- `packages/api-client` **没有** profile 更新方法；admin-web 内部另有调用（`auth.ts#L25` 注释表明存在"更新当前用户信息"）。
- `apps/miniapp/src/api/index.ts`：**无任何上传/文件方法**；`request` 封装基于 `uni.request`，不支持 multipart 文件流（需用 `uni.uploadFile` 另写）。
- `packages/api-types`：**无 upload 相关类型**（`UploadImageResponse` 是 api-client 手写接口）。

### 6.4 课程封面

admin-web `views/courses/` 中**完全没有封面相关 UI**（grep `cover_url|封面` 零命中）。`courses.cover_url` 目前只能通过接口传字符串，实际业务页面上无法设置。

---

## 7. 配置 / 部署 / CI / 测试

### 7.1 配置

- [.env.example#L47-L72](file:///Users/lixiang/Desktop/class_booking_system/.env.example#L47-L72) 已含完整 File Storage 段（`STORAGE_BACKEND`、`OSS_ENDPOINT/REGION/BUCKET/CREDENTIALS_MODE/ROLE_NAME/AK/SK/PUBLIC_BASE_URL`）。
- [config.py#L73-L127](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/core/config.py#L73-L127) 校验：生产禁 local；oss 模式必填 endpoint/region/bucket；`ecs_role` 必填 role name，`static` 必填 AK/SK。

### 7.2 部署（存在阻断级缺陷）

| 项 | 现状 | 影响 |
|---|---|---|
| `infra/docker/docker-compose.prod.yml` | `api` 服务 environment **只有** APP_ENV/DATABASE_URL/REDIS_URL/JWT/CORS/WECHAT，**无任何 STORAGE_BACKEND / OSS_* 注入** | 容器内 `STORAGE_BACKEND` 取默认 `local` + `APP_ENV=production` → **启动即 `RuntimeError`**（config.py L99-102） |
| `infra/docker/.env.prod.example` | 无 OSS 段 | 部署者无从得知要配什么 |
| `apps/api/Dockerfile` | `uv sync --frozen --no-dev` + `COPY . .` | **无上传目录 volume**；容器重建即丢文件（local 模式） |
| `infra/nginx/nginx.conf` | admin 域名 server 块**无 `client_max_body_size`**（默认 1M）；api 域名 20M；无 `/uploads` location | **5MB 头像经 admin 域名上传必 413**；local 模式图片完全无法访问 |
| `docker-compose.yml`（dev） | 同样无 STORAGE_* 注入 | 本地默认 local（可接受） |

### 7.3 CI

- `.github/workflows/ci.yml`：backend job 跑 `ruff` → mypy baseline → `alembic upgrade head` → `pytest tests/unit` → `pytest tests/integration`（排除 5 项存量债务）。
- **未设置 `STORAGE_BACKEND=oss`，也没有任何 OSS mock 测试**；上传链路 CI 覆盖为 **0**。
- frontend job：lint + build + type-check（不含 miniapp 上传验证）。

### 7.4 测试体系

- `apps/api/tests/conftest.py`：session 级 fixture 启动**真实 HTTP 服务器**（解决 asyncpg 事件循环冲突）+ 真实 PostgreSQL + Redis + 种子数据（租户 `dance-school`、角色、权限、用户）。
- `tests/unit/`：仅 4 个文件（模型、会员卡状态机、推荐、锁顺序）。
- `tests/integration/`：30 个文件，**没有任何 upload/图片/OSS 测试**。
- `pytest`：`asyncio_mode=auto`，`testpaths=["tests"]`。

### 7.5 健康检查

`GET /api/v1/common/health` 只检查 Redis，**不检查 DB、不检查 OSS**。

---

## 8. 现存问题清单（按严重程度）

| # | 问题 | 级别 | 证据 |
|---|---|---|---|
| P1 | 生产 compose 未注入 STORAGE_BACKEND/OSS_*，与「生产禁 local」校验冲突，容器无法启动 | **阻断** | `docker-compose.prod.yml` L31-52 + `config.py` L99-102 |
| P2 | 新上传接口仅 `admin/super_admin`，教师/学员无法传头像 | **阻断（功能）** | `upload/router.py` L33 |
| P3 | 头像/封面字段语义分裂：两个页面存完整 URL，两个存 object_key；OSS 下签名 URL 7 天后必然失效并被持久化 | **高** | `students/index.vue` L383、`teachers/index.vue` L393、`auth.ts` L20 |
| P4 | 旧 `/common/upload/image` 依赖未安装的 `oss2`，静默回落本地磁盘且返回 `http://localhost:8000` 绝对 URL | **高** | `core/oss/service.py` L166-176、L263-294 |
| P5 | 头像更新不校验 object_key 归属（可把任意 key/URL 写入自己资料） | **高（安全）** | `auth/service.py` L63、`user/service.py` L323 |
| P6 | 无删除接口；`file_objects.deleted_at` 无人写入；替换头像后旧对象永久残留 | **高** | `upload/` 全目录 |
| P7 | 签名有效期 7 天且被前端直接存库/缓存 | **中（安全）** | `oss_client.py` L23 |
| P8 | student-web / teacher-web 头像 src 不做解析，object_key 直接作为 img src | **中** | `student-web/views/profile/index.vue` L15、`teacher-web/...` L15 |
| P9 | 无图片解码校验/像素尺寸限制（未装 Pillow），存在解压炸弹风险 | **中** | `upload/service.py` L58-70 |
| P10 | nginx admin 域名默认 1M body 限制，5MB 头像必 413 | **中** | `infra/nginx/nginx.conf` admin server 块 |
| P11 | 课程封面无任何前端上传入口 | **中（功能）** | `apps/admin-web/src/views/courses/` |
| P12 | miniapp 无上传能力，教师头像功能仅 toast 占位 | **中（功能）** | `miniapp/.../edit.vue` L114 |
| P13 | 上传链路 CI 覆盖为 0；无 OSS mock 测试 | **中** | `.github/workflows/ci.yml` |
| P14 | 健康检查不含 OSS 连通性诊断 | **低** | `common/router.py` L24-41 |
| P15 | `core/oss_client.py` 模块级 `asyncio.Lock()` 跨 event loop 复用有隐患 | **低** | `oss_client.py` L30 |

---

## 9. 需要修改 / 新增 / 复用的文件

### 复用（不改语义）
- `file_objects` 表与其迁移 —— **无需新迁移**
- `TenantAwareRepository` / `require_roles` / `require_permissions` / `get_current_user`
- `core/oss_client.py` 的单例、凭证工厂、`resolve_object_url`
- `packages/api-client/src/common.ts` 的 `uploadImage`

### 修改
| 文件 | 改动 |
|---|---|
| `apps/api/src/app/modules/upload/router.py` | 上传权限从「仅管理员」改为「按 biz_type 分级」：`avatar` 允许本人（admin/teacher/student）；`banner/video_cover/notice/classroom_cover` 仅管理员 |
| `apps/api/src/app/modules/upload/service.py` | 增加图片解码校验（Pillow）、按 biz_type 区分的尺寸上限、object_key 归属校验辅助 |
| `apps/api/src/app/modules/upload/schemas.py` | 增加可选 `original_name`（如需） |
| `apps/api/src/app/core/oss_client.py` | 签名默认有效期下调（如 1h）；upload 与读取使用不同 TTL；Lock 改为 per-loop 惰性创建 |
| `apps/api/src/app/modules/auth/service.py` + `schemas.py` | `avatar_url` 入参校验为「本租户 `t/{tid}/avatar/` 前缀的 object_key」 |
| `apps/api/src/app/modules/user/service.py` | 同上（管理员改用户头像时） |
| `apps/api/src/app/modules/course/service.py` + `schemas.py` | `cover_url` 语义统一为 object_key，并加前缀校验 |
| `apps/api/src/app/modules/{user,auth,teacher,course,classroom}/service.py` | 出参把 object_key 解析为可访问 URL（`resolve_object_url`），前端不再自己拼 |
| `apps/api/src/app/core/config.py` | 增加 `UPLOAD_MAX_*`、`OSS_PRESIGN_TTL_SECONDS` 等业务参数 |
| `infra/docker/docker-compose.prod.yml` + `.env.prod.example` | 补齐 STORAGE_*/OSS_* 注入 |
| `infra/nginx/nginx.conf` | admin 域名补 `client_max_body_size` |
| `apps/admin-web/src/views/{students,teachers}/index.vue` | 改存 `object_key` |
| `apps/admin-web/src/views/courses/` | 新增封面上传（`biz_type=course_cover`，需同步扩展后端枚举） |
| `apps/student-web/src/views/profile/index.vue`、`apps/teacher-web/src/views/profile/index.vue` | 接上传 + 统一 URL 解析 |
| `apps/miniapp/src/api/index.ts` | 新增 `uploadFile`（基于 `uni.uploadFile`） |
| `apps/miniapp/src/pages/teacher/profile/edit.vue` | 实现 `changeAvatar` |
| `packages/api-client/src/common.ts` | 增加进度回调、删除方法、`getObjectUrl` |

### 新增
| 文件 | 用途 |
|---|---|
| `apps/api/src/app/modules/upload/image_probe.py`（或 service 内私有函数） | Pillow 解码校验 + 尺寸限制 |
| `apps/api/src/app/modules/upload/service.py::delete_object` 公开方法 + 路由 `DELETE /upload/{object_key}` | 删除/解绑，带引用检查 |
| `apps/api/tests/unit/test_upload_service.py` | mock OSS 的单元测试 |
| `apps/api/tests/integration/test_upload_api.py` | 权限/租户/格式/大小/失败补偿 |
| `scripts/oss_migrate_local_files.py`（可选，上线前） | 历史本地文件迁移到 OSS |

---

## 10. 上传方式选型：A vs B

| 维度 | A（后端中转） | B（预签名直传） |
|---|---|---|
| 现状 | **已实现**，只需修权限与语义 | 全部新建 |
| 小程序适配 | `uni.uploadFile` 直接 multipart，**无额外配置** | 需把 OSS 域名加入小程序 request 合法域名（需备案 + HTTPS），且 `uni.uploadFile` 对 PUT 支持差，通常要用 `wx.request` 传 ArrayBuffer |
| Web 适配 | FormData 现成 | 需 CORS 配置 + PUT 进度管理 |
| 安全 | 后端可完整校验内容、控制 key、写审计 | 需额外 confirm 接口校验对象存在与类型，且前端可指定 key |
| 带宽 | 经后端中转（≤5MB 图片可接受） | 直连 OSS，节省后端带宽 |
| 失败补偿 | 上传成功但 DB 失败需删除对象 | 未确认即产生孤儿对象 |

**推荐：A（后端中转）**。理由：
1. 头像/封面均为 ≤5MB 小图，中转带宽成本可忽略；
2. 小程序端 `uni.uploadFile` 是唯一稳定路径，B 会引入备案域名白名单与 PUT 能力缺失问题；
3. 安全与校验（魔数 + 解码 + key 生成 + 审计）全部收敛在后端，符合项目分层规则；
4. 已有完整实现，改动面最小。

**保留演进空间**：未来若引入课程视频（>50MB），再单独为视频设计 B 方案（分片 + 预签名 + confirm），不影响头像/封面链路。

---

## 11. 阿里云控制台待完成事项（我无法验证，需你在控制台确认/执行）

> 审计环境无阿里云访问权限，以下全部为 **UNVERIFIED**。

1. **角色可信实体**：RAM 控制台 → 角色 `class-booking-oss-role` → 信任策略必须含 `Service: ecs.aliyuncs.com`。
2. **角色授权策略**：
   ```json
   {
     "Version": "1",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["oss:PutObject", "oss:GetObject", "oss:HeadObject", "oss:DeleteObject"],
       "Resource": ["acs:oss:*:*:class-booking-system-prod/t/*"]
     }]
   }
   ```
   （`GetObject` 必须包含：预签名下载以签名者身份校验权限。）
3. **实例绑定**：ECS 控制台 → 实例 → 实例 RAM 角色 → 绑定该角色，随后重启实例或重启 api 进程。
4. **连通性自检**（在 ECS 上执行）：
   ```bash
   curl http://100.100.100.200/latest/meta-data/ram/security-credentials/class-booking-oss-role
   ```
   返回含 `AccessKeyId` + `SecurityToken` + `Expiration` 即通过。
5. **Bucket 侧**：确认「阻止公共访问」保持开启；确认无 Bucket Policy 反向拒绝该角色；确认同地域（cn-shanghai）。
6. **自定义域名**（可选，本次不做）：如启用需 CNAME + HTTPS 证书 + 中国内地 ICP 备案。当前不使用，`OSS_PUBLIC_BASE_URL` 保持空。

---

## 12. 分阶段实施计划与验收标准

| 阶段 | 内容 | 验收 |
|---|---|---|
| **S1 后端存储层加固** | Pillow 依赖 + 解码校验；签名 TTL 分级；Lock 修整；按 biz_type 的尺寸上限；配置项补齐 | 单测覆盖：格式/大小/解码失败；`pytest tests/unit` 通过 |
| **S2 权限与归属** | 上传接口按 biz_type 分级鉴权；`avatar_url`/`cover_url` 入参前缀校验；出参统一解析 URL | 集成测试：教师/学员可传头像、非管理员不可传 banner、跨租户 403、伪造 key 400 |
| **S3 删除与补偿** | `DELETE /upload/{object_key}`（引用检查 + 软删 + OSS 删除）；上传成功但 DB 失败时删除对象 | 测试：替换头像不误删被引用对象；DB 失败无孤儿记录 |
| **S4 部署配置** | compose prod 注入 OSS_*；`.env.prod.example` 补段；nginx `client_max_body_size`；容器启动校验 | `docker compose config` 校验通过；生产启动不再 RuntimeError |
| **S5 前端 web 三端** | 存 key 修正（students/teachers）；student/teacher 资料页接上传；课程封面上传；统一 URL 解析收敛到一处 | `vue-tsc` + build 通过；手工走查 4 个页面 |
| **S6 小程序** | `uni.uploadFile` 封装；教师头像上传；签名过期换链 | mp-weixin build 通过；DevTools 走查 |
| **S7 测试与验收** | 13 项验收用例补齐；真实 OSS 集成测试（专用前缀 `t/{tid}/_it/`）；ECS 实测记录 | 全部用例通过或明确标注未验证 |
| **S8 历史迁移** | 本地 `.uploads/` 与 `apps/api/uploads/` 迁移到 OSS，改写 DB 中的 `/uploads/...` | dry-run 报告 + 抽样验证 |

**总体验收标准**：见任务书第十一节；其中「生产 ECS 使用 RAM 角色获取短期凭证」必须以 §11 第 4 步的真实输出为证据，否则标注 UNVERIFIED。

---

## 13. UNVERIFIED 清单

| # | 项 | 原因 | 验证方式 |
|---|---|---|---|
| U1 | RAM 角色是否已绑定 ECS 实例 | 无云上访问权限 | 控制台或 §11 第 4 步 curl |
| U2 | 角色授权策略是否含 GetObject/PutObject/DeleteObject | 同上 | 控制台策略详情 |
| U3 | Bucket 内是否已有对象、是否存在 Bucket Policy 拒绝 | 同上 | `ossutil ls oss://class-booking-system-prod` |
| U4 | 生产环境当前是否真的以 `STORAGE_BACKEND` 未注入状态运行（即 P1 是否已在线上暴露） | 无服务器访问 | 查看 ECS 上容器 env 与启动日志 |
| U5 | 现有历史头像文件的实际物理分布（`.uploads/` vs `apps/api/uploads/` vs 已丢失） | 需登录服务器 | 服务器目录盘点 |
| U6 | 小程序 `request 合法域名` 现状（是否已含 api 域名） | 需小程序后台 | 微信公众平台 → 开发设置 |

---

## 14. 结论

1. **基础设施已就绪**：OSS 客户端、ECS 角色凭证、私有桶预签名、文件审计表、租户隔离全部存在，无需重建。
2. **真正的缺口集中在四处**：生产配置注入（P1）、上传权限过窄（P2）、头像/封面 URL 语义分裂（P3）、无删除与归属校验（P5/P6）。
3. **不需要新增数据表或迁移**，改动以「修正语义 + 补权限 + 补校验 + 补配置」为主，符合最小改动原则。
4. **上传方式选 A**（后端中转），与现有实现和小程序能力最匹配。
