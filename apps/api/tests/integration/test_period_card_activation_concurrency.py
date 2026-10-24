"""F6.3 T6.3.3/T6.3.4：期卡激活幂等/并发，以及排期收口（COMPLETED / NO_SHOW）。"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import BookingStatus
from app.modules.booking.service import BookingService
from app.modules.membership.models import CardStatus, CardType
from tests.membership_support import (
    BASE,
    SUPER_ADMIN,
    cleanup,
    count_transactions,
    create_booking,
    create_card,
    create_course,
    create_schedule,
    db_factory,
    fetch_booking,
    fetch_card,
    fetch_schedule,
    future_start,
    get_seed_ids,
    login,
)
from tests.membership_support import (
    headers as auth_headers,
)


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        yield factory, ids


async def _complete(client: AsyncClient, token: str, booking_id: int):
    return await client.post(
        f"{BASE}/bookings/{booking_id}/complete", headers=auth_headers(token)
    )


@pytest.mark.asyncio
async def test_concurrent_complete_activates_period_card_once(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    first_start = future_start(3)
    second_start = future_start(4)
    first_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=first_start,
    )
    second_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=second_start,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=7,
    )
    first_booking = await create_booking(
        factory, ids["tenant_id"], schedule_id=first_schedule,
        student_id=ids["student_id"], membership_card_id=card_id,
    )
    second_booking = await create_booking(
        factory, ids["tenant_id"], schedule_id=second_schedule,
        student_id=ids["student_id"], membership_card_id=card_id,
    )
    try:
        token = await login(client, SUPER_ADMIN)
        responses = await asyncio.gather(
            _complete(client, token, first_booking),
            _complete(client, token, second_booking),
        )
        assert [r.status_code for r in responses] == [200, 200], [
            r.text for r in responses
        ]

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.ACTIVE.value
        # 以最早完成的排期日作为生效日，且只写一条激活流水
        assert card.valid_from.date() == first_start.date()
        assert (card.expire_at.date() - card.valid_from.date()).days == 6
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            booking_ids=[first_booking, second_booking],
            schedule_ids=[first_schedule, second_schedule], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_finalize_checked_in_completes_and_activates(env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = datetime.now(UTC) - timedelta(hours=2)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=7,
    )
    booking_id = await create_booking(
        factory, ids["tenant_id"], schedule_id=schedule_id,
        student_id=ids["student_id"], membership_card_id=card_id,
        status=BookingStatus.CHECKED_IN.value,
    )
    try:
        service = BookingService()
        async with factory() as db:
            set_tenant_id(ids["tenant_id"])
            result = await service.finalize_schedule_bookings(db, schedule_id)

        assert result["completed_count"] == 1
        assert result["no_show_count"] == 0
        assert result["activated_count"] == 1

        booking = await fetch_booking(factory, ids["tenant_id"], booking_id)
        assert booking.status == BookingStatus.COMPLETED.value
        schedule = await fetch_schedule(factory, ids["tenant_id"], schedule_id)
        assert schedule.status == 3  # ScheduleStatus.FINISHED

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.ACTIVE.value
        assert card.valid_from.date() == start_at.date()
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1

        # 重复收口：排期已 FINISHED → 幂等跳过，不产生额外流水
        async with factory() as db:
            set_tenant_id(ids["tenant_id"])
            again = await service.finalize_schedule_bookings(db, schedule_id)
        assert again["skipped"] is True
        assert again["completed_count"] == 0
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_finalize_no_show_also_activates(env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = datetime.now(UTC) - timedelta(hours=1)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=3,
    )
    booking_id = await create_booking(
        factory, ids["tenant_id"], schedule_id=schedule_id,
        student_id=ids["student_id"], membership_card_id=card_id,
        status=BookingStatus.BOOKED.value,
    )
    try:
        async with factory() as db:
            set_tenant_id(ids["tenant_id"])
            result = await BookingService().finalize_schedule_bookings(db, schedule_id)

        assert result["no_show_count"] == 1
        assert result["activated_count"] == 1
        booking = await fetch_booking(factory, ids["tenant_id"], booking_id)
        assert booking.status == BookingStatus.NO_SHOW.value

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.ACTIVE.value
        assert card.valid_from.date() == start_at.date()
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )
