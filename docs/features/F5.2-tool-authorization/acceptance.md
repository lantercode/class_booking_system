# F5.2 — Acceptance Criteria

| ID | 验收标准 | 验证方式 | 结果 |
|----|---------|---------|------|
| AC-1 | create_booking 在 user_id=None 时抛 BusinessException(code=401) | test_no_user_id_raises_401 | PASS |
| AC-2 | 非学员角色（教师/管理员/无角色）调 create_booking 抛 BusinessException(code=403)，消息含"学员" | test_non_student_role_raises_403 | PASS |
| AC-3 | 角色校验失败时 BookingService.create_booking 不被调用（monkeypatch spy） | test_non_student_role_raises_403 | PASS |
| AC-4 | schedule_id 为 0 / -1 / "1" / true / None 时抛 BusinessException(code=400) | test_invalid/negative/string_schedule_id + TestValidateId | PASS |
| AC-5 | cancel_booking 在 user_id=None 时抛 401 | test_no_user_id_raises_401 | PASS |
| AC-6 | 非学员角色调 cancel_booking 抛 403 且 Service 不被调用 | test_non_student_role_raises_403 | PASS |
| AC-7 | booking_id 非法值抛 400 | test_invalid_booking_id_raises_400 | PASS |
| AC-8 | reason 非 str / 超 200 字抛 400 友好错误 | test_reason_too_long_raises_400 | PASS |
| AC-9 | 角色关不替代归属关：学员通过角色关后仍受 Service 归属校验约束（两关独立） | 代码审查 + 既有 BookingService.cancel_booking 归属判断 | PASS |
| AC-10 | 授权异常经 Runtime 映射为友好文本，且原始异常字符串不作为子串出现 | test_student_role_message（not-in 断言） | PASS |
| AC-11 | 未知异常兜底"操作失败，请稍后重试或联系客服"，不泄露 SQL/堆栈 | test_unknown_error_no_leak（SELECT/DROP not-in） | PASS |
| AC-12 | 回归：test_agent_runtime 的意图识别、F5.3 错误映射用例仍通过 | pytest test_agent_runtime.py | PASS（2 个 DB 数据依赖用例为预存失败，见 runtime-test-report） |
| AC-13 | 分层合规：Tool 只调 Service/RBAC 核心，不直连 Repository、不裸 SQL、不直连 Redis | static-verification grep | PASS |
| AC-14 | `/api/v1/ai/chat` 请求/响应契约零变更，前端 4 端无改动 | 契约审查 | PASS |
