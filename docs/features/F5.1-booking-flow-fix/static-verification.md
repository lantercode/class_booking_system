# F5.1 — 静态校验报告

> 日期：2026-09-26
> 范围：F5.1 改动的全部 Python 文件

## 1. py_compile 语法校验

命令：
```bash
cd apps/api && .venv/bin/python -m py_compile \
  src/app/ai/mcp_server.py \
  src/app/ai/agent/runtime.py \
  src/app/ai/agent/intent.py \
  tests/test_agent_runtime.py
```

结果：`ALL_COMPILE_OK`（退出码 0）。

## 2. 格式一致性审查（query_schedules ↔ _parse_schedules）

采用同一个示例字符串做 round-trip 验证：

**query_schedules 实际产出的行格式**（来自 mcp_server.py f-string）：
```
- ID:{s.id} | {date_str} | {time_str} | {teacher} | 剩余:{remaining} | {course_name}
```

**_parse_schedules 正则**（来自 runtime.py）：
```
ID:(\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d:-]+)\s*\|\s*(.+?)\s*\|\s*剩余:(\d+)\s*\|\s*(.+?)\s*$
```

逐字段对照：

| 正则组 | 匹配内容 | 对应输出字段 | 一致性 |
|--------|---------|------------|--------|
| group(1) `(\d+)` | id | `{s.id}` | PASS |
| group(2) `(\d{4}-\d{2}-\d{2})` | date | `{date_str}`（%Y-%m-%d） | PASS |
| group(3) `([\d:-]+)` | time | `{time_str}`（HH:MM-HH:MM） | PASS |
| group(4) `(.+?)` | teacher | `{teacher}` | PASS |
| group(5) `(\d+)` 跟在 `剩余:` 后 | remaining | `{remaining}` | PASS |
| group(6) `(.+?)` 行尾 | course_name | `{course_name}` | PASS |

分隔符 ` | `（空格竖线空格）与正则 `\s*\|\s*` 一致。PASS。

## 3. 架构边界审查

| 检查项 | 结果 |
|--------|------|
| Tool 是否直连 Repository / 裸 SQL | PASS：query_schedules 仍调 `ScheduleService.list_schedules` |
| Tool 是否直连 Redis 做业务读写 | PASS：无新增 Redis 调用 |
| 是否改 Service 层 | PASS：ScheduleService / BookingService 未改动 |
| 是否改 OpenAPI 契约 | PASS：/ai/chat router 未改动 |
| 是否引入未鉴权网络入口 | PASS：FastMCP 仍 stdio |
| 身份/租户链路 | PASS：set_tenant_id / _require_auth 未动 |

## 4. 变更范围审查

F5.1 实际修改文件：
- `apps/api/src/app/ai/mcp_server.py`
- `apps/api/src/app/ai/agent/runtime.py`
- `apps/api/src/app/ai/agent/intent.py`
- `apps/api/tests/test_agent_runtime.py`

均在 AI 层（`apps/api/src/app/ai/`）与测试目录内，符合 `MCP Tool → Service → Repository → Database` 分层。

## 5. 结论

静态校验全部通过。格式两端严格一致，架构边界未越界。
