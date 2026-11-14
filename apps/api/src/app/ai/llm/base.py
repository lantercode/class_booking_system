"""LLM Provider 协议与统一 DTO / 异常族。

边界：
  - 本模块只定义协议与数据类型，不含任何网络调用；
  - 异常 message 只能是固定中文文案，禁止拼接上游响应原文、Key、URL；
  - ``ToolCall.arguments`` 保留模型返回的 JSON 字符串原文，解析与校验由上层负责。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# ============================================================
# 统一 DTO
# ============================================================


@dataclass(frozen=True, slots=True)
class ToolCall:
    """模型请求的工具调用：参数保持 JSON 字符串原文，不做解析。"""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """模型单轮响应（一次性 JSON，非流式）。"""

    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None


# ============================================================
# 统一异常族（message 固定中文文案，不携带上游细节）
# ============================================================


class LLMError(Exception):
    """LLM 调用错误基类：对外只暴露可读文案，可选携带状态码。"""

    def __init__(self, message: str = "模型服务暂时不可用", *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class LLMTimeoutError(LLMError):
    def __init__(self, *, code: int | None = None) -> None:
        super().__init__("模型服务响应超时", code=code)


class LLMAuthError(LLMError):
    def __init__(self, *, code: int | None = None) -> None:
        super().__init__("模型服务认证失败", code=code)


class LLMRateLimitError(LLMError):
    def __init__(self, *, code: int | None = None) -> None:
        super().__init__("模型服务请求过于频繁", code=code)


class LLMBadRequestError(LLMError):
    def __init__(self, *, code: int | None = None) -> None:
        super().__init__("模型服务请求参数无效", code=code)


class LLMServerError(LLMError):
    def __init__(self, *, code: int | None = None) -> None:
        super().__init__("模型服务暂时不可用", code=code)


class LLMResponseError(LLMError):
    def __init__(self, *, code: int | None = None) -> None:
        super().__init__("模型服务返回内容无法解析", code=code)


# ============================================================
# Provider 协议
# ============================================================


@runtime_checkable
class LLMProvider(Protocol):
    """Provider 协议：Runtime / Loop 只依赖本协议，不依赖具体实现。"""

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        """发起一次非流式对话请求。"""
        ...

    async def aclose(self) -> None:
        """释放底层 HTTP 连接资源。"""
        ...
