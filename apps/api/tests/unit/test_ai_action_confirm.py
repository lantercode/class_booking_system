"""P1-5 写操作确认令牌单测（不联网 / 不连 DB / 不连 Redis）。"""

import pytest

from app.ai.agent.action_token import (
    ActionTokenError,
    issue_action_token,
    verify_action_token,
)


def _issue(**overrides):
    params = dict(
        action="create_booking",
        payload={"schedule_id": 1},
        user_id=10,
        tenant_id=2,
    )
    params.update(overrides)
    return issue_action_token(**params)


def test_token_roundtrip_returns_payload():
    data = verify_action_token(_issue(), user_id=10, tenant_id=2)

    assert data["action"] == "create_booking"
    assert data["payload"] == {"schedule_id": 1}


def test_tampered_token_is_rejected():
    token = _issue()
    body, signature = token.split(".", 1)

    with pytest.raises(ActionTokenError):
        verify_action_token(f"{body}x.{signature}", user_id=10, tenant_id=2)


def test_identity_mismatch_is_rejected():
    token = _issue()

    with pytest.raises(ActionTokenError):
        verify_action_token(token, user_id=11, tenant_id=2)
    with pytest.raises(ActionTokenError):
        verify_action_token(token, user_id=10, tenant_id=3)


def test_expired_token_is_rejected():
    token = _issue(ttl_seconds=-1)

    with pytest.raises(ActionTokenError):
        verify_action_token(token, user_id=10, tenant_id=2)


def test_malformed_token_is_rejected():
    with pytest.raises(ActionTokenError):
        verify_action_token("not-a-token", user_id=10, tenant_id=2)
