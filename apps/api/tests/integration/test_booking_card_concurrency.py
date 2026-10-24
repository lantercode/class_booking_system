"""F6.3 T6.3.2：次卡并发预约不得超扣（最后 1 次额度）。"""

import asyncio

import pytest
from httpx import AsyncClient

from app.modules.membership.models import CardStatus, CardType
from tests.membership_support import (
    BASE,
    SEED_STUDENT,
    cleanup,
    count_transactions,
    create_card,
    create_course,
    create_schedule,
    db_factory,
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
async def test_concurrent_bookings_cannot_overspend_credits(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    first_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3),
    )
    second_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4),
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value,
        total_credits=1, validity_days=30,
    )
    try:
        token = await login(client, SEED_STUDENT)
        first, second = await asyncio.gather(
            _book(client, token, first_schedule, card_id),
            _book(client, token, second_schedule, card_id),
        )
        statuses = sorted([first.status_code, second.status_code])
        assert statuses == [201, 400], [first.text, second.text]
        loser = first if first.status_code == 400 else second
        assert "次数已用完" in _detail(loser)

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.used_credits == 1
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
    finally:
        # 预约行由胜出的请求写入，cleanup 会按 schedule_id 一并清理
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            schedule_ids=[first_schedule, second_schedule], course_ids=[course_id],
        )
