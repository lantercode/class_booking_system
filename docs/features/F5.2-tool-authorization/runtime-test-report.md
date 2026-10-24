# F5.2 — Runtime Test Report

## 环境

- Python 3.12，pytest 9.0.3，FastAPI + SQLAlchemy async（asyncpg）
- 运行目录：`apps/api`，`PYTHONPATH=src`

## 新增测试结果

命令：
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_mcp_tool_authorization.py -v
```

结果：**18 passed**

| 测试类 / 用例 | AC | 结果 |
|---------------|----|----|
| TestValidateId::test_valid_id | AC-4/7 | PASS |
| TestValidateId::test_zero | AC-4/7 | PASS |
| TestValidateId::test_negative | AC-4/7 | PASS |
| TestValidateId::test_string | AC-4/7 | PASS |
| TestValidateId::test_bool | AC-4/7 | PASS |
| TestValidateId::test_none | AC-4/7 | PASS |
| TestCreateBooking::test_no_user_id_raises_401 | AC-1 | PASS |
| TestCreateBooking::test_invalid_schedule_id_raises_400 | AC-4 | PASS |
| TestCreateBooking::test_negative_schedule_id_raises_400 | AC-4 | PASS |
| TestCreateBooking::test_string_schedule_id_raises_400 | AC-4 | PASS |
| TestCreateBooking::test_non_student_role_raises_403（Service spy=0） | AC-2/3 | PASS |
| TestCancelBooking::test_no_user_id_raises_401 | AC-5 | PASS |
| TestCancelBooking::test_invalid_booking_id_raises_400 | AC-7 | PASS |
| TestCancelBooking::test_reason_too_long_raises_400 | AC-8 | PASS |
| TestCancelBooking::test_non_student_role_raises_403（Service spy=0） | AC-6 | PASS |
| FriendlyMessage::test_student_role_message（原文 not-in） | AC-10 | PASS |
| FriendlyMessage::test_invalid_id_message | AC-10 | PASS |
| FriendlyMessage::test_unknown_error_no_leak（SELECT/DROP not-in） | AC-11 | PASS |

## F5.3 错误映射回归

命令：
```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_agent_runtime.py::test_business_error_handling -v -s
```

结果：10/10 用例全部"匹配=是、泄露=否"（约满/已预约/扣次失败/未找到/取消截止/已开始/两周/已取消/状态/未知兜底）。

## 集成回归

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_rbac_enforcement.py tests/integration/test_booking_ownership.py
# 27 passed（rbac 17 + booking_ownership 10）
```

## 已知预存失败（非本 Feature 引入）

`tests/test_agent_runtime.py` 中 2 个用例失败，在本 Feature 修改逻辑**之前**（仅补 tenant_id 参数后）即以相同信息失败：

- `test_parse_schedules_unified_format`：`KeyError: 'course_name'`（脚本式 mock 数据结构与当前解析器不一致）；
- `test_booking_flow_end_to_end`：断言排期含"瑜伽课"，依赖 dev DB 中存在特定排期数据。

二者均为 F5.1 脚本测试对 DB 数据/mock 结构的依赖，与四关校验改动无关。建议后续将这两个脚本式用例改造为自造数据的标准 pytest 用例（技术债，不阻塞 F5.2）。

## 汇总判定

- 新增 18/18 PASS
- F5.3 映射 10/10 PASS
- 集成回归 27/27 PASS
- 预存失败 2 个（已定位、与本 Feature 无关）

**结论：AC-1 ~ AC-11、AC-13、AC-14 运行时验证通过。**
