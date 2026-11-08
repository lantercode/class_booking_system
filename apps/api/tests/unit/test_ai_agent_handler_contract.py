"""AI Tool 平台 Handler 契约回归测试（不依赖真实 DB / Redis / 网络）.

覆盖 P0-1：
1. TOOL_SPECS 与实际 Handler、MCP 入口函数三方一致，防止再次漂移；
2. execute_tool 必须调用 TOOL_SPECS.handler_name，而不是旧的 MCP 文本包装函数；
3. query_schedules 空结果也返回结构化 ToolOutcome，Runtime 不再依赖文本反解析；
4. AgentRuntime 全链路 mock，确认不会意外触发 SessionLocal。
"""

from types import SimpleNamespace

import pytest

from app.ai import mcp_server
from app.ai.agent.runtime import AgentRuntime
from app.ai.mcp_server import (
    TOOL_SPECS,
    ToolContext,
    ToolOutcome,
    execute_tool,
    tool_context,
)

# @mcp.tool 装饰后的入口函数名（与 TOOL_SPECS 的 key 一一对应）
MCP_ENTRYPOINTS = (
    "query_courses",
    "query_schedules",
    "get_my_bookings",
    "get_my_balance",
    "create_booking",
    "cancel_booking",
)


def test_tool_specs_handler_and_entrypoints_exist():
    """注册表、Handler、MCP 入口三方必须同时存在且可调用。"""
    assert set(TOOL_SPECS) == set(MCP_ENTRYPOINTS)

    for name, spec in TOOL_SPECS.items():
        assert spec.name == name
        handler = getattr(mcp_server, spec.handler_name, None)
        assert callable(handler), f"TOOL_SPECS[{name}] 指向的 handler 不存在: {spec.handler_name}"

        entrypoint = getattr(mcp_server, name, None)
        assert callable(entrypoint), f"缺少 @mcp.tool 入口函数: {name}"


@pytest.mark.asyncio
async def test_execute_tool_uses_spec_handler(monkeypatch):
    """回归：execute_tool 曾按函数名漂移，测试 monkeypatch query_schedules 实际无效。"""
    calls: list[dict] = []

    async def fake_impl(date=None, keyword="", days=7, user_id=None, tenant_id=None):
        calls.append(
            {
                "date": date,
                "keyword": keyword,
                "days": days,
                "user_id": user_id,
                "tenant_id": tenant_id,
            }
        )
        return ToolOutcome("success", "ok", data={"schedules": []})

    async def forbidden_wrapper(*args, **kwargs):  # pragma: no cover - 仅用于断言不被调用
        raise AssertionError("execute_tool 不应调用 MCP 文本包装函数 query_schedules")

    monkeypatch.setattr(mcp_server, "query_schedules_impl", fake_impl)
    monkeypatch.setattr(mcp_server, "query_schedules", forbidden_wrapper)

    with tool_context(ToolContext(user_id=1, tenant_id=1)):
        outcome = await execute_tool("query_schedules", {"date": "2026-11-07", "days": 3})

    assert outcome.ok is True
    assert outcome.data == {"schedules": []}
    assert calls == [
        {
            "date": "2026-11-07",
            "keyword": "",
            "days": 3,
            "user_id": 1,
            "tenant_id": 1,
        }
    ]


@pytest.mark.asyncio
async def test_mcp_wrapper_delegates_to_impl(monkeypatch):
    """MCP 文本入口只做包装，真实来源仍是 _impl，避免两套实现。"""
    calls: list[dict] = []

    async def fake_impl(date=None, keyword="", days=7, user_id=None, tenant_id=None):
        calls.append({"date": date, "days": days})
        return ToolOutcome("success", "排期文本")

    monkeypatch.setattr(mcp_server, "query_schedules_impl", fake_impl)

    text = await mcp_server.query_schedules(date="2026-11-07", days=2)

    assert text == "排期文本"
    assert calls == [{"date": "2026-11-07", "days": 2}]


@pytest.mark.asyncio
async def test_query_schedules_empty_result_is_structured_tool_outcome(monkeypatch):
    """空结果分支曾直接返回 str，导致 Runtime 无法消费 structured data。"""

    class FakeSessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeScheduleService:
        async def list_schedules(self, *args, **kwargs):
            return SimpleNamespace(items=[], total=0)

    async def fake_gate(*args, **kwargs):
        return ToolContext(user_id=1, tenant_id=1)

    monkeypatch.setattr(mcp_server, "SessionLocal", lambda: FakeSessionContext())
    monkeypatch.setattr(mcp_server, "ScheduleService", FakeScheduleService)
    monkeypatch.setattr(mcp_server, "_gate", fake_gate)

    outcome = await mcp_server.query_schedules_impl(date="2026-11-07", days=1)

    assert isinstance(outcome, ToolOutcome)
    assert outcome.ok is True
    assert outcome.data == {"schedules": []}
    assert "暂无排期" in outcome.text


@pytest.mark.asyncio
async def test_runtime_query_schedules_uses_structured_data(monkeypatch):
    """Runtime 全链路：只 monkeypatch Handler，不触碰 DB，也能格式化排期。"""

    async def fake_impl(date=None, keyword="", days=7, user_id=None, tenant_id=None):
        return ToolOutcome(
            "success",
            "- ID:101 | 2026-11-07 | 10:00-11:00 | 张老师 | 剩余:5 | 瑜伽",
            data={
                "schedules": [
                    {
                        "id": 101,
                        "date": "2026-11-07",
                        "time": "10:00-11:00",
                        "teacher": "张老师",
                        "remaining": 5,
                        "course_name": "瑜伽",
                    }
                ]
            },
        )

    monkeypatch.setattr(mcp_server, "query_schedules_impl", fake_impl)

    runtime = AgentRuntime(redis_client=None, user_id=1, tenant_id=1)
    reply = await runtime._execute_intent("query_schedules", {}, session_id="unit-test")

    assert "瑜伽" in reply
    assert "101" in reply or "10:00" in reply
