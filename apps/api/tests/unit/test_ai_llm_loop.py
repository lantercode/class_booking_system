"""AgentLoop 单测（不联网 / 不连 DB / 不连 Redis）。"""

import asyncio

import pytest

from app.ai.agent.loop import FALLBACK_REPLY, AgentLoop
from app.ai.llm.base import LLMResponse, ToolCall
from app.ai.mcp_server import ToolOutcome


class ScriptedProvider:
    """按脚本依次返回响应的假 Provider。"""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.received: list[list[dict]] = []

    async def chat(self, *, messages, tools=None, tool_choice=None):
        self.calls += 1
        self.received.append(list(messages))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def aclose(self):
        return None


class SlowProvider:
    async def chat(self, *, messages, tools=None, tool_choice=None):
        await asyncio.sleep(5)
        return LLMResponse(content="不应到达")

    async def aclose(self):
        return None


def _tool_call(call_id: str = "c1", arguments: str = "{}", name: str = "query_courses") -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=arguments)


def _final(content: str = "最终回答") -> LLMResponse:
    return LLMResponse(content=content)


TOOLS = [{"type": "function", "function": {"name": "query_courses"}}]


async def _run(provider, executor, *, max_loops=2, budget_ms=5000, allowed=None, limit=4000):
    loop = AgentLoop(
        provider,
        max_loops=max_loops,
        total_budget_ms=budget_ms,
        tool_result_max_chars=limit,
    )
    return await loop.run(
        messages=[{"role": "user", "content": "查课程"}],
        tools=TOOLS,
        allowed_tools=allowed or {"query_courses"},
        executor=executor,
    )


@pytest.mark.asyncio
async def test_tool_then_final_answer():
    provider = ScriptedProvider(
        [
            LLMResponse(content="", tool_calls=(_tool_call("c1", '{"keyword": "瑜伽"}'),)),
            _final("找到 1 门瑜伽课"),
        ]
    )
    calls: list[tuple[str, dict]] = []

    async def executor(name, args):
        calls.append((name, args))
        return ToolOutcome("success", "共 1 门课程：瑜伽")

    result = await _run(provider, executor)

    assert result.reply == "找到 1 门瑜伽课"
    assert result.llm_calls == 2
    assert result.tool_calls == 1
    assert result.fallback_reason is None
    assert calls == [("query_courses", {"keyword": "瑜伽"})]

    second_messages = provider.received[1]
    assert any(m.get("role") == "assistant" and m.get("tool_calls") for m in second_messages)
    tool_messages = [m for m in second_messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "c1"
    assert tool_messages[0]["content"].startswith("[TOOL_RESULT name=query_courses status=success]")


@pytest.mark.asyncio
async def test_unknown_tool_not_executed():
    provider = ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=(_tool_call("c1", "{}", name="hack_tool"),),
            ),
            _final("好的"),
        ]
    )

    async def executor(name, args):  # pragma: no cover - 不应被调用
        raise AssertionError("未知工具不得执行")

    result = await _run(provider, executor)

    assert result.reply == "好的"
    assert result.tool_calls == 0
    tool_messages = [m for m in provider.received[1] if m.get("role") == "tool"]
    assert "该工具不可用" in tool_messages[0]["content"]


@pytest.mark.asyncio
async def test_invalid_json_not_executed():
    provider = ScriptedProvider(
        [
            LLMResponse(content="", tool_calls=(_tool_call("c1", "{not-json"),)),
            _final("好的"),
        ]
    )

    async def executor(name, args):  # pragma: no cover
        raise AssertionError("非法参数不得执行")

    result = await _run(provider, executor)

    assert result.tool_calls == 0
    tool_messages = [m for m in provider.received[1] if m.get("role") == "tool"]
    assert "参数无效" in tool_messages[0]["content"]


@pytest.mark.asyncio
async def test_identity_fields_are_dropped():
    provider = ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=(
                    _tool_call(
                        "c1",
                        '{"keyword": "瑜伽", "user_id": 999, "tenant_id": 888,'
                        ' "tenant_slug": "evil"}',
                    ),
                ),
            ),
            _final("完成"),
        ]
    )
    calls: list[dict] = []

    async def executor(name, args):
        calls.append(args)
        return ToolOutcome("success", "ok")

    await _run(provider, executor)

    assert calls == [{"keyword": "瑜伽"}]


