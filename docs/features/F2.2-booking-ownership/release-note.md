# F2.2 — Release Note

## 预约数据归属与泄露修复（2026-09-28）

### 功能变更

- `GET /api/v1/bookings`：强制角色归属过滤——学员只返回自己的预约；教师只返回其授课排期下的预约；admin/super_admin 全量可见。Router 不再做 `student_id` 推导（原逻辑在 `schedule_id` 存在时把 `student_id` 置 None，导致越权查看该排期下全租户学员预约）。
- `GET /api/v1/bookings/{id}`：新增归属校验——学员只能查自己创建的预约；教师只能查其授课排期下的预约；admin/super_admin 全量可查；其余返回 403「无权查看该预约」。跨租户或不存在的 `booking_id` 返回 404（不泄露存在性）。
- MCP `get_my_bookings` 工具：同步调用签名，student 用户行为不变（仍只返回自己的预约）；teacher 用户行为由"空列表"改为"见自己排期下的预约"（符合 T2.2.3 预期）。

### 兼容性

- API 路径、方法、查询参数、请求体、响应模型全部不变；`current_user` 是 `Depends(get_current_user)` 注入，不出现在 OpenAPI schema → 无需 `pnpm gen:types`。
- 响应字段集合不变（`_to_response` 不消费新增的内部 `teacher_id` 字段）。
- 前端 4 端影响评估：
  - admin-web：`GET /bookings` 全量可见，行为不变 → **不涉及**
  - student-web：原本只能看自己的预约，行为一致 → **不涉及**
  - teacher-web：`GET /bookings` 从"空"改为"见自己排期下的预约"——符合 T2.2.3 预期，前端无需改动（接口契约不变）
  - miniapp：`GET /bookings` 学员路径行为不变 → **不涉及**

### 修复

- 修复 `GET /bookings?schedule_id=<X>` 越权：学员可查看该排期下全租户所有学员预约的越权漏洞（Router 层 `student_id = current_user.get("user_id") if not schedule_id else None` 逻辑错误）。
- 修复 `GET /bookings/{id}` 无归属校验：任意认证用户凭任意 `booking_id` 可查任意同租户预约的越权漏洞。

### 运维与数据

- 无数据库结构变更，无需迁移。
- 无配置 / 环境变量变更。
- 无 Redis key 结构变更。

### 已知遗留（后续处理）

- `booking/router.py` 仍有 3 处 `student_id = current_user.get("user_id")` 在写操作端点（`create_booking` / `cancel_booking` / `cancel_booking_by_schedule`），均受 `@require_roles("student")` 限定，属 actor 自身身份而非越权过滤——不在 F2.2 Scope，建议后续单开债务项复核写操作端点归属校验完备性。
- `get_user_role_codes` 每次请求单次 DB 查询——若后续 list 接口 QPS 上升，可考虑加角色集合缓存（当前性能占比低，不阻塞）。
- 教师同时持有 student 角色时按优先级 student 赢（生产中不应出现此场景，如确有需要后续可加显式"切换视角"参数）。
