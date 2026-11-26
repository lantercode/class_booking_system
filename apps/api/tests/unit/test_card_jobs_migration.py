"""阶段 2 剩余任务迁移测试：2.3 到期提醒 / 2.4 自动解冻 / 2.5 PENDING 作废。"""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.modules.membership.models import CardStatus, CardType
from app.modules.membership.scheduler import (
    auto_cancel_pending_membership_cards,
    auto_unfreeze_membership_cards,
    notify_expiring_membership_cards,
)
from app.modules.membership.service import membership_card_service
from app.modules.task.service import (
    cancel_pending_membership_card,
    notify_card_expiring,
    unfreeze_membership_card,
)
from tests.membership_support import (
    cleanup,
    count_transactions,
    create_card,
    day_end,
    day_start,
    db_factory,
    fetch_card,
    get_seed_ids,
)


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        yield factory, ids


async def _delete_jobs(factory, tenant_id: int) -> None:
    async with factory() as session:
        await session.execute(
            text("DELETE FROM job_queue WHERE tenant_id = :tid"), {"tid": tenant_id}
        )
        await session.commit()


async def _delete_notifications(factory, tenant_id: int) -> None:
    async with factory() as session:
        await session.execute(
            text("DELETE FROM notifications WHERE tenant_id = :tid"), {"tid": tenant_id}
        )
        await session.commit()


async def _job_rows(factory, tenant_id: int, job_type: str) -> list[dict]:
    async with factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT payload FROM job_queue "
                    "WHERE tenant_id = :tid AND type = :t"
                ),
                {"tid": tenant_id, "t": job_type},
            )
        ).mappings().all()
    out = []
    for row in rows:
        payload = row["payload"]
        out.append(json.loads(payload) if isinstance(payload, str) else payload)
    return out


def _worker_settings(*, enabled: bool):
    return SimpleNamespace(TASK_WORKER_ENABLED=enabled)


# ---------------------------------------------------------------------------
# 2.3 到期提醒
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expiry_reminder_enqueues_when_worker_enabled(env):
    factory, ids = env
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.ACTIVE.value,
        validity_days=30, total_credits=10, used_credits=3,
        valid_from=day_start(datetime.now(UTC) - timedelta(days=28)),
        expire_at=datetime.now(UTC) + timedelta(days=2),
        applicable_course_type_code=None,
    )
    try:
        with (
            patch("app.modules.membership.scheduler.SessionLocal", new=factory),
            patch(
                "app.modules.membership.scheduler.get_settings",
                lambda: _worker_settings(enabled=True),
            ),
        ):
            await notify_expiring_membership_cards()

        payloads = await _job_rows(factory, ids["tenant_id"], "notify_card_expiring")
        assert len(payloads) == 1
        assert payloads[0]["user_id"] == ids["student_id"]
        assert payloads[0]["type"] == "card_expiry_reminder"
        assert payloads[0]["idempotency_key"].startswith(f"card_expiring:{card_id}:")

        # 入队模式不直接落通知
        async with factory() as session:
            note_count = (
                await session.execute(
                    text("SELECT count(*) FROM notifications WHERE tenant_id = :tid"),
                    {"tid": ids["tenant_id"]},
                )
            ).scalar_one()
        assert note_count == 0
    finally:
        await _delete_jobs(factory, ids["tenant_id"])
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_expiry_reminder_sends_directly_when_worker_disabled(env):
    factory, ids = env
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.ACTIVE.value,
        validity_days=30, total_credits=10, used_credits=3,
        valid_from=day_start(datetime.now(UTC) - timedelta(days=28)),
        expire_at=datetime.now(UTC) + timedelta(days=2),
        applicable_course_type_code=None,
    )
    try:
        with (
            patch("app.modules.membership.scheduler.SessionLocal", new=factory),
            patch(
                "app.modules.membership.scheduler.get_settings",
                lambda: _worker_settings(enabled=False),
            ),
        ):
            await notify_expiring_membership_cards()

        async with factory() as session:
            keys = (
                await session.execute(
                    text(
                        "SELECT idempotency_key FROM notifications "
                        "WHERE tenant_id = :tid AND type = 'card_expiry_reminder'"
                    ),
                    {"tid": ids["tenant_id"]},
                )
            ).scalars().all()
        assert len(keys) == 1
        assert keys[0].startswith(f"card_expiring:{card_id}:")
        assert await _job_rows(factory, ids["tenant_id"], "notify_card_expiring") == []
    finally:
        await _delete_notifications(factory, ids["tenant_id"])
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_expiry_reminder_handler_is_idempotent(env):
    factory, ids = env
    payload = {
        "user_id": ids["student_id"],
        "type": "card_expiry_reminder",
        "title": "会员卡即将到期",
        "content": "测试内容",
        "idempotency_key": "card_expiring:test:20261201",
    }
    try:
        async with factory() as db:
            await notify_card_expiring(db, payload, tenant_id=ids["tenant_id"])
            await db.commit()
        async with factory() as db:
            await notify_card_expiring(db, payload, tenant_id=ids["tenant_id"])
            await db.commit()

        async with factory() as session:
            count = (
                await session.execute(
                    text("SELECT count(*) FROM notifications WHERE tenant_id = :tid"),
                    {"tid": ids["tenant_id"]},
                )
            ).scalar_one()
        assert count == 1
    finally:
        await _delete_notifications(factory, ids["tenant_id"])


