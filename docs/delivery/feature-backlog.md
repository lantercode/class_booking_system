# Feature Backlog（后续开发任务）

> 生成日期：2026-09-24
> 来源：产品交付基线审计（`docs/delivery/product-gap-analysis.md`）
> 结构：Epic → Feature → User Story → Task

---

## Epic 1：安全防线修复

### Feature 1.1：RBAC 权限校验真实生效 ✅ DONE（2026-09-27）

- **Goal**：所有受保护端点执行真实权限校验，杜绝越权操作
- **User Story**：作为系统管理员，我希望权限控制真正生效，以便普通学员无法访问管理接口
- **Scope**：`PERMISSION_CHECK_BYPASS` 置 False；补全所有缺失的 `@require_permissions` 装饰器
- **Out of Scope**：不新增权限模型，不重构 RBAC 架构
- **Dependencies**：无
- **Acceptance Criteria**：
  - `PERMISSION_CHECK_BYPASS = False` ✅（改为配置驱动，默认 False）
  - 所有写操作端点有 RBAC 装饰器 ✅
  - 学员角色访问 `/admin/*` 返回 403 ✅
  - 无权限用户访问受保护接口返回 403 ✅
- **Required Agents**：project-architect, backend-engineer
- **交付物**：`docs/features/F1.1-rbac-enforcement/`（requirement / user-flow / acceptance / implementation-plan / implementation-report / static-verification / runtime-test-report / review / release-note）
- **验收结论**：READY_FOR_ACCEPTANCE（test_rbac_enforcement.py 17/17 通过；test_auth_api 25/25、test_rbac_real_redis + test_agent_runtime 11/11 回归通过）
- **上线注意**：存量数据库需先执行 release-note.md §4.2 的补权 SQL，否则 admin 部分操作 403
- **新登记技术债**：
  - D-F1.1-1：`ai/router.py` `get_supported_intents` 访问不存在的 `IntentRecognizer.intents` 实例属性，认证通过后 500，应改用类属性 `INTENTS`

### Feature 1.2：JWT Token 主动失效 ✅ DONE（2026-09-26）

- **Goal**：登出后 access_token 立即失效
- **User Story**：作为用户，我希望登出后我的 Token 立即失效，不被他人冒用
- **Scope**：登出时将 access_token 加入黑名单；`get_current_user` 校验黑名单
- **Dependencies**：Redis 可用
- **Acceptance Criteria**：登出后旧 access_token 调用任何接口返回 401
- **Required Agents**：backend-engineer
- **Test Criteria**：登出 → 用旧 access_token 调用 → 401
- **Tasks**：
  - T1.2.1：logout 接口接收并拉黑 access_token ✅
  - T1.2.2：`get_current_user` 增加 `is_token_blacklisted` 检查 ✅
  - T1.2.3：黑名单 TTL = access_token 剩余有效期 ✅
- **交付物**：`docs/features/F1.2-jwt-token-invalidation/`（requirement / user-flow / architecture / test-plan / acceptance / implementation-report / static-verification / review / release-note）
- **验收结论**：READY_FOR_ACCEPTANCE → CLOSE（test_auth_api.py 25/25 通过，含 6 个新增黑名单用例）
- **新登记技术债**：
  - D-F1.2-1：`get_redis_client` 中存在 `print(f"🔗 正在连接 Redis: {settings.REDIS_URL}")` 调试输出，泄露 Redis URL（安全隐患，建议 F1.3 或独立清理）
  - D-F1.2-2：`test_tenant_isolation.py` / `test_mcp_server.py` 预存失败（事件循环、租户上下文设置），与 F1.2 无关但影响 CI 绿度

### Feature 1.3：通用异常处理器 + 生产 debug 关闭 ✅ DONE（2026-09-26）

- **Goal**：未捕获异常返回标准化 500，不泄露 traceback
- **Scope**：注册 `Exception` handler；生产环境 `APP_DEBUG=False`
- **Dependencies**：无
- **Acceptance Criteria**：触发未捕获异常时返回 `{code:500,msg:"服务暂时不可用"}`，无 traceback
- **Required Agents**：backend-engineer
- **Tasks**：
  - T1.3.1：注册 `@app.exception_handler(Exception)` ✅
  - T1.3.2：生产环境 `APP_DEBUG=False`（config 默认值改为 False，开发环境 .env 覆盖）✅
  - T1.3.3：修复 AI router 异常处理（移除本地 try/except，交全局 handler）✅
- **交付物**：`docs/features/F1.3-exception-handler/`（requirement / architecture / test-plan / acceptance / implementation-report / static-verification / release-note）
- **验收结论**：READY_FOR_ACCEPTANCE → CLOSE（test_exception_handlers.py 7/7 通过；422 不回归；500 统一信封不泄露）

### Feature 1.4：生产 Redis 密码认证 ✅ DONE（2026-09-27）

- **Goal**：生产 Redis 必须密码认证
- **Scope**：`docker-compose.prod.yml` 加 `requirepass`；后端连接串带密码
- **Dependencies**：无
- **Required Agents**：backend-engineer
- **Tasks**：
  - T1.4.1：compose 加 `command: redis-server --requirepass ${REDIS_PASSWORD}` ✅（healthcheck 同步加 `-a` 认证）
  - T1.4.2：`config.py` REDIS_URL 支持密码 ✅（新增 `REDIS_PASSWORD` 字段，默认空兼容 dev）
  - T1.4.3：`.env.prod.example` 加 `REDIS_PASSWORD` ✅（新建生产模板）
- **附带修复**：D-F1.2-1（`get_redis_client` print 泄露 Redis URL）→ 改 logger 且不输出 URL
- **交付物**：`docs/features/F1.4-redis-password-auth/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（回归 30/30 通过；prod compose 渲染验证通过；AC-1.2/1.3 NOAUTH 行为留生产部署窗口人工验收）
- **上线注意**：`.env.prod` 必须设置 `REDIS_PASSWORD`，否则 compose 启动即 warning + API 不健康（可立即发现，不会静默裸奔）

### Feature 1.5：定时任务租户隔离 ✅ DONE（2026-09-27）

- **Goal**：APScheduler 任务按租户循环并设置 ContextVar
- **Scope**：schedule/membership scheduler 改为按租户循环
- **Dependencies**：无
- **Acceptance Criteria**：定时任务不跨租户操作数据 ✅
- **Required Agents**：backend-engineer
- **Tasks**：
  - T1.5.1：scheduler 开头查询所有 ACTIVE 租户 ✅
  - T1.5.2：循环内 `set_tenant_id(tenant_id)` 后再执行业务 ✅
  - T1.5.3：异常隔离（单租户失败不影响其他租户）✅
- **交付物**：`docs/features/F1.5-scheduler-tenant-isolation/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（test_scheduler_tenant_isolation.py 9/9 通过）

---

## Epic 2：核心业务修复

### Feature 2.1：admin 用户管理真实化 ✅ DONE（2026-09-27）

- **Goal**：admin 模块用户管理操作真实数据库，不再返回 Mock
- **Scope**：`admin/service.py` 全部方法改为调用 user/role Service
- **Dependencies**：Feature 1.1（RBAC 生效）✅
- **Acceptance Criteria**：admin 创建/更新/删除用户真实生效；角色分配真实生效 ✅
- **Required Agents**：backend-engineer
- **Tasks**：
  - T2.1.1：`create_user` 调用 `user_service.create` ✅
  - T2.1.2：`update_user` / `delete_user` 真实操作 ✅
  - T2.1.3：`assign_roles` / `batch_delete` 真实操作 + 失效缓存 ✅（批量删除为原子事务，任一失败整体回滚）
  - T2.1.4：admin dashboard 统计真实查询 ✅（原本已真实；`public/stats` 硬编码假数据改为按租户真实聚合）
- **交付物**：`docs/features/F2.1-admin-user-real/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（test_admin_user_real.py 12/12 通过；test_auth_api + test_rbac_enforcement 42/42 回归通过）
- **新登记技术债**：
  - D-F2.1-1：`POST /api/v1/users` 尾斜杠 405 预存问题（test_user_api.py::test_create_user_success 失败，与本 Feature 无关，已 git stash 对照证实）
  - D-F2.1-2：admin dashboard 聚合 SQL 在 Router 层（违反分层但功能真实），建议下沉 Service
  - D-F2.1-3：`AuthRepository.get_role_by_id` 缺失导致 assign_roles 休眠路径必 500 — **已在本 Feature 顺手修复**

### Feature 2.2：预约数据归属与泄露修复 ✅ DONE（2026-09-28）

- **Goal**：学员只能查看自己的预约
- **Scope**：`GET /bookings` 强制 student_id 过滤；`GET /bookings/{id}` 归属校验
- **Dependencies**：无
- **Acceptance Criteria**：学员 A 无法查看学员 B 的预约 ✅
- **Required Agents**：backend-engineer
- **Tasks**：
  - T2.2.1：`list_bookings` 对学员角色强制 `student_id=current_user.id` ✅（角色由 Service 经 `get_user_role_codes` 查 DB，不从 JWT payload 读）
  - T2.2.2：`get_booking` 增加归属校验（学员只能看自己的）✅（owner OR teacher-of-schedule OR admin）
  - T2.2.3：教师可看其排期下的预约 ✅（JOIN schedule.teacher_id 过滤）
- **交付物**：`docs/features/F2.2-booking-ownership/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（test_booking_ownership 10/10；回归 test_auth_api + test_rbac_enforcement + test_admin_user_real 54/54；合计 64/64 通过）
- **关键改动**：6 源文件（checker.py 新增 `get_user_role_codes`；booking repo/service/router；mcp_server `get_my_bookings` 同步签名）；契约零变更，前端 4 端无影响
- **新登记技术债**：
  - D-F2.2-1：写操作端点（create_booking/cancel_booking/cancel_by_schedule）归属校验完备性复核（受 `@require_roles("student")` 限定，非越权，建议后续复核）

