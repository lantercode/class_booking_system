"""火山方舟（Volcengine Ark）OpenAI 兼容 Provider。

唯一外部 HTTP 调用点：
  - ``POST {base_url}/chat/completions``，非流式；
  - 固定关闭深度思考（``thinking={"type": "disabled"}``），不提供开关；
  - 状态码映射为统一异常族，退避重试仅针对超时 / 限流 / 5xx。

安全约束：
  - 日志只记录 model / 耗时 / token / 工具调用数 / 重试次数；
  - 禁止记录 messages、tools 内容与 API Key；
  - 异常 message 使用固定中文文案，不透传上游响应原文。
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

import httpx

from app.ai.llm.base import (
    LLMAuthError,
    LLMBadRequestError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseError,
    LLMServerError,
    LLMTimeoutError,
    ToolCall,
)

logger = logging.getLogger(__name__)

# 关闭深度思考后 TTFT 从 ~13s 降到 ~0.6s（实测），必须显式传参，不允许配置放开
_THINKING_DISABLED = {"type": "disabled"}
_DEFAULT_TEMPERATURE = 0.3


class ArkProvider(LLMProvider):
    """方舟 Chat Completions Provider（httpx 直连，不依赖官方 SDK）。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_ms: int,
        max_retries: int,
        max_tokens: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_retries = max(0, max_retries)
        self._max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_ms / 1000),
            transport=transport,
        )

    # ========================================================
    # 对外接口
    # ========================================================

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": _DEFAULT_TEMPERATURE,
            "max_tokens": self._max_tokens,
            "stream": False,
            "thinking": dict(_THINKING_DISABLED),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"

        retry_count = 0
        while True:
            started = time.perf_counter()
            try:
                try:
                    response = await self._client.post(
                        f"{self._base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
                except httpx.TimeoutException as exc:
                    raise LLMTimeoutError() from exc
                except httpx.HTTPError as exc:
                    raise LLMServerError() from exc
                result = self._parse_response(response)
            except (LLMTimeoutError, LLMRateLimitError, LLMServerError) as exc:
                elapsed_ms = (time.perf_counter() - started) * 1000
                if retry_count >= self._max_retries:
                    logger.warning(
                        "[LLM] request_failed provider=ark model=%s error_type=%s "
                        "elapsed_ms=%.1f retry_count=%d",
                        self._model,
                        type(exc).__name__,
                        elapsed_ms,
                        retry_count,
                    )
                    raise
                retry_count += 1
                logger.warning(
                    "[LLM] retry provider=ark model=%s attempt=%d error_type=%s elapsed_ms=%.1f",
                    self._model,
                    retry_count,
                    type(exc).__name__,
                    elapsed_ms,
                )
                await asyncio.sleep(_backoff_seconds(retry_count))
                continue

            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "[LLM] request_ok provider=ark model=%s elapsed_ms=%.1f "
                "prompt_tokens=%s completion_tokens=%s tool_call_count=%d retry_count=%d",
                self._model,
                elapsed_ms,
                result.prompt_tokens,
                result.completion_tokens,
                len(result.tool_calls),
                retry_count,
            )
            return result

    async def aclose(self) -> None:
        await self._client.aclose()

    # ========================================================
    # 内部实现
    # ========================================================

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _parse_response(self, response: httpx.Response) -> LLMResponse:
        """状态码映射 + 响应体解析；所有失败都转成统一异常族。"""
        status = response.status_code
        if status in (401, 403):
            raise LLMAuthError(code=status)
        if status == 429:
            raise LLMRateLimitError(code=status)
        if status in (400, 404):
            raise LLMBadRequestError(code=status)
        if status >= 500:
            raise LLMServerError(code=status)
        if status >= 400:
            raise LLMBadRequestError(code=status)

        try:
            data = response.json()
        except ValueError:
            # 抑制异常链，避免上游响应片段经 traceback 外泄
            raise LLMResponseError() from None

        return _to_llm_response(data)


def _to_llm_response(data: Any) -> LLMResponse:
    """从 OpenAI 兼容响应中提取 content / tool_calls / usage / finish_reason。"""
    if not isinstance(data, dict):
        raise LLMResponseError()

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMResponseError()

    choice = choices[0]
    if not isinstance(choice, dict):
        raise LLMResponseError()

    message = choice.get("message")
    if not isinstance(message, dict):
        raise LLMResponseError()

    raw_content = message.get("content")
    if raw_content is None:
        content = ""
    elif isinstance(raw_content, str):
        content = raw_content
    else:
        raise LLMResponseError()

    tool_calls: list[ToolCall] = []
    raw_tool_calls = message.get("tool_calls")
    if raw_tool_calls is not None:
        if not isinstance(raw_tool_calls, list):
            raise LLMResponseError()
        for item in raw_tool_calls:
            tool_calls.append(_to_tool_call(item))

    usage = data.get("usage")
    prompt_tokens = completion_tokens = None
    if isinstance(usage, dict):
        prompt_tokens = _optional_int(usage.get("prompt_tokens"))
        completion_tokens = _optional_int(usage.get("completion_tokens"))

    finish_reason = choice.get("finish_reason")
    if finish_reason is not None and not isinstance(finish_reason, str):
        finish_reason = None

    return LLMResponse(
        content=content,
        tool_calls=tuple(tool_calls),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        finish_reason=finish_reason,
    )


def _to_tool_call(item: Any) -> ToolCall:
    if not isinstance(item, dict):
        raise LLMResponseError()

    function = item.get("function")
    if not isinstance(function, dict):
        raise LLMResponseError()

    call_id = item.get("id")
    name = function.get("name")
    # arguments 必须是字符串：保持原文，不做 JSON 解析
    arguments = function.get("arguments")
    if not isinstance(call_id, str) or not isinstance(name, str) or not isinstance(arguments, str):
        raise LLMResponseError()

    return ToolCall(id=call_id, name=name, arguments=arguments)


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _backoff_seconds(attempt: int) -> float:
    """指数退避 + 抖动：0.3 * 2^(n-1) + random(0~0.2)。"""
    return 0.3 * (2 ** (attempt - 1)) + random.uniform(0, 0.2)
