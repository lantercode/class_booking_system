"""Agent Function Calling 执行循环（Phase 1：只读）。

职责：
  - 调用 ``LLMProvider``，处理 tool_calls → executor → role=tool 消息 → 下一轮；
  - 所有 Tool 执行只经调用方注入的 ``executor``（Runtime 内部走 ``execute_tool``），
    本模块不 import 任何 Service / Repository / SQL / Redis；
  - LLM 产出的参数不可信：结构校验、白名单、身份字段丢弃、去重与数量上限都在这里收口。

安全约束：
  - 日志只记录 llm_calls / tool_call_count / fallback_reason / elapsed_ms，
    不记录消息正文与工具参数值；
  - tool 消息不携带 error_type 与 data 原始结构。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.ai.llm.base import LLMProvider, LLMResponse
from app.ai.mcp_server import TOOL_SPECS, ToolOutcome

logger = logging.getLogger(__name__)

FALLBACK_REPLY = "抱歉，我暂时无法完成这个查询，请稍后再试，或在小程序页面查看。"

# 单次工具调用参数上限（字符）
MAX_ARGUMENTS_CHARS = 2000
# 整请求最多执行的 Tool 调用次数
MAX_TOTAL_TOOL_CALLS = 5
# 身份字段永不由模型提供
IDENTITY_FIELDS = frozenset({"user_id", "tenant_id", "tenant_slug"})

TOOL_UNAVAILABLE_TEXT = "该工具不可用，请勿调用。"
INVALID_ARGUMENTS_TEXT = "参数无效，请重新说明。"
LOOP_LIMIT_TEXT = "本轮工具调用数量已达上限，请基于已有结果回答。"
TOTAL_LIMIT_TEXT = "本次请求工具调用次数已达上限，请基于已有结果回答。"
TRUNCATED_SUFFIX = "\n...（内容已截断）"

Executor = Callable[[str, dict[str, Any]], Awaitable[ToolOutcome]]


@dataclass(frozen=True, slots=True)
class LoopResult:
    reply: str
    llm_calls: int
    tool_calls: int
    fallback_reason: str | None = None


class AgentLoop:
    """最小 Function Calling 循环：最多 N 轮模型调用 + 总预算。"""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        max_loops: int,
        total_budget_ms: int,
        max_tool_calls_per_loop: int = 2,
        tool_result_max_chars: int = 4000,
    ) -> None:
        self._provider = provider
        self._max_loops = max(1, max_loops)
        self._total_budget_ms = max(1, total_budget_ms)
        self._max_tool_calls_per_loop = max(1, max_tool_calls_per_loop)
        self._tool_result_max_chars = max(100, tool_result_max_chars)

    async def run(
        self,
        *,
        messages: list[dict],
        tools: list[dict],
        allowed_tools: set[str],
        executor: Executor,
    ) -> LoopResult:
        started_at = time.perf_counter()
        deadline = started_at + self._total_budget_ms / 1000
        working_messages = list(messages)

        llm_calls = 0
        tool_calls = 0
        last_content = ""
        fallback_reason: str | None = None
        cache: dict[tuple[str, str], str] = {}

        while llm_calls < self._max_loops:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                fallback_reason = "budget_exceeded"
                break

            try:
                response = await asyncio.wait_for(
                    self._provider.chat(
                        messages=working_messages,
                        tools=tools or None,
                        tool_choice="auto" if tools else None,
                    ),
                    timeout=remaining,
                )
            except TimeoutError:
                # 预算耗尽：不向上抛，交给 Runtime 决定是否回退规则链路
                fallback_reason = "budget_exceeded"
                break

            llm_calls += 1
            content = (response.content or "").strip()
            if content:
                last_content = content

            if not response.tool_calls:
                return self._finish(
                    LoopResult(content or FALLBACK_REPLY, llm_calls, tool_calls),
                    started_at,
                )

            working_messages.append(_assistant_tool_call_message(response))

            executed_this_loop = 0
            for call in response.tool_calls:
                if executed_this_loop >= self._max_tool_calls_per_loop:
                    working_messages.append(_tool_message(call.id, LOOP_LIMIT_TEXT))
                    continue
                if tool_calls >= MAX_TOTAL_TOOL_CALLS:
                    working_messages.append(_tool_message(call.id, TOTAL_LIMIT_TEXT))
                    continue
                if call.name not in allowed_tools or call.name not in TOOL_SPECS:
                    working_messages.append(_tool_message(call.id, TOOL_UNAVAILABLE_TEXT))
                    continue

                arguments = _parse_arguments(call.name, call.arguments)
                if arguments is None:
                    working_messages.append(_tool_message(call.id, INVALID_ARGUMENTS_TEXT))
                    continue

                # 同请求内 (name, canonical_args) 只执行一次
                cache_key = (call.name, json.dumps(arguments, sort_keys=True, ensure_ascii=False))
                if cache_key in cache:
                    working_messages.append(_tool_message(call.id, cache[cache_key]))
                    continue

                outcome = await executor(call.name, arguments)
                tool_calls += 1
                executed_this_loop += 1

                result_text = _format_tool_result(call.name, outcome, self._tool_result_max_chars)
                cache[cache_key] = result_text
                working_messages.append(_tool_message(call.id, result_text))

            if tool_calls >= MAX_TOTAL_TOOL_CALLS:
                fallback_reason = "tool_limit_exceeded"
                break

        if fallback_reason is None:
            # 达到最大轮次仍有 tool_calls
            fallback_reason = "max_loops_exceeded"

        return self._finish(
            LoopResult(last_content or FALLBACK_REPLY, llm_calls, tool_calls, fallback_reason),
            started_at,
        )

    def _finish(self, result: LoopResult, started_at: float) -> LoopResult:
        logger.info(
            "[AI-LOOP] finished llm_calls=%d tool_call_count=%d fallback_reason=%s elapsed_ms=%d",
            result.llm_calls,
            result.tool_calls,
            result.fallback_reason,
            int((time.perf_counter() - started_at) * 1000),
        )
        return result


# ============================================================
# 消息与结果组装
# ============================================================


def _assistant_tool_call_message(response: LLMResponse) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": response.content or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in response.tool_calls
        ],
    }


def _tool_message(tool_call_id: str, content: str) -> dict[str, str]:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def _parse_arguments(tool_name: str, raw: str) -> dict[str, Any] | None:
    """LLM 参数结构校验：不合法返回 None（不调用 Tool），不做类型强转。"""
    if not isinstance(raw, str) or len(raw) > MAX_ARGUMENTS_CHARS:
        return None

    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None

    if not isinstance(data, dict):
        return None

    spec = TOOL_SPECS.get(tool_name)
    if spec is None:
        return None

    # 身份字段与未声明字段一律丢弃；值保持原样，不做类型强转
    return {
        key: value
        for key, value in data.items()
        if key in spec.input_fields and key not in IDENTITY_FIELDS
    }


def _format_tool_result(tool_name: str, outcome: ToolOutcome, max_chars: int) -> str:
    if outcome.kind == "success":
        header = f"[TOOL_RESULT name={tool_name} status=success]"
    elif outcome.kind == "business_error":
        header = f"[TOOL_RESULT name={tool_name} status=business_error code={outcome.code}]"
    else:
        header = f"[TOOL_RESULT name={tool_name} status=system_error]"

    body = _sanitize_text(outcome.text)
    return _truncate_by_lines(f"{header}\n{body}", max_chars)


def _sanitize_text(text: str | None) -> str:
    cleaned = (text or "").replace("\r", " ")
    return "".join(ch for ch in cleaned if ch.isprintable() or ch in "\n\t").strip()


def _truncate_by_lines(text: str, limit: int) -> str:
    """按行裁剪，保留前部；超出时末尾追加截断标记。"""
    if len(text) <= limit:
        return text

    budget = max(1, limit - len(TRUNCATED_SUFFIX))
    kept: list[str] = []
    total = 0
    for line in text.split("\n"):
        addition = len(line) + (1 if kept else 0)
        if total + addition > budget:
            break
        kept.append(line)
        total += addition

    if not kept:
        kept = [text[:budget]]

    return "\n".join(kept) + TRUNCATED_SUFFIX