### Feature 2.3：签到/完成加行锁 ✅ DONE（2026-09-28）

- **Goal**：签到/完成操作并发安全
- **Scope**：`check_in_booking` / `complete_booking` 使用 `get_by_id_for_update`
- **Dependencies**：无
- **Required Agents**：backend-engineer, database-engineer
- **Tasks**：
  - T2.3.1：check_in 用 FOR UPDATE 取 booking，重检 status ✅
  - T2.3.2：complete 同上 ✅
- **交付物**：`docs/features/F2.3-checkin-complete-lock/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（test_checkin_complete_lock 9/9；回归 test_booking_ownership 10/10 + test_auth_api 25/25；合计 44/44 通过）
- **关键改动**：service.py 2 处 `get_by_id` → `get_by_id_for_update`（与 `_do_cancel_booking` 同构）；复用既有 repository 方法，零 DB 结构变更

### Feature 2.4：cancel_schedule 回补失败回滚 ✅ DONE（2026-09-28）

- **Goal**：取消排期时若某预约课时回补失败，整体回滚
- **User Story**：作为运营/教师，我希望取消排期失败时不会留下"已 CANCELLED 但 credit 未恢复"的脏数据
- **Scope**：`cancel_schedule` 移除外层 try/except 吞异常，任一 booking 处理失败（含 `restore_credit` 失败）直接 raise 触发 AsyncSession 回滚
- **Out of Scope**：不改 router / OpenAPI / 前端 / booking service / membership service；不改 DB 结构
- **Dependencies**：无
- **Acceptance Criteria**：
  - AC-1 正常取消（含 booking+card）→ 全部 CANCELLED + credit 恢复 ✅
  - AC-2 restore_credit 失败 → raise BusinessException(500) + DB 回滚到初始状态 ✅
  - AC-3 多 booking 中途失败 → 已成功变更也回滚（mock 调用计数==2，DB 终态全部 BOOKED）✅
  - AC-4 无 BOOKED 预约 → 直接成功 ✅
  - AC-5 已 CANCELLED 排期再取消 → 400 ✅
  - AC-6 HTTP 正常取消 → 200 + 信封正确 ✅
  - AC-7 HTTP 失败路径 → 500 + 信封 + DB 回滚 + msg 不含 Traceback ✅
  - AC-8 回归不破现有行为 ✅
  - AC-9 分层合规（Service 内 commit；不裸 SQL；跨模块仅调 MembershipCardService.restore_credit）✅
- **Required Agents**：backend-engineer, database-engineer
- **Tasks**：
  - T2.4.1：移除 `cancel_schedule` 外层 try/except 吞异常 ✅
  - T2.4.2：内层 except 包装为 `raise BusinessException(500, "会员卡恢复次数失败，取消排期操作已撤销: ...")` ✅（不再累积 `failed_bookings`/`success_count`，事务回滚路径不到达 return）
- **交付物**：`docs/features/F2.4-cancel-schedule-rollback/`（requirement / user-flow / acceptance / implementation-plan / implementation-report / static-verification / runtime-test-report / review / release-note，SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（test_cancel_schedule_rollback 12/12；回归 test_checkin_complete_lock 9/9 + test_booking_ownership 10/10 + test_auth_api 25/25 = 44/44；合计 56/56 通过）
- **关键改动**：1 源文件（schedule/service.py 单方法重构：移除外层 try/except，内层 except 改 raise BusinessException(500)）；契约零变更，前端 4 端无影响；零 DB 结构变更（FOR UPDATE 行锁按主键命中已有主键索引）
- **新登记技术债**：
  - D-F2.4-1：`cancel_schedule` 当前 `page_size=1000` 上限，单排期 BOOKED 预约数超过 1000 时会漏处理（实际排期容量远小于 1000，属另一优化 Feature 范围）
  - D-F2.4-2：`cancel_schedule` 当前仅取消 `status=BOOKED` 的预约，对 CHECKED_IN / COMPLETED 预约不特殊处理，建议后续 Feature 复核"取消排期对 CHECKED_IN 预约的处置策略"

### Feature 2.5：delete_schedule 下沉到 Service ✅ DONE（2026-09-28）

- **Goal**：Router 不直接操作 Repository
- **User Story**：作为后端工程师，我希望删除排期的业务规则与数据访问只存在于 Service 层，Router 为薄层，其他调用方未来可复用同一权威实现
- **Scope**：`delete_schedule` 逻辑原样下沉到 `ScheduleService.delete_schedule(db, schedule_id)`；router 端点瘦身；清理唯一使用点的 `ScheduleStatus` import
- **Out of Scope**：不改 booking 模块 / repository / models / schemas / `batch_delete_schedules`；不改 OpenAPI / 前端 4 端 / MCP；不改 DB 结构；业务规则、错误码、文案、删除顺序与事务语义零变化
- **Dependencies**：无（复用既有 `BookingRepository.delete_by_schedule_id` 与 `TenantAwareRepository.delete(hard_delete=True)`）
- **Acceptance Criteria**：
  - AC-1 Service 直调删除已取消排期成功，关联 booking 级联硬删（DB 双表断言）✅
  - AC-2 删除不存在排期 → NotFoundException（404）✅
  - AC-3 NORMAL 且 booked_count>0 → BusinessException(400)，DB 无变更 ✅
  - AC-4 HTTP admin DELETE /schedules/{id} → 200 + msg="排期删除成功" ✅
  - AC-5 HTTP student（无 schedule:delete）→ 403，schedule 未删除 ✅
  - AC-6 HTTP 删除不存在 → 404 业务信封，无 Traceback ✅
  - AC-7 回归不破现有行为 ✅
  - AC-8 分层合规：router grep `BookingRepository`/`repo.`/`get_by_id`/`hard_delete` 0 匹配 ✅
- **Required Agents**：backend-engineer
- **Tasks**：
  - T2.5.1：`schedule_service.delete_schedule` 方法 ✅（service.py L332-364，逻辑逐行迁移；返回 `{"schedule_id": id}`）
  - T2.5.2：router 调用 service ✅（端点体缩为 1 行 Service 调用 + 移除顶部 ScheduleStatus import）
- **交付物**：`docs/features/F2.5-delete-schedule-service/`（requirement / user-flow / acceptance / implementation-plan / implementation-report / static-verification / runtime-test-report / review / release-note，SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（test_delete_schedule_service 9/9；回归 test_cancel_schedule_rollback 12/12 + test_checkin_complete_lock 9/9 + test_booking_ownership 10/10 + test_auth_api 25/25 = 56/56；合计 65/65 通过）
- **关键改动**：2 源文件（service.py 仅追加 1 方法；router.py 2 处定点编辑）+ 1 新测试；OpenAPI 契约零变更，前端 4 端零改动；零 DB 结构变更
- **新登记技术债**：
  - D-F2.5-1：schedule Service 三处（`cancel_schedule` / `batch_delete_schedules` / `delete_schedule`）直调 `BookingRepository`，建议后续由 booking Service 提供入口统一收口跨模块调用并整理函数内 import 风格
  - D-F2.5-2：排期删除为物理硬删且级联清除任意状态历史 booking（迁移前既有行为，本次原样保留），是否需要删除前归档 / 软删建议另立 Feature 评估

---

## Epic 3：前端崩溃修复

### Feature 3.1：miniapp 运行时崩溃修复

- **Status**：✅ DONE（2026-09-26 关闭，人工验收通过）
- **交付物**：`docs/features/F3.1-miniapp-crash-fix/`（requirement / user-flow / acceptance / implementation-plan / implementation-report / static-verification / runtime-test-report / review / release-note）
- **Goal**：教师排期/学员、学员排期页面正常加载
- **Scope**：补全缺失的 import
- **Dependencies**：无
- **Acceptance Criteria**：3 个页面加载无 ReferenceError
- **Required Agents**：frontend-engineer
- **Tasks**：
  - T3.1.1：`teacher/schedule/index.vue` 导入 `extractList` from `@/utils/helpers`
  - T3.1.2：`teacher/students/index.vue` 导入 `extractList`
  - T3.1.3：`student/schedule/index.vue` 导入 `tenantApi` from `@/api`

### Feature 3.2：miniapp 类型检查门禁 ✅ DONE（2026-09-29）

- **Goal**：miniapp 构建前强制类型检查，TS 错误不流入生产
- **Scope**：package.json 加 `vue-tsc --noEmit` 到 build 脚本
- **Dependencies**：无
- **Acceptance Criteria**：`npm run build:mp-weixin` 前先过 vue-tsc，有错误则构建失败
- **Required Agents**：frontend-engineer
- **Tasks**：
  - T3.2.1：package.json build 脚本改为 `vue-tsc --noEmit && uni build -p mp-weixin` ✅（build:mp-weixin 与 build:mp-weixin:dev 均前置门禁，另加 type-check 脚本）
  - T3.2.2：修复现有 TS 错误 ✅（实测基线 27 error → 0；api/index.ts 补 7 个后端契约 interface + PATCH 联合 + 递归泛型修复，AiAssistant 补 message-sent emit，4 页 statusBarHeight `?? 0`，schedule 状态联合补 pending/frozen，booking-confirm null 收窄）
- **交付物**：`docs/features/F3.2-miniapp-type-gate/`（requirement / user-flow / acceptance / implementation-plan / implementation-report / static-verification / runtime-test-report / review / release-note）
- **验收结论**：READY_FOR_ACCEPTANCE（`npx vue-tsc --noEmit` 退出码 0，错误数 27→0；正向 `npm run build:mp-weixin` 出包成功 dist/build/mp-weixin；反向探针退出码 2 且 uni build 被 && 短路；无新增 @ts-ignore / as any / 依赖 / tsconfig 改动；F3.1 import 回归通过）
- **关键改动**：纯前端类型层 + 构建脚本（7 文件）；无后端 / OpenAPI / DB / 其他三端改动，运行时行为零变化

### Feature 3.3：admin tenant 页对接真实接口 ✅ DONE（2026-09-29）

- **Goal**：机构设置页可查看和保存真实配置
- **Scope**：对接 `GET/PUT /tenant/settings` + `GET/PUT /tenant/info`
- **Dependencies**：后端需新增 `PUT /tenant/settings`（本 Feature 内完成）
- **Required Agents**：frontend-engineer, backend-engineer
- **Tasks**：
  - T3.3.1：后端新增 `PUT /tenant/settings` + `PUT /tenant/info` ✅（schemas.py 4 模型 + service update_settings/update_info + router 2 PUT 端点，浅合并/部分更新）
  - T3.3.2：前端 tenant 页读取真实数据 ✅（onMounted 并行 GET settings + GET info）
  - T3.3.3：保存按钮调用 PUT ✅（dirty 检测 + exclude_unset 语义 + 两独立保存 + 四态覆盖）
- **交付物**：`docs/features/F3.3-tenant-settings/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（后端 18/18 集成测试；前端 vue-tsc 0 error + build 成功；rbac 回归无影响）
- **关键改动**：后端 4 文件（schemas/service/router/test）+ 前端 3 文件（tenant.ts/index.ts/tenant/index.vue）；契约兼容变更（纯新增端点）；DB schema 不变
- **新登记技术债**：D-F3.3-1（response_model 全项目统一迁移为 StandardResponse[Schema]，独立技术债）

