"""F6.3 T6.3.2/T6.3.5：次卡扣次基准、余额不足回滚、取消回补幂等。"""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.modules.membership.models import CardStatus, CardType
from tests.membership_support import (
    BASE,
    SEED_STUDENT,
    cleanup,
    count_bookings_for_schedule,
    count_transactions,
    create_card,
    create_course,
    create_schedule,
    day_end,
    day_start,
    db_factory,
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


def _detail(resp) -> str:
    body = resp.json()
    return body.get("msg") or body.get("detail") or ""


async def _book(client: AsyncClient, token: str, schedule_id: int, card_id: int):
    return await client.post(
        f"{BASE}/bookings/",
        json={"schedule_id": schedule_id, "membership_card_id": card_id},
        headers=auth_headers(token),
    )


@pytest.mark.asyncio
async def test_count_card_validity_uses_schedule_date(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value,
        total_credits=2,
        valid_from=day_start(start_at - timedelta(days=1)),
        expire_at=day_end(start_at),
    )
    booking_id = None
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _book(client, token, schedule_id, card_id)
        assert resp.status_code == 201, resp.text
        booking_id = resp.json()["data"]["id"]

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.used_credits == 1
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            booking_ids=[booking_id] if booking_id else None,
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_count_card_expired_by_schedule_date_rejected(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value,
        total_credits=2,
        valid_from=day_start(start_at - timedelta(days=5)),
        expire_at=day_end(start_at - timedelta(days=1)),
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _book(client, token, schedule_id, card_id)
        assert resp.status_code == 400, resp.text
        assert "已过期" in _detail(resp)
        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.used_credits == 0
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_insufficient_credits_rolls_back_booking_and_capacity(
    client: AsyncClient, env
):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value,
        total_credits=1, used_credits=1, validity_days=30,
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _book(client, token, schedule_id, card_id)
        assert resp.status_code == 400, resp.text
        assert "次数已用完" in _detail(resp)

        # 扣次发生在预约行与 capacity 自增之后：失败必须整体回滚
        schedule = await fetch_schedule(factory, ids["tenant_id"], schedule_id)
        assert schedule.booked_count == 0
        assert await count_bookings_for_schedule(
            factory, ids["tenant_id"], schedule_id
        ) == 0
        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.used_credits == 1
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 0
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_cancel_restores_credits_once(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value,
        total_credits=2, validity_days=30,
    )
    booking_id = None
    try:
        token = await login(client, SEED_STUDENT)
        booked = await _book(client, token, schedule_id, card_id)
        assert booked.status_code == 201, booked.text
        booking_id = booked.json()["data"]["id"]
        assert (await fetch_card(factory, ids["tenant_id"], card_id)).used_credits == 1

        cancelled = await client.post(
            f"{BASE}/bookings/{booking_id}/cancel?reason=测试取消",
            headers=auth_headers(token),
        )
        assert cancelled.status_code == 200, cancelled.text
        assert (await fetch_card(factory, ids["tenant_id"], card_id)).used_credits == 0

        # 重复取消不会再次回补
        again = await client.post(
            f"{BASE}/bookings/{booking_id}/cancel?reason=重复取消",
            headers=auth_headers(token),
        )
        assert again.status_code == 400, again.text
        assert (await fetch_card(factory, ids["tenant_id"], card_id)).used_credits == 0
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 2
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            booking_ids=[booking_id] if booking_id else None,
            schedule_ids=[schedule_id], course_ids=[course_id],
        )