# ---------------------------------------------------------------------------
# 2.4 自动解冻
# ---------------------------------------------------------------------------


async def _make_frozen_card(factory, ids, *, remaining_days: int = 10) -> int:
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.ACTIVE.value,
        validity_days=30,
        valid_from=day_start(datetime.now(UTC) - timedelta(days=20)),
        expire_at=datetime.now(UTC) + timedelta(days=1),
        applicable_course_type_code=None,
    )
    async with factory() as session:
        await session.execute(
            text(
                "UPDATE membership_cards SET status = :st, frozen_at = :fa, "
                "frozen_until = :fu, frozen_reason = '测试冻结', "
                "frozen_remaining_days = :rd WHERE id = :cid"
            ),
            {
                "st": CardStatus.FROZEN.value,
                "fa": datetime.now(UTC) - timedelta(days=3),
                "fu": datetime.now(UTC) - timedelta(hours=1),
                "rd": remaining_days,
                "cid": card_id,
            },
        )
        await session.commit()
    return card_id


@pytest.mark.asyncio
async def test_auto_unfreeze_service_without_conflict(env):
    factory, ids = env
    card_id = await _make_frozen_card(factory, ids)
    try:
        # 不设置租户 ContextVar：模拟 Worker 环境
        async with factory() as db:
            card = await membership_card_service.auto_unfreeze_card(
                db, card_id, ids["tenant_id"]
            )
            await db.commit()

        assert card.status == CardStatus.ACTIVE.value
        assert card.frozen_until is None and card.frozen_at is None
        assert card.frozen_reason is None
        # 有效期按冻结剩余天数顺延
        assert card.expire_at > datetime.now(UTC) + timedelta(days=9)
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_scheduler_unfreeze_enqueues_when_worker_enabled(env):
    factory, ids = env
    card_id = await _make_frozen_card(factory, ids)
    try:
        with (
            patch("app.modules.membership.scheduler.SessionLocal", new=factory),
            patch(
                "app.modules.membership.scheduler.get_settings",
                lambda: _worker_settings(enabled=True),
            ),
        ):
            await auto_unfreeze_membership_cards()

        payloads = await _job_rows(factory, ids["tenant_id"], "unfreeze_membership_card")
        assert len(payloads) == 1
        assert payloads[0]["card_id"] == card_id
        assert (await fetch_card(factory, ids["tenant_id"], card_id)).status == (
            CardStatus.FROZEN.value
        )
    finally:
        await _delete_jobs(factory, ids["tenant_id"])
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_unfreeze_handler_activates_without_context(env):
    factory, ids = env
    card_id = await _make_frozen_card(factory, ids)
    try:
        async with factory() as db:
            await unfreeze_membership_card(
                db, {"card_id": card_id}, tenant_id=ids["tenant_id"]
            )
            await db.commit()
        assert (await fetch_card(factory, ids["tenant_id"], card_id)).status == (
            CardStatus.ACTIVE.value
        )
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


# ---------------------------------------------------------------------------
# 2.5 PENDING 期卡超期作废
# ---------------------------------------------------------------------------


async def _make_stale_pending_card(factory, ids) -> int:
    valid_from = day_start(datetime.now(UTC) + timedelta(days=1))
    return await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=30, valid_from=valid_from,
        expire_at=day_end(valid_from + timedelta(days=29)),
        applicable_course_type_code=None,
        created_at=datetime.now(UTC) - timedelta(days=40),
    )


@pytest.mark.asyncio
async def test_cancel_pending_enqueues_when_worker_enabled(env):
    factory, ids = env
    card_id = await _make_stale_pending_card(factory, ids)
    try:
        with (
            patch("app.modules.membership.scheduler.SessionLocal", new=factory),
            patch(
                "app.modules.membership.scheduler.settings",
                SimpleNamespace(
                    PENDING_CARD_CANCEL_ENABLED=True, PENDING_CARD_CANCEL_DAYS=30
                ),
            ),
            patch(
                "app.modules.membership.scheduler.get_settings",
                lambda: _worker_settings(enabled=True),
            ),
        ):
            await auto_cancel_pending_membership_cards()

        payloads = await _job_rows(
            factory, ids["tenant_id"], "cancel_pending_membership_card"
        )
        assert len(payloads) == 1
        assert payloads[0] == {"card_id": card_id, "days": 30}
        assert (await fetch_card(factory, ids["tenant_id"], card_id)).status == (
            CardStatus.PENDING.value
        )
    finally:
        await _delete_jobs(factory, ids["tenant_id"])
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_cancel_pending_handler_without_context(env):
    factory, ids = env
    card_id = await _make_stale_pending_card(factory, ids)
    try:
        async with factory() as db:
            await cancel_pending_membership_card(
                db, {"card_id": card_id, "days": 30}, tenant_id=ids["tenant_id"]
            )
            await db.commit()

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.CANCELLED.value
        assert card.cancelled_reason and "超期未激活" in card.cancelled_reason
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1

        # 幂等：二次执行不重复写流水
        async with factory() as db:
            await cancel_pending_membership_card(
                db, {"card_id": card_id, "days": 30}, tenant_id=ids["tenant_id"]
            )
            await db.commit()
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])