### Feature 3.4：前端四态补全 ✅ DONE（2026-09-29）

- **Goal**：所有列表页具备 loading / empty / error / success 四态
- **Scope**：student-web、teacher-web、admin-web 缺失四态的页面（共 12 个列表页）
- **Required Agents**：frontend-engineer
- **Tasks**：
  - T3.4.1：补全 loading 态（skeleton 或 v-loading）✅（admin-web/dashboard 与 teacher-web/students、teacher-web/schedule 补 v-loading；student-web/my-bookings 补 v-if loading + v-loading 区块）
  - T3.4.2：补全 error 态（ElMessage + 重试）✅（统一 el-result icon="error" + 重试按钮 + loadError ref + catch 走 e?.response?.data?.msg + ElMessage.error）
  - T3.4.3：补全 empty 态 ✅（admin-web el-table 加 empty-text="暂无数据"；student-web/teacher-web 用 el-empty + 描述）
- **交付物**：`docs/features/F3.4-list-page-states/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（三端 vue-tsc 0 error + build 成功：admin 3.54s / student 3.08s / teacher 3.52s；grep 验证 16 个被改列表页全部命中 v-loading + el-empty|empty-text + el-result icon="error"|loadError；纯前端无后端改动；catch 走统一信封 msg）
- **关键改动**：纯前端 12 文件（admin-web 6 + student-web 3 + teacher-web 3）；不引入新依赖、不改业务逻辑、不改后端；admin-web 已有四态的 5 页面（tenant/schedules/teachers/students/users）未动
- **新登记技术债**：D-F3.4-1（admin-web/courses/index.vue 等 unused function 警告，既有代码本 Feature 仅补四态未清理）；D-F3.4-2（admin-web/dashboard 的 unused var 警告，同上）

---

## Epic 4：数据库一致性

### Feature 4.1：恢复 bookings.membership_card_id 外键 ✅ DONE（2026-09-29）

- **Goal**：预约必须引用存在的会员卡
- **Scope**：Alembic migration 加外键 `ON DELETE SET NULL`
- **Dependencies**：先清理孤立数据
- **Required Agents**：database-engineer
- **Tasks**：
  - T4.1.1：查询并清理孤立预约 ✅（migration 内 `UPDATE ... SET NULL WHERE card_id NOT IN (SELECT id FROM membership_cards)`，实测 4 条孤立全部置 NULL）
  - T4.1.2：migration 加外键约束 ✅（`op.create_foreign_key("fk_bookings_membership_card_id", ..., ondelete="SET NULL")`；模型补 `ForeignKey("membership_cards.id", ondelete="SET NULL")`）
- **交付物**：`docs/features/F4.1-booking-fk-membership-card/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE → CLOSE（test_booking_fk_membership_card.py 6/6 通过 + 回归 31/31；migration 可逆性 downgrade→upgrade 往返成功；孤立 4→0；FK ON DELETE SET NULL 已建；Service/Repository 零改动）
- **关键改动**：纯数据库结构 3 文件（migration `f41ab2c3d4e5` 新建 + booking/models.py 补 ForeignKey + 新增集成测试）；不动 Service/Repository/Router/OpenAPI/前端/MCP；恢复 init migration 原设计（`4bd04b738098` 原有该 FK，后丢失）

### Feature 4.2：orders.membership_card_id 外键 + 索引 ✅ DONE（2026-09-29）

- **Goal**：订单引用完整性
- **Scope**：外键 `ON DELETE SET NULL` + 索引
- **Required Agents**：database-engineer
- **Tasks**：
  - T4.2.1：migration 加外键 `ON DELETE SET NULL` ✅（同一事务内先防御性清理孤立 `UPDATE ... SET NULL WHERE card_id NOT IN (SELECT id FROM membership_cards)`，dev 库 0 行受影响；再 `op.create_foreign_key("fk_orders_membership_card_id", ..., ondelete="SET NULL")`；模型补 `ForeignKey("membership_cards.id", ondelete="SET NULL")`）
  - T4.2.2：加索引 ✅（`op.create_index("ix_orders_membership_card_id", "orders", ["membership_card_id"])`；模型 `__table_args__` 补 `Index("ix_orders_membership_card_id", "membership_card_id")`）
