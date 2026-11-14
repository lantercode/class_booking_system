"""LLM Provider 工厂：进程内单例 + 生命周期关闭。

约定：
  - 未启用（``AI_LLM_ENABLED=false``）时**不在启动阶段构造 Provider**，
    线上行为与纯规则链路完全一致；
  - 调用方需要判断开关时使用 ``is_llm_enabled()``，不要直接读 Settings。
"""

from __future__ import annotations

import logging

from app.ai.llm.ark import ArkProvider
from app.ai.llm.base import LLMProvider
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_provider: LLMProvider | None = None


def is_llm_enabled() -> bool:
    """返回 LLM 总开关状态（默认 False）。"""
    return get_settings().AI_LLM_ENABLED


def is_llm_enabled_for_tenant(tenant_id: int | None) -> bool:
    """返回指定租户是否启用 LLM。

    规则（与方案一致）：
      - 总开关关闭 → False；
      - 租户白名单为空 → False（空表示不启用）；
      - tenant_id 为空 → False；
      - 否则仅当 ``str(tenant_id)`` 在去空格后的白名单中才为 True。
    """
    settings = get_settings()
    if not settings.AI_LLM_ENABLED:
        return False
    if tenant_id is None:
        return False

    allowed = [t.strip() for t in settings.AI_LLM_ENABLED_TENANTS.split(",") if t.strip()]
    if not allowed:
        return False
    return str(tenant_id) in allowed


def get_llm_provider() -> LLMProvider:
    """返回模块级单例 Provider（首次调用时按配置构造）。"""
    global _provider
    if _provider is None:
        settings = get_settings()
        _provider = ArkProvider(
            api_key=settings.ARK_API_KEY,
            base_url=settings.AI_LLM_BASE_URL,
            model=settings.AI_LLM_MODEL,
            timeout_ms=settings.AI_LLM_TIMEOUT_MS,
            max_retries=settings.AI_LLM_MAX_RETRIES,
            max_tokens=settings.AI_LLM_MAX_TOKENS,
        )
    return _provider


async def close_llm_provider() -> None:
    """关闭并清空单例（供 lifespan / 测试使用）。"""
    global _provider
    if _provider is None:
        return
    try:
        await _provider.aclose()
    finally:
        _provider = None
