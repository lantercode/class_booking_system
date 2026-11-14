"""AI LLM 配置校验单测（不依赖网络 / DB / Redis）。"""

import pytest

from app.core.config import Settings


def test_llm_disabled_by_default():
    """默认关闭：不需要 Key，也不影响启动。"""
    settings = Settings()

    assert settings.AI_LLM_ENABLED is False
    assert settings.ARK_API_KEY == ""
    assert settings.AI_LLM_READONLY_ONLY is True
    assert "ARK_API_KEY" not in repr(settings)


def test_enabled_without_api_key_fails():
    with pytest.raises(ValueError):
        Settings(AI_LLM_ENABLED=True, ARK_API_KEY="")


def test_enabled_with_unknown_model_fails():
    with pytest.raises(ValueError):
        Settings(
            AI_LLM_ENABLED=True,
            ARK_API_KEY="test-key",
            AI_LLM_MODEL="not-in-whitelist",
        )


def test_timeout_must_be_less_than_total_budget():
    with pytest.raises(ValueError):
        Settings(
            AI_LLM_ENABLED=True,
            ARK_API_KEY="test-key",
            AI_LLM_TIMEOUT_MS=15000,
            AI_LLM_TOTAL_BUDGET_MS=15000,
        )


def test_enabled_with_valid_config_passes():
    settings = Settings(
        AI_LLM_ENABLED=True,
        ARK_API_KEY="test-key",
        AI_LLM_MODEL="doubao-seed-2-1-lite-260915",
        AI_LLM_TIMEOUT_MS=6000,
        AI_LLM_TOTAL_BUDGET_MS=15000,
    )

    assert settings.AI_LLM_ENABLED is True
    assert "test-key" not in repr(settings)


def test_allowed_model_list_strips_whitespace():
    settings = Settings(
        AI_LLM_ALLOWED_MODELS=" model-a , model-b ,, model-c ",
    )

    assert settings.ai_llm_allowed_model_list == ["model-a", "model-b", "model-c"]