- **交付物**：`docs/features/F4.2-order-fk-membership-card/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE → CLOSE（test_order_fk_membership_card.py 7/7 通过 + F4.1 回归 6/6；migration 可逆性 downgrade→upgrade 往返成功；孤立 0→0（dev 库原本 0，防御性清理 0 行）；FK ON DELETE SET NULL + 索引 ix_orders_membership_card_id 已建；Service/Repository/Router/schemas 零改动）
- **关键改动**：纯数据库结构 3 文件（migration `f42cd3e4f5a6` 新建 + order/models.py 补 ForeignKey + Index + 新增集成测试）；不动 Service/Repository/Router/OpenAPI/前端/MCP；down_revision=f41ab2c3d4e5（F4.1 后唯一 head）；恢复 57aeb9dcf020 建列时遗漏的 FK 并补索引

### Feature 4.3：解冻批量操作锁排序 ✅ DONE（2026-09-29）

- **Goal**：消除死锁风险
- **Scope**：`unfreeze_and_cancel_conflicts` / `unfreeze_and_freeze_conflicts` 对 conflict_card_ids 排序后再加锁（+ 扩展修复 `batch_cancel_cards` 同模式）
- **Dependencies**：无
- **Required Agents**：backend-engineer, database-engineer
- **Tasks**：
  - T4.3.1：`conflict_card_ids = sorted(conflict_card_ids)` ✅（`unfreeze_and_cancel_conflicts` [service.py:906](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L906) 循环前注入，带 `# F4.3` 注释引用 transaction.md §锁顺序）
  - T4.3.2：按排序顺序调用 `get_card_with_lock` ✅（`unfreeze_and_freeze_conflicts` [service.py:1041](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/service.py#L1041) 同模式注入；`get_card_with_lock` 的 `SELECT ... FOR UPDATE` 未动）
- **交付物**：`docs/features/F4.3-unfreeze-lock-ordering/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE → CLOSE（test_unfreeze_lock_ordering.py 8/8 通过 + F2.4 回归 12/12 + checkin/ownership 回归 19/19 = 39 passed；spy 等价证明两个反序请求加锁顺序收敛到 sorted 全局升序 → Coffman 循环等待条件被打破 → 死锁不可能；get_card_with_lock / 事务边界 / 状态机 / Repository / Router / schemas / migration / DB schema / OpenAPI / 前端 / MCP 零改动）
- **关键改动**：纯 Service 层 2 文件（membership/service.py 3 处各加 `# F4.3` 注释 + `sorted(...)`：T4.3.1 cancel / T4.3.2 freeze / 扩展 batch_cancel_cards + 新增单元测试）；不动 get_card_with_lock/Repository/Router/schemas/migration/OpenAPI/前端/MCP；扩展修复 batch_cancel_cards（同模式同风险，按用户提示"一并修复"指令，D6 决策透明记录）

### Feature 4.4：status 字段 Check 约束 ✅ DONE（2026-10-02）

- **Goal**：数据库层防止非法状态值
- **Scope**：核心表 status 字段加 Check 约束
- **Required Agents**：database-engineer
- **Tasks**：
  - T4.4.1：`ck_bookings_status` ✅（`CHECK (status IN (1,2,3,4,5))`，对应 `BookingStatus`；migration `create_check_constraint` + [booking/models.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/booking/models.py#L67-L70) `__table_args__` 补同名 `CheckConstraint`）
  - T4.4.2：`ck_course_schedules_status` ✅（`CHECK (status IN (1,2,3))`，对应 `ScheduleStatus`；[schedule/models.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/schedule/models.py#L66-L69) 同模式）
  - T4.4.3：`ck_membership_cards_status` ✅（`CHECK (status IN (0,1,2,3,6))`，对应 `CardStatus`；[membership/models.py](file:///Users/lixiang/Desktop/class_booking_system/apps/api/src/app/modules/membership/models.py#L228-L231) 同模式）
  - T4.4.4：migration ✅（`f44ab1c2d3e4_add_status_check_constraints`，`down_revision=f42cd3e4f5a6`；upgrade 同一事务内先 fail-fast 越界校验（三表逐表 `WHERE status NOT IN (...)`，越界即 raise 回滚并打印明细——非法 status 无语义安全修正目标，D2 决策区别于 F4.1/F4.2 的防御性清理）再建三约束；downgrade 反序 drop）
- **交付物**：`docs/features/F4.4-status-check-constraints/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE → CLOSE（test_status_check_constraints.py 18/18 通过 + F4.1 回归 6/6 + F4.2 回归 7/7 = 31 passed；migration 可逆性 downgrade→upgrade 往返成功；三表越界 0（bookings 11 / course_schedules 33 / membership_cards 17 行，存量数据未破坏）；三个 Check 约束已建且与模型一致；Service/Repository/Router/schemas/OpenAPI/前端/MCP 零改动）
- **关键改动**：纯数据库结构 5 文件（migration `f44ab1c2d3e4` 新建 + 三张模型 `__table_args__` 各补 1 个 `CheckConstraint`（booking 另补 import）+ 新增集成测试）；down_revision=f42cd3e4f5a6（F4.2 后唯一 head）；枚举值核查与 backlog 一致（BookingStatus{1,2,3,4,5} / ScheduleStatus{1,2,3} / CardStatus{0,1,2,3,6}）；存量命名漂移（membership_cards `chk_credits_range` vs DB `chk_used_credits_valid`/`chk_total_credits_positive`）记为 UNKNOWN U3，另立 Feature 处理

### Feature 4.5：排期创建并发安全 ✅ DONE（2026-10-02）

- **Goal**：并发创建不产生时间冲突排期
- **Scope**：冲突检查与插入放入同一事务 + SERIALIZABLE（D1：实证表明二者必须叠加，非二选一）
- **Required Agents**：backend-engineer, database-engineer（双专家独立评审，一轮 NEEDS_FIX 回修）
- **Tasks**：
  - T4.5.1：`find_conflicts` + `create` 同事务 ✅
  - T4.5.2：`db.connection(execution_options={"isolation_level":"SERIALIZABLE"})`（官方入口，替代遗留裸 `BEGIN`）✅
  - T4.5.3（评审新增）：冲突检查改快照谓词读 `use_lock=False`，杜绝 `SKIP LOCKED` 吞掉被并发 RC 事务持锁的已存在冲突行 ✅
- **交付物**：`docs/features/F4.5-schedule-create-concurrency/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE → CLOSE（test_schedule_create_concurrency.py 9/9 含评审回归 AC-5b；F4.4 18 + F4.1 6 + F4.2 7 + schedule delete 9 + cancel rollback 12 + scheduler 9 = 70/70 一次合并通过；SHOW/SSI/Barrier 因果实证 + 持锁冲突行因果翻转（旧代码 DID NOT RAISE）留痕；无 migration，head 仍 f44ab1c2d3e4）
- **关键改动**：service.py（创建路径同事务 SERIALIZABLE + 40001 三次重试 + 友好兜底 + `use_lock=False`）、repository.py（仅 `find_conflicts` docstring 补 SKIP LOCKED 警告，逻辑零改）、新增集成测试 9 用例；Router/schemas/models/migration/OpenAPI/前端 4 端/MCP/Redis 零改动；同文件预存 `increment_booked_count` skip_locked hunk 与本 Feature 无关，提交按 hunk 隔离
- **新登记技术债**：
  - D-F4.5-1（中）：`batch_create_schedules`（RC + use_lock=True，POST /schedules/batch 存活）同构并发缺口
  - D-F4.5-2（中低）：`update_schedule`（RC + 快照读）时间更新 write skew 缺口
  - D-F4.5-3（低）：EXCLUDE 排他约束（btree_gist + tenant/teacher、tenant/classroom 两条部分排他约束）库内最终保证专项
  - D-F4.5-4（低）：find_conflicts 手工 tenant 谓词叠加无注释；router `/schedules/` 尾斜杠不符 contracts.md

---

## Epic 5：AI / MCP 修复

### Feature 5.1：多轮预约流程修复 ✅ DONE（2026-09-27）

- **Goal**：AI 能正确解析排期列表并完成预约
- **Scope**：统一 `query_schedules` 输出格式与 `_parse_schedules` 解析格式
- **Dependencies**：无
- **Acceptance Criteria**：用户说"预约明天的瑜伽课"，AI 能列出排期并完成预约 ✅
- **Required Agents**：mcp-engineer, backend-engineer
- **Tasks**：
  - T5.1.1：定义统一的排期输出格式（`- ID:{id} | {日期} | {时间} | {教师} | 剩余:{n} | {课程}`）✅
  - T5.1.2：`query_schedules` 按统一格式输出 ✅
  - T5.1.3：`_parse_schedules` 按统一格式解析 ✅
  - T5.1.4：端到端测试 ✅
- **交付物**：`docs/features/F5.1-booking-flow-fix/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（test_agent_runtime.py 5/5 通过，含端到端预约成功用例）

### Feature 5.2：Tool 授权校验 ✅ DONE（2026-09-29）

- **Goal**：写操作 Tool 校验用户权限
- **Scope**：create_booking / cancel_booking 等写 Tool 增加授权判断
- **Dependencies**：无
- **Required Agents**：mcp-engineer
- **Tasks**：
  - T5.2.1：create_booking 校验当前用户是学员 ✅（`_require_student_role` 复用 `get_user_role_codes`，非学员 403 且 Service 不被调用）
  - T5.2.2：cancel_booking 校验预约归属 ✅（Tool 角色关 + BookingService 既有归属关，两关独立）
- **额外修复**：
  - 写 Tool 补四关（Authentication 401 / Authorization 403 / Tenant ORM 事件 / Input 400），移除吞异常回显
  - runtime `_handle_business_error` 改中文关键词匹配 + 安全兜底（不回显原文，F5.3 约束在当前代码落地）
  - AgentRuntime 补 `tenant_id` 构造参数（修复 AI router 传参 TypeError）
- **交付物**：`docs/features/F5.2-tool-authorization/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（新增授权测试 18/18；F5.3 映射 10/10；rbac+booking_ownership 回归 27/27；2 个 F5.1 脚本测试预存失败与本 Feature 无关）
- **关键改动**：mcp_server.py（2 helper + 2 Tool 四关）、runtime.py（tenant_id 参数 + 错误映射）、test_mcp_tool_authorization.py 新增；/ai/chat 契约零变更，前端 4 端无改动
- **新登记技术债**：
  - D-F5.2-1：查询类 Tool（get_my_bookings/get_my_balance）收口为 Service 调用（当前直写 select/透传 user_id）
  - D-F5.2-2：test_agent_runtime 两个 F5.1 脚本式用例改造为自造数据标准用例
  - D-F5.2-3：stdio MCP 独立会话的显式 tenant 传递机制评估

### Feature 5.3：异常处理不泄露原始信息 ✅ DONE（2026-09-27）

- **Goal**：AI 错误响应友好，不回显内部异常
- **Scope**：修复 `_handle_business_error` 映射表，兜底返回通用提示
- **Required Agents**：mcp-engineer
- **Tasks**：
  - T5.3.1：修复异常消息匹配（中文 key）✅
  - T5.3.2：兜底返回"操作失败，请稍后重试"，不回显原始异常 ✅
- **交付物**：`docs/features/F5.3-ai-error-handling/`（requirement / architecture / test-plan / acceptance / implementation-report / static-verification / release-note）
- **验收结论**：READY_FOR_ACCEPTANCE → CLOSE（`test_business_error_handling` 10/10 通过，所有业务异常友好映射且不泄露原文）

### Feature 5.4：清理 ai/tools/ 残留 ✅ DONE（2026-09-29）

- **Goal**：消除两套 Tool 注册并存
- **Scope**：删除 `ai/tools/` 目录（确认未被引用后）
- **Dependencies**：确认 mcp_server.py 是唯一注册路径
- **Required Agents**：mcp-engineer
- **Tasks**：
  - T5.4.1：全局搜索 `from ai.tools import` 确认无引用 ✅（*.py 全仓库零引用；importlib/pkgutil 无动态加载）
  - T5.4.2：删除 `ai/tools/` 目录 ✅（11 stub + __init__，另连带删除孤儿 ai/context.py 与 ai/auth/ stub 体系，共 14 文件）
- **交付物**：`docs/features/F5.4-cleanup-ai-tools/`（SKILL.md 9 产物齐备）
- **验收结论**：READY_FOR_ACCEPTANCE（from app.main import 冒烟通过；删除后 grep 零残留；隔离执行 rbac 17/17、F5.2 18/18、F1.3 7/7、booking_ownership 10/10；混跑 3 个异常均为预存问题，单跑全绿）
- **关键改动**：纯删除型（14 文件）+ ai/__init__.py 1 行注释；mcp_server.py 成为唯一 Tool 注册点；契约/DB/配置/前端零变更
- **Epic 5 状态**：F5.1 / F5.2 / F5.3 / F5.4 全部 DONE

---

## Epic 6：业务域补全（Phase 3+）

### Feature 6.1：支付渠道接入

- **Goal**：支持在线支付购卡
- **Scope**：微信支付 / 支付宝
- **Dependencies**：order 模块业务逻辑
- **Required Agents**：backend-engineer, database-engineer
- **Tasks**：
  - T6.1.1：order 模块 Service/Router
  - T6.1.2：payment 模块接入微信支付
  - T6.1.3：支付回调 + 订单状态机

### Feature 6.2：通知系统

- **Goal**：会员卡到期、预约成功/取消等事件推送通知
- **Scope**：微信小程序订阅消息 / 短信
- **Dependencies**：无
- **Required Agents**：backend-engineer
- **Tasks**：
  - T6.2.1：notification 模块 Service
  - T6.2.2：接入微信订阅消息
  - T6.2.3：定时任务触发通知

> **Epic 6 立项说明（2026-10-21）**
> F6.0 是原型规划条目，不进入 feature-delivery-lifecycle 队列；以下 F6.3–F6.11 为可开发拆分。
> 产品负责人已冻结：**F6 先于 F7**、放弃 Figma、以 `docs/features/F6.0-membership-card-prototype/prototype/index.html` 为唯一设计依据，D1–D10 全部按推荐方案采纳（`open-decisions.md` 决策记录表）。
> 拆分原则：按"可独立交付、可独立验收、依赖单向"切分；F6.3 为首个实施项（P0），F6.4–F6.7 为 P1，F6.8–F6.9 为 P2/Blocked，UI 集中到 F6.10–F6.11，避免后端能力未就绪时前端先行造假设。

### Feature 6.3：会员卡扣次与期卡激活状态机（D1 / D4 / D5 / D9）✅ DONE（2026-10-22，人工验收有条件通过）

- **Status**：DONE（后端范围；合并/上线前须完成下文「验收条件」）
- **Priority**：P0（Epic 6 首个实施项）
- **Goal**：把"D1 预约预扣 + COMPLETED 确认""D9 期卡首次完成激活 + 预期有效期冲突预校验""D4 有效期边界""D5 缺席自动消解"落到 Service / Scheduler，形成次卡与期卡可验证的生命周期闭环。
- **Scope**：
  - 次卡：预约时预扣（现状保留）、取消回补（现状保留）、课程完成/缺席不额外扣次；明确"确认"为无操作幂等语义。
  - 期卡：发卡 PENDING 且 `valid_from/expire_at` 留空；预约不扣次、不激活；按排期日 + `validity_days` 计算预期有效期做同课程类型区间重叠预校验；课程完成/缺席时首次激活并写入真实有效期。
  - PENDING 期卡 90 天无完成记录自动 CANCELLED；freeze 拒绝 PENDING；过期扫描扩展为 `status IN (ACTIVE, PENDING)` 且 `expire_at IS NOT NULL`。
  - 课程完成触发点：`BookingStatus.COMPLETED` / `NO_SHOW`（真实代码的排期结束由 `schedule/scheduler.py` 批量写入），不引入不存在的 `ScheduleStatus.COMPLETED`。
  - 边界：`expire_at` 当天 23:59:59 前可预约/可完成；未来生效的 PENDING 卡不可预约。
- **Out of Scope**：D2 用尽状态、D3 失效替代与受影响预约、D6 多卡推荐、D7 改期/改派、D8 退款、D10 跨排期重叠、任何前端页面改造、通知推送（F6.2）、支付（F6.1）。
- **Dependencies**：F4.1（booking→card FK SET NULL）、F4.4（status Check 约束）、F2.3（签到/完成行锁）、F2.4（取消排期回补回滚）均已 DONE；无前置未完成 Feature。
- **Current Code Gaps（真实代码证据）**：
  - 期卡发卡即计算 `valid_from=now`、`expire_at` 并可能直接 ACTIVE：`apps/api/src/app/modules/membership/service.py:396-428`；与"D9 发卡一律 PENDING、有效期留空"冲突。
  - `deduct_credit` 要求 `status=ACTIVE` 且用 `now` 校验有效期，PENDING 期卡无法预约：`membership/service.py:1348-1363`；期卡 `total_credits IS NULL` 不扣次：同文件 `1365-1368`。
  - 课程完成只改 booking 状态，不触碰卡：`apps/api/src/app/modules/booking/service.py:305-332`。
  - 排期自动结束直接 bulk update 预约状态，未触发卡激活，且业务规则写在 Scheduler：`apps/api/src/app/modules/schedule/scheduler.py:90-111`；`ScheduleStatus` 只有 NORMAL/CANCELLED/FINISHED：`schedule/models.py:12-15`。
  - freeze 未拒绝 PENDING（仅拦 FROZEN/EXPIRED/CANCELLED）：`membership/service.py:624-632`。
  - 过期扫描仅 `status=ACTIVE`：`membership/scheduler.py:283-289`；自动激活会把带 `valid_from` 的 PENDING 卡直接激活：`membership/scheduler.py:136-140,203`。
  - 无 90 天 PENDING 自动作废任务（scheduler 仅 4 个任务）。
  - 预约时无期卡预期有效期冲突预校验：`booking/service.py:51-160` 全链路无卡有效期区间判断。
  - `restore_credit` 对期卡也会 `used_credits -= 1`：`membership/service.py:1427-1434`，期卡回补语义未分支。
- **Tasks**：
  - T6.3.1：`issue_card` 期卡分支改为 PENDING + 空有效期；非期卡行为不变（`membership/service.py`）。
  - T6.3.2：新增期卡预约校验与预期有效期冲突预校验（Service 层，复用区间重叠口径）；预约链路按卡类型分支，期卡不调 `deduct_credit`。
  - T6.3.3：新增期卡完成激活方法（行锁 + 状态重检 + 幂等键）；`complete_booking` 与排期结束批量 finalize 均调用。
  - T6.3.4：将排期结束的预约终态处理从 Scheduler 直写收口到 `BookingService.finalize_schedule_bookings`（禁止 Scheduler 直接写业务状态）。
  - T6.3.5：`restore_credit` 调用方按期卡/次卡分支；期卡取消不回补。
  - T6.3.6：freeze 拒绝 PENDING；过期扫描扩展；新增 PENDING 超期作废任务（90 天，可配置）。
  - T6.3.7：补单测/集成/并发测试；回归 F2.3/F2.4/F4.1/F4.4/F4.5。
- **Required Agents**：project-architect（设计对账）、backend-engineer（实现）、database-engineer（无迁移评估 + 锁/索引复核）
- **Definition of Ready**：是。F6.0 决策表 D1/D4/D5/D9 已确认；真实代码缺口已逐项定位；无未决 D 编号；无 DB 结构变更即可实施（是否新增配置项由设计确认）。
- **Acceptance 概要**：期卡发卡为 PENDING 且无有效期；期卡预约不扣次、冲突拒绝；完成/缺席后首次激活且日期正确；次卡完成不重复扣；取消期卡不回补；PENDING 不可冻结；过期/90 天任务正确；完成/激活并发幂等；跨租户隔离；无分层违规。
- **交付物**：`docs/features/F6.3-membership-card-state-machine/`（requirement / user-flow / acceptance / implementation-plan / implementation-report / static-verification / runtime-test-report / review / release-note，共 9 份 + 1 份任务遥测记录）
- **验收结论（2026-10-22）**：后端范围 **PASS（有条件）**。定向 41 passed（修复后连续 23 轮）+ 回归 118 passed（2 次）；`py_compile` 21 文件、`ruff` All checks passed；迁移 `a7b8c9d0e1f2` 本地 upgrade/downgrade/upgrade 往返通过、回填 9 张卡 0 NULL；改动范围无越界。
- **验收条件（合并/上线前必须完成）**：
  1. 补跑全量 `pytest`（本次仅定向 + 11 个回归文件）
  2. 补 C-4（跨租户卡预约）与 C-7（PENDING 作废任务租户隔离）用例
  3. 生产快照统计 90 天作废任务首日受影响 PENDING 卡数量（或先 dry-run / 临时关闭 `PENDING_CARD_CANCEL_ENABLED`）
- **未验证（NOT VERIFIED）**：四端联调 / 小程序 PENDING 展示（F6.10/F6.11）、多实例 APScheduler 互斥、生产库回填量、OpenAPI 前后 diff、`mypy`。
- **新登记技术债**：
  - D-F6.3-1（中）：多实例 APScheduler 无分布式互斥，PENDING 作废/过期任务可能重复执行（当前依赖幂等，未做实机验证）
  - D-F6.3-2（中）：全量 `pytest` 未纳入本次验证，建议 CI 前置为合并门控
  - D-F6.3-3（低）：`membership/models.py` 新列 `validity_days` 用 `Integer`，与设计文档的 `SmallInteger` 不一致（已人工接受，与产品表同类型）
  - D-F6.3-4（低）：并发测试中出现 1 次未复现的 4 failed（疑与并行 `py_compile` 写 `.pyc` 竞争），根因 UNKNOWN

### Feature 6.4：预约跨排期时间段重叠校验（D10）✅ DONE（2026-10-22，人工验收通过）

- **Status**：DONE（后端范围）
- **Priority**：P1（建议紧随 F6.3）
- **Goal**：同一学员的进行中预约所在排期时间段与目标排期重叠时拒绝预约。
- **Scope**：`BookingRepository` 新增区间重叠查询；`BookingService.create_booking` 在同排期查重后、容量/扣次前校验；半开区间 `a.start < b.end AND b.start < a.end`；状态仅 `BOOKED/CHECKED_IN`。
- **Out of Scope**：不改 D9 卡有效期冲突；不改排期创建冲突；不新增端点/DTO；不做"自动取消旧约再改约"。
- **Dependencies**：无（独立小改动）；与 F6.3 同日开发时需先合并 F6.4，减少 `create_booking` 冲突。
- **Current Code Gaps**：
  - `create_booking` 无跨排期查询：`apps/api/src/app/modules/booking/service.py:87-89`。
  - `find_active_booking` 只按 schedule_id + student_id：`booking/repository.py:123-151`。
  - 已有区间重叠范式可复用：`schedule/repository.py:142-146`（`start_at < end_at AND end_at > start_at`）。
  - 时间字段带时区：`schedule/models.py:42-43`；学员维度索引：`booking/models.py:78`。
- **Tasks**：T6.4.1 Repository 方法；T6.4.2 Service 校验与错误文案；T6.4.3 单测/集成/并发/跨租户；T6.4.4 4 端影响确认（无契约变更）。
- **Required Agents**：backend-engineer, database-engineer
- **Definition of Ready**：是。`D10-booking-time-conflict-validation.md` 已立项；第 11 节待确认项需在开工前由 Architect 拍板（建议：不覆盖式改约、同课程不豁免、纳入 CHECKED_IN、排除 COMPLETED、文案带课程名）。
- **Acceptance 概要**：重叠拒绝且不落库不扣次；边界相接放行；CANCELLED/COMPLETED/NO_SHOW 不参与；CHECKED_IN 参与；跨租户互不影响；并发至多一个成功；D9 校验不回归。
- **交付物**：`docs/features/F6.4-booking-time-overlap/`（requirement / user-flow / acceptance / implementation-plan / implementation-report / static-verification / runtime-test-report / review / release-note，共 9 份 + 任务遥测记录）
- **验收结论（2026-10-22）**：后端范围 **PASS**。定向 8 条 × 11 次（含 10 轮稳定性）+ F6.3 定向 41 + 通用回归 118 全通过；`py_compile` / `ruff` 首轮通过；无迁移、无契约变更、无返工。
- **关键实现**：`BookingRepository.find_overlapping_active_booking`（半开区间、`BOOKED/CHECKED_IN`）+ `lock_student_booking_scope`（`pg_advisory_xact_lock` 串行化同一学员预约创建，因真实入口为 READ COMMITTED）；`create_booking` 在卡校验后、占名额前校验；文案含课程名与时间段。
- **未验证（NOT VERIFIED）**：全量 `pytest`、D-2 并发取消 vs 预约、C-3 的 API 级双租户（仅 Repository 层验证）、多实例 advisory lock、四端联调、`mypy`。
- **新登记技术债**：
  - D-F6.4-1（中）：advisory lock 使用 `(int4, int4)` 双键，ID 超 2^31 会溢出（当前量级安全）
  - D-F6.4-2（中）：取消/完成链路不取该锁，理论无死锁环但缺 D-2 用例实证
  - D-F6.4-3（低）：冲突文案时区固定 `Asia/Shanghai`，多区域部署需改租户级配置

### Feature 6.5：原子改期 / 原子改派（D7）✅ DONE（2026-10-22）

- **Status**：✅ DONE（2026-10-22，人工验收通过；D-6 已修复后 Close）
- **Priority**：P1
- **Goal**：一次事务内完成"回补原卡 → 锁定新排期 → 扣/校验新卡（可同卡）→ 更新预约"，消除两步改期的"已回补未锁定"窗口。
- **Scope**：新增改期端点（建议 `POST /api/v1/bookings/{id}/reschedule`，请求 `new_schedule_id` + 可选 `new_membership_card_id`）；改派复用同一事务骨架；行锁顺序与幂等键；OpenAPI 同步。
- **Out of Scope**：不自动取消旧约后重约的旧语义；不做批量改期；不做 UI（由 F6.10/F6.11 消费）。
- **Dependencies**：F6.3（期卡不扣次/激活后的卡状态语义）；F6.4（目标排期时间段重叠校验必须复用）。
- **Current Code Gaps**：
  - 无 reschedule/改派端点：`booking/router.py` 仅 create/list/get/cancel/check-in/complete。
  - 改期=取消+重约，两个独立 `commit()`：`booking/service.py:156,269`，中间态窗口真实存在。
  - 无"回补+新扣+改名额"的复合事务方法。
- **Tasks（实际）**：T6.5.1 模型 + 迁移；T6.5.2~T6.5.4 Repository / 排期锁 / 卡锁入口；T6.5.5~T6.5.7 Service 复合事务 + DTO/路由 + OpenAPI/types；T6.5.8 集成/并发/幂等测试；T6.5.9~T6.5.10 静态验证与评审；T6.5.11 排期取消锁硬化（D-6）。前端契约交接见 F6.10/F6.11。
- **Required Agents**：backend-engineer, database-engineer, project-architect（契约冻结）
- **Definition of Ready**：需先确认端点路径/请求体与错误码；F6.3、F6.4 已合并。
- **Acceptance 概要**：改期成功旧约 CANCELLED + 新约 BOOKED 同事务；任一步失败全部回滚；同卡/换卡两路径；目标满员/时间重叠/卡不可用均拒绝且旧约保持；重复提交幂等；跨租户/越权 403/404。
- **交付物**：`docs/features/F6.5-atomic-reschedule/`（requirement / user-flow / acceptance / implementation-plan / implementation-report / static-verification / runtime-test-report / review / release-note，共 9 份）+ `docs/engineering/task-records/20261022-F6.5-atomic-reschedule.md`。
- **验收结论（2026-10-22）**：**人工验收通过**。定向功能 31 + 并发 9（含 D-6 两条，连续 10 轮稳定）全通过；定向回归 93（分两批，含 RBAC 17）通过；`py_compile` / `ruff` / 迁移往返 / `alembic check` 通过；租户隔离 2 例既有事件循环失败与本 Feature 无关。
- **关键实现**：`POST /api/v1/bookings/{booking_id}/reschedule`；`BookingService.reschedule_booking` 复合事务；固定锁序 advisory → booking → schedule(id ASC) → card(id ASC)；`booking_reschedules` 审计表 + 两个部分唯一索引；`populate_existing=True` 修复并发旧快照；**T6.5.11** 将 `cancel_schedule` 改为 booking(id ASC) → schedule 并持锁重收集/过滤 BOOKED，消除 D-6。
- **未验证（NOT VERIFIED）**：B-5、B-11 其余分支、B-14 冻结/过期/课程类型不适配、B-15、C-9、D-7/D-9、全量 `pytest`、生产多实例；以上前四项已由人工验收判定逻辑正确，但仍未落单测。
- **新登记技术债**：
  - D-F6.5-1：排期取消 vs 改期并发（D-6）—— **已关闭**（T6.5.11 锁硬化 + 2 条并发用例）
  - D-F6.5-2（中）：期卡 PENDING 锚点可能漂移，旧 PENDING 卡可能永久失去锚点（B-5 未单测，人工已接受）
  - D-F6.5-3（低）：`booking_reschedules` 无业务 FK，排期/预约硬删后可能产生孤儿引用
  - D-F6.5-4（低）：目标排期校验规则与 `create_booking` 重复，存在漂移风险
  - D-F6.5-5（低）：D-10 跨 booking 同幂等键与两个约束 409 分支未覆盖
  - D-F6.5-6（低）：`test_booking_ownership.py` 的 `booking_data` 为 session 级 fixture，与 `now+3d` 同时段的其它用例同会话运行会触发既有时间重叠校验，回归需分批执行

### Feature 6.6：多卡默认推荐策略（D6）

- **Status**：READY（前端部分依赖 F6.3 的卡可用语义）
- **Priority**：P1
- **Goal**：统一"先过期优先 → 剩余次数少优先 → 同分取先发放"的默认推荐，避免小程序本地规则与后端不一致。
- **Scope**：后端新增推荐能力（建议 `GET /api/v1/membership/recommend-card?course_id=&schedule_id=` 或在 `my-cards` 响应增加推荐字段，二选一由 Architect 冻结）；小程序 `booking-confirm` 改为消费后端推荐；无可用卡空态与理由展示。
- **Out of Scope**：不做自动替卡/自动顺延（D3）；不做多卡同时扣次；不改发卡/扣次事务。
- **Dependencies**：F6.3（PENDING/ACTIVE/用尽/课程类型语义稳定）；契约冻结后前端才编码（v3 R5）。
- **Current Code Gaps**：
  - 小程序本地推荐：unlimited→period→count，且次卡按剩余次数**降序**：`apps/miniapp/src/pages/student/booking-confirm/index.vue:552-615`；与 D6"剩余少优先、先过期优先"相反/缺失。
  - 后端无推荐端点：`membership/router.py` 无 recommend 路由。
  - `my-cards` 返回全部卡（含过期/作废）：`membership/router.py:247-257`，过滤在 `booking-confirm/index.vue:642-654`。
- **Tasks**：T6.6.1 推荐策略纯函数 + Service；T6.6.2 端点/DTO；T6.6.3 小程序替换本地排序；T6.6.4 单测 + 小程序 vue-tsc/build。
- **Required Agents**：backend-engineer, frontend-engineer, project-architect（契约）
- **Definition of Ready**：需冻结"推荐字段 vs 独立端点"；需确认同分"先发放"以 `created_at` 还是 `id` 排序（建议 `created_at, id`）。
- **Acceptance 概要**：给定固定卡集合推荐顺序稳定；无可用卡返回空原因；过期/未来生效/冻结/课程不适用被排除；两端显示一致；无契约漂移。
- **交付物**：`docs/features/F6.6-card-recommendation/`。

### Feature 6.7：卡失效替代与受影响预约（D3）

- **Status**：READY（依赖 F6.5 的改派能力）
- **Priority**：P1
- **Goal**：冻结/过期/作废卡时能查询受影响的有效预约；学员可自助换卡改派，无卡时引导联系机构；管理端操作前展示影响面。
- **Scope**：后端新增"受影响预约"查询（建议 `GET /api/v1/membership/cards/{id}/affected-bookings`）；管理端冻结/作废确认弹窗展示 N 条；小程序预约列表警示条 + 换卡入口（复用 F6.5 改派）；无替代卡空态。
- **Out of Scope**：不做自动顺延；不自动取消预约；不做通知推送（F6.2）。
- **Dependencies**：F6.5（原子改派）、F6.3（卡状态语义）；admin/miniapp UI 契约需冻结。
- **Current Code Gaps**：
  - `conflict-check` 只查同课程类型卡冲突，不查预约：`membership/service.py:674-717`。
  - 冻结/作废直接改状态，无预约影响面：`membership/service.py:624-672,1529-1576`。
  - admin 会员卡页无"受影响预约"提示：`apps/admin-web/src/views/membership/index.vue`（作废弹窗仅原因，`:394-414`）。
  - 小程序我的预约无计划卡状态警示：`apps/miniapp/src/pages/student/bookings/index.vue`（现有列表无卡状态字段）。
- **Tasks**：T6.7.1 Repository/Service 查询；T6.7.2 端点 + 权限（admin 全量、学员仅本人）；T6.7.3 admin 影响面弹窗；T6.7.4 小程序警示条 + 换卡跳转；T6.7.5 测试（归属、跨租户、空态）。
- **Required Agents**：backend-engineer, frontend-engineer
- **Definition of Ready**：需冻结"受影响"状态口径（建议 BOOKED/CHECKED_IN 且未开始）；需确认学员查询端点归属校验。
- **Acceptance 概要**：作废/冻结前返回准确 N 条；学员只能看自己；换卡成功走 F6.5 原子事务；无卡时仅人工出口；空态/错误态齐全。
- **交付物**：`docs/features/F6.7-card-invalid-replacement/`。

### Feature 6.8：次卡余额用尽展示（D2）

- **Status**：READY（低风险）
- **Priority**：P2
- **Goal**：不新增 EXHAUSTED 状态，用余额徽标/文案表达"已用尽"，并在选卡时过滤/灰显。
- **Scope**：miniapp 会员卡列表/详情/预约选卡；admin 会员卡列表状态列辅助文案（不新增筛选枚举）；student-web 若 F6.11 已落地则同步。
- **Out of Scope**：不改枚举、不改 Check 约束、不改 scheduler、不改扣次规则。
- **Dependencies**：F6.3（期卡/次卡状态与余额口径稳定）；F6.6（选卡推荐语义）。
- **Current Code Gaps**：
  - 无 EXHAUSTED 枚举：`membership/models.py:49-57`；余额为属性：`models.py:250-254`。
  - 小程序已有"已用完"分组但仅本地判断：`apps/miniapp/src/pages/student/membership/index.vue:767-777`。
  - 选卡过滤本地计算：`booking-confirm/index.vue:328-329,521-524`。
- **Tasks**：T6.8.1 统一"已用尽"文案/徽标；T6.8.2 选卡灰显与原因；T6.8.3 四态与构建自验。
- **Required Agents**：frontend-engineer
- **Definition of Ready**：是。D2 已冻结；仅展示层。
- **Acceptance 概要**：remaining=0 的 ACTIVE 次卡显示"已用尽"且不可选；不改变后端状态值；过期/冻结/作废徽标不混淆；vue-tsc/build 通过。
- **交付物**：`docs/features/F6.8-exhausted-card-display/`。

### Feature 6.9：退款入口占位（D8）

- **Status**：BLOCKED（依赖 F6.1 支付渠道，FUTURE_PHASE）
- **Priority**：P2（F6.1 启动后再排）
- **Goal**：管理端卡详情提供"申请退款"入口占位，明确标注依赖 F6.1，不产生任何退款写操作。
- **Scope**：仅 UI 占位 + 文案；不新增端点、不写 REFUND 流水、不改卡状态。
- **Out of Scope**：退款审批流、线下退款登记、撤销核销、支付回调。
- **Dependencies**：F6.1（支付/订单）；F6.10（管理端卡详情页）。
- **Current Code Gaps**：
  - `REFUND` 仅枚举：`membership/models.py:66`；service/router 无退款实现。
  - admin 卡详情弹窗无退款入口：`apps/admin-web/src/views/membership/index.vue:299-361`。
- **Tasks**：T6.9.1 占位按钮/提示；T6.9.2 明令禁用点击与请求；T6.9.3 文案审查。
- **Required Agents**：frontend-engineer
- **Definition of Ready**：F6.1 已立项/启动；否则保持 BLOCKED。
- **Acceptance 概要**：按钮灰置、无网络请求、无状态变更；文案含"依赖 F6.1"；不出现假端点。
- **交付物**：`docs/features/F6.9-refund-placeholder/`。

### Feature 6.10：管理端预约管理与卡详情/流水 UI

- **Status**：READY（依赖后端能力）
- **Priority**：P1（预约管理）/ P2（卡详情流水）
- **Goal**：补齐 admin-web 预约管理入口、排期名单代签到/完成、会员卡详情与流水、受影响预约影响面。
- **Scope**：新增 `/bookings` 路由与页面（按排期/学员/状态筛选，代签到/完成，复用 `booking:manage`）；会员卡详情抽屉增加流水（`GET /membership/transactions`）；接入 F6.7 影响面。
- **Out of Scope**：不做退款（F6.9）；不做改期（F6.5 仅后端，UI 另评估）；不做卡产品编辑重构。
- **Dependencies**：F6.3/F6.4/F6.5/F6.7 后端契约；`@dance-saas/api-client` 与 `api-types` 重新生成。
- **Current Code Gaps**：
  - admin 路由无 bookings：`apps/admin-web/src/router/index.ts:74-84`（仅 tenant/membership/card-types）。
  - 会员卡页无流水调用：`views/membership/index.vue` 全文无 `getTransactions`；api-client 已有方法：`packages/api-client/src/membership.ts:229-237`；后端端点存在：`membership/router.py:486-507`。
  - 教师端无"完成"按钮：`apps/teacher-web/src/views/students/index.vue:169-171` 仅 checkIn。
- **Tasks**：T6.10.1 路由/页面/四态；T6.10.2 代签到/完成；T6.10.3 卡详情流水；T6.10.4 影响面；T6.10.5 vue-tsc/build。
- **Required Agents**：frontend-engineer, backend-engineer（契约核对）
- **Definition of Ready**：后端端点冻结；`gen:types` 完成；逐方法核对端点存在。
- **Acceptance 概要**：预约页可按排期查名单并代签到/完成；四态齐全；流水字段与后端一致且学员 PII 最小化；403/409/500 正确展示；无虚构端点。
- **交付物**：`docs/features/F6.10-admin-booking-card-ui/`。

### Feature 6.11：学员端卡详情与流水（miniapp + student-web）

- **Status**：BLOCKED（先修归属/越权缺口）
- **Priority**：P2
- **Goal**：学员可查看单卡详情、有效期、余额与使用记录；student-web 补齐会员卡入口。
- **Scope**：miniapp 新增卡详情/流水页（消费 `getCardDetail` / `getTransactions`）；student-web 新增会员卡列表/详情/流水页；预约选卡复用 F6.6 推荐。
- **Out of Scope**：购卡/支付（F6.1）；退款（F6.9）；改期 UI（F6.5）。
- **Dependencies**：F6.3/F6.8；**安全前置**：`GET /membership/cards/{id}` 与 `GET /membership/transactions` 当前仅租户校验、无学员归属校验（`membership/router.py:260-269,486-507`；`service.py:471-479,587-606`），必须先补归属校验，否则不得暴露 UI。
- **Current Code Gaps**：
  - miniapp API 已有 `getCardDetail`/`getTransactions`，但 `pages.json` 无卡详情/流水页：`apps/miniapp/src/api/index.ts:623,635`；`pages.json:133` 仅会员卡列表。
  - student-web 全目录无 membership 引用（`grep` 零命中）。
  - 后端详情/流水无学员归属校验（见上）。
- **Tasks**：T6.11.1 后端归属校验（独立安全修复，先合入）；T6.11.2 miniapp 两页；T6.11.3 student-web 三页/入口；T6.11.4 四态 + 多端构建。
- **Required Agents**：frontend-engineer, backend-engineer（安全前置）
- **Definition of Ready**：归属校验修复通过安全评审；契约冻结。
- **Acceptance 概要**：学员只能看自己的卡与流水；他人卡 403/404；流水字段与 admin 口径一致但无 operator/幂等键；空态/loading/error 齐全；两端构建通过。
- **交付物**：`docs/features/F6.11-student-card-detail/`。

### Epic 6 推荐实施顺序与依赖图

```
F6.3（P0，后端状态机）
  ├─→ F6.4（P1，预约时间重叠，建议紧随/同批）
  ├─→ F6.5（P1，原子改期/改派，依赖 F6.3+F6.4）
  │      └─→ F6.7（P1，失效替代，依赖 F6.5）
  ├─→ F6.6（P1，推荐策略，契约冻结后小程序）
  └─→ F6.8（P2，用尽展示）
F6.1（FUTURE）─→ F6.9（P2，退款占位）
F6.3/F6.4/F6.5/F6.7 ─→ F6.10（P1/P2，admin UI）
F6.3/F6.8 + 归属校验 ─→ F6.11（P2，学员端卡详情）
```

**顺序理由**：F6.3 是所有卡语义的权威来源，先落地可避免前端/F6.6/F6.7 基于旧行为做兼容；F6.4 与 F6.3 同改 `create_booking`，先合并小改动降低冲突；F6.5 依赖 F6.4 的重叠校验作为改期目标校验；F6.7 必须复用 F6.5 的事务骨架才不会再造第二套改派逻辑。

---

## Epic 7：运维与可观测性（Phase 5）

### Feature 7.1：数据库备份

- **Goal**：生产数据库每日自动备份
- **Scope**：pg_dump 定时任务 + 异地存储
- **Required Agents**：backend-engineer
- **Tasks**：
  - T7.1.1：备份脚本
  - T7.1.2：cron / CI 调度
  - T7.1.3：恢复演练

### Feature 7.2：监控与告警

- **Goal**：核心指标可视化 + 异常告警
- **Scope**：Prometheus + Grafana（或云服务）
- **Required Agents**：backend-engineer
- **Tasks**：
  - T7.2.1：应用指标暴露
  - T7.2.2：Grafana 面板
  - T7.2.3：告警规则

### Feature 7.3：CI 测试覆盖

- **Goal**：CI 运行 integration 测试，类型检查阻塞
- **Scope**：ci.yml 增加 integration 测试；mypy 改为阻塞
- **Required Agents**：backend-engineer
- **Tasks**：
  - T7.3.1：ci.yml 加 `pytest tests/integration`
  - T7.3.2：mypy `continue-on-error: false`
  - T7.3.3：前端三端 + miniapp 类型检查加入 CI

---

## 附录：F3.1 实施期间新发现的技术债（2026-09-26 登记）

> 以下来自 F3.1 实施/验证过程的发现，不属于 F3.1 Scope，登记待排期。

| # | 债务项 | 来源 | 建议归属 |
|---|--------|------|---------|
| D-F3.1-1 | miniapp 未配置 lint（package.json 无 lint 脚本），代码风格仅靠人工约束 | static-verification.md | F3.2 或独立前端工具链 Feature |
| D-F3.1-2 | `tenantApi.getSettings()` 返回类型为 `{}`，`student/schedule/index.vue:572` 访问 `.booking_cancel_minutes` 报 TS 错误；租户设置缺少强类型 DTO | runtime-test-report U2 / vue-tsc | F3.2（27 个存量错误之一） |
| D-F3.1-3 | `student/schedule/index.vue` 存在 F3.1 之前的预存未提交改动（`validateCardForSchedule` 区域），归属待定 | static-verification.md 第 5 节 | 用户决策：保留/拆分提交/还原 |
| D-F3.1-4 | 教师两页存在未使用的 `goToXxx` 声明（IDE 诊断，疑似 TabBar 导航残留） | implementation-report.md Risks | F3.2 存量错误清零时一并处理 |

---

## 附录：F4.5 实施期间确认的技术债（2026-10-02 登记）

> 以下为 F4.5 双专家评审中确认但**不属于本 Feature Scope** 的并发/清理缺口，登记待排期。F4.5 仅加固单个 `create_schedule`，未顺手扩范围。

| # | 债务项 | 风险 | 来源 | 建议归属 |
|---|--------|------|------|---------|
| D-F4.5-1 | `batch_create_schedules`（`POST /schedules/batch`，端点存活）仍为 READ COMMITTED + `find_conflicts(use_lock=True)`：既无 SSI 兜底空集双插，`SKIP LOCKED` 还会吞被预约/取消 RC 事务持锁的已存在冲突行 | 中 | review.md L7 / requirement.md U2 | 独立 Feature，按 F4.5 同方案（SERIALIZABLE + 快照谓词读 + 40001 重试，批量需评估逐条/整批语义） |
| D-F4.5-2 | `update_schedule` 仍为 READ COMMITTED + 快照读：更新时间字段时存在 write skew（两事务各改不同排期至同一重叠时段均提交成功） | 中低 | review.md L7 | 独立 Feature；与 D-F4.5-3 可合并评估 |
| D-F4.5-3 | 缺少数据库层防重叠最终保证：建议 `btree_gist` 扩展 + 两条部分排他约束（`USING gist (tenant_id, teacher_id, tstzrange(start_at,end_at))` / classroom 同构，`WHERE status=NORMAL`） | 低（纵深防御） | requirement.md U3 / review.md L8 | 专项 DBA Feature：扩展安装、约束设计、存量越界数据校验、与应用层 40001 重试的错误映射 |
| D-F4.5-4 | `find_conflicts` 内手工 `tenant_id` 谓词与 ORM 租户自动注入叠加且无注释；排期 router 集合端点尾斜杠 `/schedules/` 不符 contracts.md（集合端点不加尾斜杠） | 低 | review.md L6 | 后端清理小项（随相关模块改动顺带处理） |

### F4.5 评审 LOW 项（非技术债，随版本已知项发布，见 release-note）

非 40001 异常统一转 500 文案略宽泛（L1）；commit 后 refresh 理论"成功报失败"窗口（L2）；重试无 backoff/jitter、rollback 依赖上游无写约定（L3）；教室状态事务外校验 TOCTOU（L4，存量行为）；并发测试缺教室维度/跨租户/连接池复位/混跑隔离级别用例（L5）。
