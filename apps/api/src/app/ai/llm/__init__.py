"""LLM Provider 适配层。

只导出协议、DTO、异常族与工厂；不暴露密钥与具体 HTTP 实现细节。
"""

from app.ai.llm.base import (
    LLMAuthError,
    LLMBadRequestError,
    LLMError,
    LLMProvider,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseError,
    LLMServerError,
    LLMTimeoutError,
    ToolCall,
)
from app.ai.llm.factory import (
    close_llm_provider,
    get_llm_provider,
    is_llm_enabled,
    is_llm_enabled_for_tenant,
)

__all__ = [
    "LLMError",
    "LLMTimeoutError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMBadRequestError",
    "LLMServerError",
    "LLMResponseError",
    "LLMProvider",
    "LLMResponse",
    "ToolCall",
    "get_llm_provider",
    "close_llm_provider",
    "is_llm_enabled",
    "is_llm_enabled_for_tenant",
]
