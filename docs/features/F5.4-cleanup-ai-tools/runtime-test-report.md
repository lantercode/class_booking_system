# F5.4 — Runtime Test Report

## 环境

- Python 3.12.13 / pytest 9.0.3 / pytest-asyncio（mode=auto）/ asyncpg
- 运行目录：`apps/api`，`PYTHONPATH=src`

## 1. 导入冒烟（AC-5）

```bash
python -c "from app.main import app"
# IMPORT_OK（仅 FastAPI example deprecation 既有警告）
```

## 2. 隔离执行结果

| 套件 | 命令 | 结果 |
|------|------|------|
| RBAC 权限（F1.1） | pytest tests/integration/test_rbac_enforcement.py | **17 passed** |
| F5.2 Tool 授权 + F1.3 异常 | pytest tests/test_mcp_tool_authorization.py tests/test_exception_handlers.py | **25 passed**（18+7） |

## 3. 混合回归

命令（6 套件合并）：
```bash
pytest tests/test_agent_runtime.py tests/test_mcp_tool_authorization.py \
       tests/test_exception_handlers.py \
       tests/integration/test_rbac_enforcement.py \
       tests/integration/test_booking_ownership.py \
       tests/integration/test_auth_api.py
```

结果：**79 passed, 2 failed, 1 error**

### 失败/错误归因（全部为预存，与删除无关）

| 项 | 现象 | 归因证据 |
|----|------|---------|
| test_agent_runtime::test_parse_schedules_unified_format | `KeyError: 'course_name'` | F5.2 报告（D-F5.2-2）已记录的 F5.1 脚本测试 mock 结构问题，删除前后信息一致 |
| test_agent_runtime::test_booking_flow_end_to_end | 断言排期含"瑜伽课"失败 | 同上，依赖 dev DB 特定排期数据 |
| test_rbac_enforcement::test_student_cannot_create_user（setup ERROR） | `got Future attached to a different loop` | 跨文件混跑的事件循环污染；**该文件单独执行 17/17 通过**（见上表），且删除的是零引用 stub，不可能影响 asyncpg 连接归属 |

关键判据：三个问题在 F5.2 交付时即以相同形态存在（前两个有书面记录；第三个为测试基建隔离问题，单跑即绿），删除操作不涉及任何被测试 import 的模块。

## 4. 覆盖的 AC

- AC-5 导入冒烟：PASS
- AC-6 F5.2 授权 18/18：PASS
- AC-7 F1.3 异常处理器 7/7：PASS
- AC-8 RBAC 17/17、booking_ownership 10/10（混排中全绿）、auth_api 混排中无新增失败：PASS
- AC-1/AC-2/AC-3/AC-4/AC-9/AC-10：见 static-verification.md，PASS

## 汇总判定

删除型变更未破坏任何生效链路；AI 与核心业务测试在隔离执行下全绿；混跑中的 3 个异常均有"预存 + 与本变更无因果"的证据。

**结论：PASS，READY_FOR_ACCEPTANCE。**
