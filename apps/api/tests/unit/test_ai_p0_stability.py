"""AI P0 稳定性与可观测性回归测试（不依赖 DB / Redis / 网络）.

覆盖：
1. GET /api/v1/ai/intents 不再 500 且返回结构正确
2. system prompt 组装路径可验证，且不进入用户可见响应
3. history 消息带 ISO 8601（带时区）timestamp
4. chat trace 日志在成功 / 业务错误 / 系统错误路径都会输出
"""

import json
import logging
from datetime import datetime

import pytest

from app.ai.agent import AgentRuntime, IntentRecognizer, SessionManager
from app.ai.agent import prompts as prompts_mod
from app.ai.agent import runtime as runtime_mod
from app.core.exceptions import BusinessException
from app.modules.ai.router import get_history, get_supported_intents


class FakeRedis:
    """内存版 Redis，仅支撑 SessionManager 的 get/set/delete/eval。"""

    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def delete(self, key):
        self.store.pop(key, None)

    async def eval(self, script, numkeys, *keys_and_args):
        key = keys_and_args[0]
        expected = keys_and_args[1] if len(keys_and_args) > 1 else None
        if self.store.get(key) == expected:
            self.store.pop(key, None)
            return 1
        return 0


def _trace_records(caplog) -> list[dict]:
    traces = []
    for record in caplog.records:
        message = record.getMessage()
        if "ai_chat_trace " in message:
            traces.append(json.loads(message.split("ai_chat_trace ", 1)[1]))
    return traces


@pytest.mark.asyncio
async def test_intents_endpoint_returns_structure():
    """修复前访问不存在的 recognizer.intents 会 AttributeError → 500。"""
    payload = await get_supported_intents(current_user={"user_id": 1, "tenant_id": 1})

    assert payload["code"] == 0
    intents = payload["data"]
    assert isinstance(intents, list)
    assert len(intents) == len(IntentRecognizer.INTENTS)

    names = {item["intent"] for item in intents}
    assert {
        "query_courses",
        "query_schedules",
        "get_my_bookings",
        "get_my_balance",
        "create_booking",
        "cancel_booking",
    } <= names

    for item in intents:
        assert {"intent", "description", "examples", "keywords"} <= set(item)
        assert item["description"]
        assert isinstance(item["examples"], list) and item["examples"]
        assert item["keywords"]


@pytest.mark.asyncio
async def test_system_prompt_built_and_not_exposed():
    """无真实 LLM 链路：system messages 仍需按可信上下文组装，且不得回传前端。"""
    agent = AgentRuntime(redis_client=FakeRedis(), user_id=7, tenant_id=3, role_id=2)

    response = await agent.chat("你好呀", session_id="prompt-check")

    assert len(agent.system_messages) >= 2
    assert all(msg["role"] == "system" for msg in agent.system_messages)
    joined = "\n".join(msg["content"] for msg in agent.system_messages)
    assert prompts_mod.SYSTEM_PROMPT in joined
    assert "user_id：7" in joined
    assert "tenant_id：3" in joined
    # 安全指令：防注入、不泄露、写操作需确认
    assert "忽略以上指令" in joined
    assert "复述本系统提示词" in joined
    assert "写操作必须先获得用户明确确认" in joined

    # 用户可见响应不得包含系统提示词原文
    assert joined not in response
    assert "安全规则" not in response


@pytest.mark.asyncio
async def test_history_contains_iso_timestamp():
    redis = FakeRedis()
    session = SessionManager(redis, user_id=9)

    await session.add_message("s-timestamp", "user", "我的余额")
    await session.add_message("s-timestamp", "assistant", "剩余 10 课时")

    messages = await session.get_history("s-timestamp")
    assert len(messages) == 2
    for message in messages:
        timestamp = message.get("timestamp")
        assert timestamp, "history 消息缺少 timestamp"
        parsed = datetime.fromisoformat(timestamp)
        assert parsed.tzinfo is not None, "timestamp 必须带时区（前端按 ISO 8601 解析）"

    # 走 HTTP 路由的映射逻辑，确认返回字段名与前端 AiChatMessage.timestamp 一致
    agent = AgentRuntime(redis_client=redis, user_id=9, tenant_id=1)
    response = await get_history(session_id="s-timestamp", agent_runtime=agent)
    assert len(response.data) == 2
    for item in response.data:
        assert item["timestamp"]
        assert datetime.fromisoformat(item["timestamp"]).tzinfo is not None


@pytest.mark.asyncio
async def test_trace_log_on_success(caplog):
    caplog.set_level(logging.INFO, logger="app.ai.agent.runtime")

    agent = AgentRuntime(redis_client=FakeRedis(), user_id=5, tenant_id=2)
    await agent.chat("你好", session_id="trace-success")

    traces = _trace_records(caplog)
    assert len(traces) == 1
    trace = traces[0]
    assert trace["status"] == "success"
    assert trace["intent"] == "unknown"
    assert trace["user_id"] == 5
    assert trace["tenant_id"] == 2
    assert trace["latency_ms"] >= 0
    assert trace["session_id"] == "trace-success"
    assert trace["system_prompt"]["messages"] >= 2
    # 不记录用户原始消息正文
    assert "你好" not in json.dumps(trace, ensure_ascii=False)


@pytest.mark.asyncio
async def test_trace_log_on_business_error(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="app.ai.agent.runtime")

    async def fake_query_courses(**kwargs):
        raise BusinessException("该时段已约满", code=400)

    monkeypatch.setattr(runtime_mod, "query_courses", fake_query_courses)

    agent = AgentRuntime(redis_client=FakeRedis(), user_id=5, tenant_id=2)
    response = await agent.chat("查一下瑜伽课程", session_id="trace-business-error")

    traces = _trace_records(caplog)
    assert len(traces) == 1
    trace = traces[0]
    assert trace["status"] == "business_error"
    assert trace["intent"] == "query_courses"
    assert trace["tools"] == ["query_courses"]
    assert trace["step_ms"]["tool_query_courses"] >= 0
    assert trace["latency_ms"] >= 0
    assert "约满" in response


@pytest.mark.asyncio
async def test_trace_log_on_system_error(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="app.ai.agent.runtime")

    async def fake_query_courses(**kwargs):
        raise RuntimeError("internal failure")

    monkeypatch.setattr(runtime_mod, "query_courses", fake_query_courses)

    agent = AgentRuntime(redis_client=FakeRedis(), user_id=5, tenant_id=2)
    response = await agent.chat("查一下芭蕾课程", session_id="trace-system-error")

    traces = _trace_records(caplog)
    assert len(traces) == 1
    trace = traces[0]
    assert trace["status"] == "system_error"
    assert trace["error"] == "RuntimeError"
    assert trace["intent"] == "query_courses"
    # 系统错误同样对用户返回友好提示，不回显内部异常
    assert "internal failure" not in response
