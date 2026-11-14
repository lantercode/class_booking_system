"""AgentRuntime Phase 1 分流与回退单测（不联网 / 不连 DB / 不连 Redis）。"""

from types import SimpleNamespace

import pytest

from app.ai.agent import runtime as runtime_module
from app.ai.agent.runtime import WRITE_INTENT_REPLY, AgentRuntime
from app.ai.llm.base import LLMResponse, LLMTimeoutError, ToolCall
from app.ai.mcp_server import ToolOutcome


async def _async(value):
    return value


def _settings(**overrides):
    values = {
        "AI_LLM_READONLY_ONLY": True,
        "AI_LLM_MAX_TOOL_LOOPS": 2,
        "AI_LLM_TOTAL_BUDGET_MS": 15000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeProvider:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def chat(self, *, messages, tools=None, tool_choice=None):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def aclose(self):
        return None


def _runtime(user_id=7, tenant_id=3) -> AgentRuntime:
    return AgentRuntime(redis_client=None, user_id=user_id, tenant_id=tenant_id)


def _capture_trace(monkeypatch) -> dict:
    captured: dict = {}
    monkeypatch.setattr(AgentRuntime, "_emit_trace", lambda self, trace: captured.update(trace))
    return captured


def _set_intent(monkeypatch, runtime: AgentRuntime, intent: str, params: dict) -> None:
    monkeypatch.setattr(
        runtime,
        "intent",
        SimpleNamespace(recognize=lambda _text: {"intent": intent, "params": params}),
    )


def _tools_payload() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "query_courses",
                "description": "查询课程",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


@pytest.mark.asyncio
async def test_llm_disabled_uses_rule_chain(monkeypatch):
    runtime = _runtime()
    trace = _capture_trace(monkeypatch)
    monkeypatch.setattr(runtime_module, "is_llm_enabled_for_tenant", lambda tid: False)
    monkeypatch.setattr(runtime_module, "get_settings", lambda: _settings())
    _set_intent(monkeypatch, runtime, "query_courses", {"keyword": "瑜伽"})

    async def fake_execute(tool_name, arguments):
        return ToolOutcome("success", "课程：瑜伽课")

    monkeypatch.setattr(runtime_module, "execute_tool", fake_execute)

    reply = await runtime.chat("查瑜伽课", session_id="s1")

    assert "瑜伽课" in reply
    assert trace["mode"] == "rule"
    assert trace["llm_calls"] == 0


@pytest.mark.asyncio
async def test_tenant_not_in_whitelist_skips_llm(monkeypatch):
    runtime = _runtime()
    _capture_trace(monkeypatch)
    monkeypatch.setattr(runtime_module, "is_llm_enabled_for_tenant", lambda tid: False)
    monkeypatch.setattr(runtime_module, "get_settings", lambda: _settings())
    _set_intent(monkeypatch, runtime, "query_courses", {})

    async def fake_execute(tool_name, arguments):
        return ToolOutcome("success", "课程A")

    monkeypatch.setattr(runtime_module, "execute_tool", fake_execute)
    monkeypatch.setattr(
        runtime_module, "get_llm_provider", lambda: pytest.fail("不应构造 Provider")
    )

    reply = await runtime.chat("查课程", session_id="s1")

    assert "课程A" in reply


@pytest.mark.asyncio
async def test_llm_enabled_uses_function_calling(monkeypatch):
    runtime = _runtime()
    trace = _capture_trace(monkeypatch)
    monkeypatch.setattr(runtime_module, "is_llm_enabled_for_tenant", lambda tid: True)
    monkeypatch.setattr(runtime_module, "get_settings", lambda: _settings())

    captured_ctx: dict = {}

    async def fake_tools(ctx, *, readonly_only=True):
        captured_ctx["user_id"] = ctx.user_id
        captured_ctx["tenant_id"] = ctx.tenant_id
        captured_ctx["readonly_only"] = readonly_only
        return _tools_payload()

    monkeypatch.setattr(runtime_module, "list_tool_definitions", fake_tools)

    monkeypatch.setattr(
        runtime_module,
        "get_llm_provider",
        lambda: FakeProvider([LLMResponse(content="已为您查询完成")]),
    )

    reply = await runtime.chat("查课程", session_id="s1")

    assert reply == "已为您查询完成"
    assert trace["mode"] == "llm"
    assert trace["llm_calls"] == 1
    assert trace["provider"] == "ark"
    assert trace["fallback_reason"] is None
    assert captured_ctx == {"user_id": 7, "tenant_id": 3, "readonly_only": True}


@pytest.mark.asyncio
async def test_provider_error_falls_back_to_rule_chain(monkeypatch):
    runtime = _runtime()
    trace = _capture_trace(monkeypatch)
    monkeypatch.setattr(runtime_module, "is_llm_enabled_for_tenant", lambda tid: True)
    monkeypatch.setattr(runtime_module, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        runtime_module,
        "list_tool_definitions",
        lambda ctx, readonly_only=True: _async(_tools_payload()),
    )
    monkeypatch.setattr(
        runtime_module,
        "get_llm_provider",
        lambda: FakeProvider([LLMTimeoutError()]),
    )
    _set_intent(monkeypatch, runtime, "query_courses", {})

    async def fake_execute(tool_name, arguments):
        return ToolOutcome("success", "课程A")

    monkeypatch.setattr(runtime_module, "execute_tool", fake_execute)

    reply = await runtime.chat("查课程", session_id="s1")

    assert "课程A" in reply
    assert trace["mode"] == "llm_fallback"
    assert trace["fallback_reason"] == "LLMTimeoutError"


@pytest.mark.asyncio
async def test_readonly_gate_blocks_write_intent_in_llm_mode(monkeypatch):
    runtime = _runtime()
    trace = _capture_trace(monkeypatch)
    monkeypatch.setattr(runtime_module, "is_llm_enabled_for_tenant", lambda tid: True)
    monkeypatch.setattr(runtime_module, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        runtime_module,
        "list_tool_definitions",
        lambda ctx, readonly_only=True: _async(_tools_payload()),
    )
    monkeypatch.setattr(
        runtime_module,
        "get_llm_provider",
        lambda: FakeProvider([LLMTimeoutError()]),
    )
    _set_intent(monkeypatch, runtime, "create_booking", {})

    async def forbidden(tool_name, arguments):  # pragma: no cover
        raise AssertionError("只读闸门下不得执行写 Tool")

    monkeypatch.setattr(runtime_module, "execute_tool", forbidden)

    state_calls: list[dict] = []

    async def record_state(session_id, state):
        state_calls.append(state)

    monkeypatch.setattr(runtime.session, "set_state", record_state)

    reply = await runtime.chat("帮我约课", session_id="s1")

    assert reply == WRITE_INTENT_REPLY
    assert state_calls == []
    assert trace["mode"] == "llm_fallback"


@pytest.mark.asyncio
async def test_identity_fields_from_model_are_filtered(monkeypatch):
    runtime = _runtime()
    _capture_trace(monkeypatch)
    monkeypatch.setattr(runtime_module, "is_llm_enabled_for_tenant", lambda tid: True)
    monkeypatch.setattr(runtime_module, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        runtime_module,
        "list_tool_definitions",
        lambda ctx, readonly_only=True: _async(_tools_payload()),
    )
    monkeypatch.setattr(
        runtime_module,
        "get_llm_provider",
        lambda: FakeProvider(
            [
                LLMResponse(
                    content="",
                    tool_calls=(
                        ToolCall(
                            id="c1",
                            name="query_courses",
                            arguments='{"keyword": "瑜伽", "user_id": 999, '
                            '"tenant_id": 888, "tenant_slug": "evil"}',
                        ),
                    ),
                ),
                LLMResponse(content="完成"),
            ]
        ),
    )

    received: list[dict] = []

    async def fake_execute(tool_name, arguments):
        received.append(arguments)
        return ToolOutcome("success", "课程A")

    monkeypatch.setattr(runtime_module, "execute_tool", fake_execute)

    reply = await runtime.chat("查瑜伽", session_id="s1")

    assert reply == "完成"
    assert received == [{"keyword": "瑜伽"}]
