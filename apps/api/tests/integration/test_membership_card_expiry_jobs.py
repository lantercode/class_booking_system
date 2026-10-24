"""F6.3 T6.3.6：过期扫描与 PENDING 期卡 90 天作废任务。"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.modules.booking.models import BookingStatus
from app.modules.membership.models import CardStatus, CardType
from app.modules.membership.scheduler import (
    auto_cancel_pending_membership_cards,
    auto_expire_membership_cards,
)
from tests.membership_support import (
    cleanup,
    count_transactions,
    create_booking,
    create_card,
    create_course,
    create_schedule,
    db_factory,
    fetch_card,
    future_start,
    get_seed_ids,
)


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        yield factory, ids


@pytest.mark.asyncio
async def test_expire_job_marks_active_and_pending_expired(env):
    factory, ids = env
    now = datetime.now(UTC)
    count_card = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value,
        total_credits=5, used_credits=1, validity_days=30,
        valid_from=now - timedelta(days=30), expire_at=now - timedelta(hours=1),
    )
    pending_card = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=30, valid_from=now - timedelta(days=30),
        expire_at=now - timedelta(hours=1),
    )
    try:
        with patch(
            "app.modules.membership.scheduler.SessionLocal", new=factory
        ):
            await auto_expire_membership_cards()
            # 再跑一次：状态重检必须幂等，不重复写流水
            await auto_expire_membership_cards()

        count_after = await fetch_card(factory, ids["tenant_id"], count_card)
        assert count_after.status == CardStatus.EXPIRED.value
        assert count_after.used_credits == 5
        assert await count_transactions(factory, ids["tenant_id"], count_card) == 1

        pending_after = await fetch_card(factory, ids["tenant_id"], pending_card)
        assert pending_after.status == CardStatus.EXPIRED.value
        assert await count_transactions(
            factory, ids["tenant_id"], pending_card
        ) == 1
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[count_card, pending_card]
        )


@pytest.mark.asyncio
async def test_cancel_job_cancels_old_unused_pending_card(env):
    factory, ids = env
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=7, created_at=datetime.now(UTC) - timedelta(days=100),
    )
    try:
        with patch(
            "app.modules.membership.scheduler.SessionLocal", new=factory
        ):
            await auto_cancel_pending_membership_cards()

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.CANCELLED.value
        assert "超期未激活" in (card.cancelled_reason or "")
        assert card.cancelled_at is not None
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_cancel_job_skips_used_pending_card(env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3),
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=7, created_at=datetime.now(UTC) - timedelta(days=100),
    )
    booking_id = await create_booking(
        factory, ids["tenant_id"], schedule_id=schedule_id,
        student_id=ids["student_id"], membership_card_id=card_id,
        status=BookingStatus.COMPLETED.value,
    )
    try:
        with patch(
            "app.modules.membership.scheduler.SessionLocal", new=factory
        ):
            await auto_cancel_pending_membership_cards()

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.PENDING.value
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 0
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_cancel_job_skips_recent_pending_card(env):
    factory, ids = env
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=7,
    )
    try:
        with patch(
            "app.modules.membership.scheduler.SessionLocal", new=factory
        ):
            await auto_cancel_pending_membership_cards()

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.PENDING.value
        assert card.cancelled_at is None
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])
