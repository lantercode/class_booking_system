# F5.2 — User Flow

## Flow 1：学员正常预约（Happy Path）

1. 学员在小程序对 AI 说"帮我预约明天的瑜伽课"。
2. AgentRuntime 从 `get_current_user` 注入 `user_id`（JWT，可信来源）。
3. 多轮选择排期后调用 `create_booking(schedule_id, user_id)`。
4. Tool 四关：认证通过 → 查角色含 `student` → `_validate_id` 通过 → 调 BookingService。
5. Service 完成容量/余额/冲突校验，返回预约成功。
6. AI 回复"预约成功"。

## Flow 2：教师/管理员账号尝试预约（Authorization 拒绝）

1. 教师账号对 AI 说"帮我预约"。
2. `_require_student_role` 查得角色集合 `{teacher}`，不含 `student`。
3. 抛 `BusinessException(code=403, "当前账号没有学员身份…")`，**BookingService 不会被调用**。
4. Runtime `_handle_business_error` 命中"学员身份"关键词，回复"当前账号没有学员身份，请使用学员账号登录后再试"。

## Flow 3：非法排期 ID（Input Validation 拒绝）

1. LLM 误传 `schedule_id=0` / `-1` / `"1"` / `true`。
2. `_validate_id` 抛 `BusinessException(code=400, "排期ID无效，请重新选择")`。
3. Runtime 命中"无效"关键词，回复"输入参数无效，请重新选择"。
4. 无 DB 查询发生。

## Flow 4：学员取消他人的预约（角色通过 + Service 归属拦截）

1. 学员角色通过第 2 关。
2. 调 `BookingService.cancel_booking(student_id=本人, booking_id=他人预约)`。
3. Service 归属校验抛业务异常（非 403）。
4. 证明角色关与归属关互不替代：前者判断"是不是学员"，后者判断"这条数据是不是你的"。

## Flow 5：未登录调用（Authentication 拒绝）

1. `user_id is None`（HTTP 侧 get_current_user 理论上已拦截，Tool 层兜底）。
2. 抛 `BusinessException(code=401)`，Runtime 返回登录引导。

## Error States

| 场景 | HTTP/Tool 码 | 用户可见回复 |
|------|-------------|-------------|
| 未登录 | 401 | 请先登录 |
| 非学员角色 | 403 | 当前账号没有学员身份 |
| ID 非法 | 400 | 输入参数无效，请重新选择 |
| 取消原因超 200 字 | 400 | 取消原因过长，请精简后重试 |
| 未知内部异常 | 不回显 | 操作失败，请稍后重试或联系客服 |

## Permissions

- 身份仅来自 `get_current_user` → AgentRuntime 注入；LLM 产出的内容不构成身份来源；
- Tool 不接受请求体中的 `tenant_id` 覆盖（当前 Tool 签名不含 tenant_id，租户由 ORM 租户事件链路保证）。
