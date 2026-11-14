"""ArkProvider 单测：httpx.MockTransport，不联网。"""

import asyncio
import json

import httpx
import pytest

from app.ai.llm.ark import ArkProvider
from app.ai.llm.base import (
    LLMAuthError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)

_API_KEY = "unit-test-secret-key"


def _make_provider(handler, *, max_retries: int = 2) -> ArkProvider:
    return ArkProvider(
        api_key=_API_KEY,
        base_url="https://ark.example.com/api/v3",
        model="doubao-seed-2-1-lite-260915",
        timeout_ms=1000,
        max_retries=max_retries,
        max_tokens=800,
        transport=httpx.MockTransport(handler),
    )


def _ok_payload() -> dict:
    return {
        "choices": [
            {
                "message": {"content": "你好，我是助手", "tool_calls": None},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7},
    }


@pytest.mark.asyncio
async def test_request_payload_disables_thinking_and_streaming():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=_ok_payload())

    provider = _make_provider(handler)
    try:
        await provider.chat(messages=[{"role": "user", "content": "hi"}])
    finally:
        await provider.aclose()

    body = captured["body"]
    assert body["thinking"] == {"type": "disabled"}
    assert body["stream"] is False
    assert body["temperature"] == 0.3
    assert body["max_tokens"] == 800
    assert body["model"] == "doubao-seed-2-1-lite-260915"
    assert captured["auth"] == f"Bearer {_API_KEY}"
    assert "tools" not in body


@pytest.mark.asyncio
async def test_parse_content_tool_calls_and_usage():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "query_courses",
                                        "arguments": '{"keyword": "瑜伽"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 30, "completion_tokens": 9},
            },
        )

    provider = _make_provider(handler)
    try:
        result = await provider.chat(
            messages=[{"role": "user", "content": "瑜伽课"}],
            tools=[{"type": "function", "function": {"name": "query_courses"}}],
        )
    finally:
        await provider.aclose()

    assert result.content == ""
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "call_1"
    assert result.tool_calls[0].name == "query_courses"
    # arguments 保持 JSON 字符串原文，不做解析
    assert result.tool_calls[0].arguments == '{"keyword": "瑜伽"}'
    assert result.prompt_tokens == 30
    assert result.completion_tokens == 9
    assert result.finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_auth_error_maps_and_does_not_retry():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401, json={"error": "invalid key " + _API_KEY})

    provider = _make_provider(handler)
    try:
        with pytest.raises(LLMAuthError) as exc_info:
            await provider.chat(messages=[{"role": "user", "content": "hi"}])
    finally:
        await provider.aclose()

    assert calls["count"] == 1
    message = str(exc_info.value)
    assert _API_KEY not in message
    assert "ark.example.com" not in message


@pytest.mark.asyncio
async def test_rate_limit_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, json={"error": "too many"})
        return httpx.Response(200, json=_ok_payload())

    provider = _make_provider(handler, max_retries=2)
    try:
        result = await provider.chat(messages=[{"role": "user", "content": "hi"}])
    finally:
        await provider.aclose()

    assert calls["count"] == 2
    assert result.content == "你好，我是助手"


@pytest.mark.asyncio
async def test_timeout_retries_exhausted(monkeypatch):
    calls = {"count": 0}

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.ReadTimeout("upstream timeout", request=request)

    provider = _make_provider(handler, max_retries=1)
    try:
        with pytest.raises(LLMTimeoutError):
            await provider.chat(messages=[{"role": "user", "content": "hi"}])
    finally:
        await provider.aclose()

    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_rate_limit_error_after_retries_exhausted(monkeypatch):
    calls = {"count": 0}

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(429, json={"error": "too many"})

    provider = _make_provider(handler, max_retries=1)
    try:
        with pytest.raises(LLMRateLimitError):
            await provider.chat(messages=[{"role": "user", "content": "hi"}])
    finally:
        await provider.aclose()

    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_invalid_json_raises_response_error():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, content=b"not-a-json")

    provider = _make_provider(handler)
    try:
        with pytest.raises(LLMResponseError):
            await provider.chat(messages=[{"role": "user", "content": "hi"}])
    finally:
        await provider.aclose()

    # 响应解析错误不重试
    assert calls["count"] == 1
