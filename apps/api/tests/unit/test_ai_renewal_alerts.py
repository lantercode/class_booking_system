"""P1-4 会员续费预警单测（不联网 / 不连 DB / 不连 Redis）。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.ai.agent import renewal
from app.ai.agent.renewal import build_renewal_template, compose_renewal_content
from app.ai.mcp_server import TOOL_SPECS
from app.modules.membership.service import MembershipCardService
from app.modules.notification.service import NotificationService


def _item(**overrides):
    base = {
        "card_id": 1,
        "student_id": 10,
        "student_name": "张三",
        "product_name": "月卡",
        "expire_at": datetime.now(UTC) + timedelta(days=3),
        "remaining_credits": 2,
        "days_left": 3,
    }
    base.update(overrides)
    return base


def test_template_for_expiring_card():
    text = build_renewal_template(_item())

    assert "3 天后到期" in text
    assert "剩余 2 课时" in text


def test_template_for_low_credits_without_expire():
    text = build_renewal_template(_item(expire_at=None, days_left=None, remaining_credits=1))

    assert "剩余课时不足" in text
    assert "剩余 1 课时" in text


@pytest.mark.asyncio
async def test_compose_falls_back_to_template_when_llm_disabled(monkeypatch):
    monkeypatch.setattr(
        renewal, "get_settings", lambda: SimpleNamespace(AI_LLM_ENABLED=False)
    )

    text = await compose_renewal_content(_item())

    assert text == build_renewal_template(_item())


@pytest.mark.asyncio
async def test_compose_falls_back_when_provider_raises(monkeypatch):
    class _BrokenProvider:
        async def chat(self, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(
        renewal,
        "get_settings",
        lambda: SimpleNamespace(AI_LLM_ENABLED=True, AI_LLM_TIMEOUT_MS=1000),
    )
    monkeypatch.setattr(renewal, "get_llm_provider", lambda: _BrokenProvider())

    text = await compose_renewal_content(_item())

    assert text == build_renewal_template(_item())


@pytest.mark.asyncio
async def test_notification_create_is_idempotent():
    class _FakeRepo:
        def __init__(self):
            self.keys: set[str] = set()

        async def create_if_absent(self, db, **kwargs):
            key = kwargs["idempotency_key"]
            if key in self.keys:
                return None
            self.keys.add(key)
            return 1

    service = NotificationService()
    service.repo = _FakeRepo()
    payload = dict(
        tenant_id=1,
        user_id=10,
        type="renewal_alert",
        title="提醒",
        content="内容",
        idempotency_key="renewal:1:20261126",
    )

    assert await service.create_idempotent(None, **payload) == 1
    assert await service.create_idempotent(None, **payload) is None


@pytest.mark.asyncio
async def test_service_computes_days_left():
    expire_at = datetime.now(UTC) + timedelta(days=3, hours=1)

    class _FakeCardRepo:
        async def list_renewal_alerts(self, db, **kwargs):
            return [
                {
                    "card_id": 1,
                    "student_id": 10,
                    "student_name": "张三",
                    "product_name": "月卡",
                    "expire_at": expire_at,
                    "total_credits": 10,
                    "used_credits": 9,
                    "remaining_credits": 1,
                }
            ]

    service = MembershipCardService()
    service.card_repo = _FakeCardRepo()

    items = await service.list_renewal_alerts(None, tenant_id=1, days=7)

    assert items[0]["days_left"] == 3


def test_expiring_cards_tool_is_readonly_and_admin_only():
    spec = TOOL_SPECS["query_expiring_cards"]

    assert spec.is_write is False
    assert "student" not in spec.required_roles
    assert {"admin", "super_admin", "teacher"} <= spec.required_roles
