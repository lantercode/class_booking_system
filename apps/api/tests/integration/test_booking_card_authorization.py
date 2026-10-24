"""F6.3 T6.3.7：会员卡相关接口的认证 / 授权边界。"""

import pytest
from httpx import AsyncClient

from app.modules.booking.models import BookingStatus
from app.modules.membership.models import CardStatus, CardType
from tests.membership_support import (
    BASE,
    SEED_STUDENT,
    SEED_TEACHER,
    TENANT_HEADERS,
    cleanup,
    create_booking,
    create_card,
    create_course,
    create_schedule,
    db_factory,
    fetch_booking,
    fetch_card,
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


@pytest.mark.asyncio
async def test_teacher_cannot_create_booking(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3),
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=7,
    )
    try:
        token = await login(client, SEED_TEACHER)
        resp = await client.post(
            f"{BASE}/bookings/",
            json={"schedule_id": schedule_id, "membership_card_id": card_id},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403, resp.text
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_unauthenticated_booking_rejected(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3),
    )
    try:
        resp = await client.post(
            f"{BASE}/bookings/",
            json={"schedule_id": schedule_id},
            headers=TENANT_HEADERS,
        )
        assert resp.status_code == 401, resp.text
    finally:
        await cleanup(
            factory, ids["tenant_id"], schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_student_cannot_complete_booking(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3),
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
        token = await login(client, SEED_STUDENT)
        resp = await client.post(
            f"{BASE}/bookings/{booking_id}/complete", headers=auth_headers(token)
        )
        assert resp.status_code == 403, resp.text

        booking = await fetch_booking(factory, ids["tenant_id"], booking_id)
        assert booking.status == BookingStatus.CHECKED_IN.value
        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.PENDING.value
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_student_cannot_freeze_card(client: AsyncClient, env):
    factory, ids = env
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.ACTIVE.value,
        validity_days=7,
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await client.post(
            f"{BASE}/membership/cards/{card_id}/freeze",
            json={"reason": "越权测试", "freeze_days": 7},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403, resp.text
        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.ACTIVE.value
        assert card.frozen_until is None
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])