@pytest.mark.asyncio
async def test_overlong_arguments_not_executed():
    arguments = '{"keyword": "' + "x" * 2500 + '"}'
    provider = ScriptedProvider(
        [
            LLMResponse(content="", tool_calls=(_tool_call("c1", arguments),)),
            _final("好的"),
        ]
    )

    async def executor(name, args):  # pragma: no cover
        raise AssertionError("超长参数不得执行")

    result = await _run(provider, executor)

    assert len(arguments) > 2000
    assert result.tool_calls == 0


@pytest.mark.asyncio
async def test_per_loop_tool_call_limit():
    provider = ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=(
                    _tool_call("c1", '{"keyword": "a"}'),
                    _tool_call("c2", '{"keyword": "b"}'),
                    _tool_call("c3", '{"keyword": "c"}'),
                ),
            ),
            _final("完成"),
        ]
    )
    calls: list[str] = []

    async def executor(name, args):
        calls.append(args["keyword"])
        return ToolOutcome("success", "ok")

    result = await _run(provider, executor)

    assert calls == ["a", "b"]
    assert result.tool_calls == 2
    tool_messages = [m for m in provider.received[1] if m.get("role") == "tool"]
    assert any("本轮工具调用数量已达上限" in m["content"] for m in tool_messages)


@pytest.mark.asyncio
async def test_duplicate_tool_calls_executed_once():
    provider = ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=(
                    _tool_call("c1", '{"keyword": "瑜伽"}'),
                    _tool_call("c2", '{"keyword": "瑜伽"}'),
                ),
            ),
            _final("完成"),
        ]
    )
    calls: list[dict] = []

    async def executor(name, args):
        calls.append(args)
        return ToolOutcome("success", "共 1 门课程")

    result = await _run(provider, executor)

    assert len(calls) == 1
    assert result.tool_calls == 1
    tool_messages = [m for m in provider.received[1] if m.get("role") == "tool"]
    assert len(tool_messages) == 2
    assert tool_messages[0]["content"] == tool_messages[1]["content"]


@pytest.mark.asyncio
async def test_business_and_system_error_message_format():
    provider = ScriptedProvider(
        [
            LLMResponse(
                content="",
                tool_calls=(
                    _tool_call("c1", "{}", name="query_schedules"),
                    _tool_call("c2", "{}", name="get_my_bookings"),
                ),
            ),
            _final("完成"),
        ]
    )
    outcomes = [
        ToolOutcome("business_error", "当前账号没有学员身份", code=403, error_type="Permission"),
        ToolOutcome("system_error", "操作失败，请稍后重试或联系客服", error_type="RuntimeError"),
    ]

    async def executor(name, args):
        return outcomes.pop(0)

    allowed = {"query_schedules", "get_my_bookings"}
    result = await _run(provider, executor, allowed=allowed)

    assert result.tool_calls == 2
    contents = [m["content"] for m in provider.received[1] if m.get("role") == "tool"]
    assert contents[0].startswith(
        "[TOOL_RESULT name=query_schedules status=business_error code=403]"
    )
    assert contents[1].startswith("[TOOL_RESULT name=get_my_bookings status=system_error]")
    for content in contents:
        assert "error_type" not in content
        assert "data" not in content.split("\n")[0]


@pytest.mark.asyncio
async def test_tool_result_is_truncated_by_lines():
    provider = ScriptedProvider(
        [
            LLMResponse(content="", tool_calls=(_tool_call("c1", "{}"),)),
            _final("完成"),
        ]
    )
    long_text = "\n".join(f"第 {i} 行课程信息" for i in range(200))

    async def executor(name, args):
        return ToolOutcome("success", long_text)

    await _run(provider, executor, limit=100)

    content = next(m["content"] for m in provider.received[1] if m.get("role") == "tool")
    assert content.endswith("（内容已截断）")
    assert len(content) <= 120


@pytest.mark.asyncio
async def test_max_loops_stops():
    responses = [
        LLMResponse(content="", tool_calls=(_tool_call(f"c{i}", '{"keyword": "a"}'),))
        for i in range(5)
    ]
    provider = ScriptedProvider(responses)

    async def executor(name, args):
        return ToolOutcome("success", "ok")

    result = await _run(provider, executor, max_loops=2)

    assert result.llm_calls == 2
    assert result.fallback_reason == "max_loops_exceeded"
    assert result.reply == FALLBACK_REPLY


@pytest.mark.asyncio
async def test_budget_exceeded_returns_fallback_without_raising():
    async def executor(name, args):  # pragma: no cover
        raise AssertionError("预算耗尽不应执行工具")

    result = await _run(SlowProvider(), executor, budget_ms=50)

    assert result.fallback_reason == "budget_exceeded"
    assert result.reply == FALLBACK_REPLY
    assert result.llm_calls == 0
