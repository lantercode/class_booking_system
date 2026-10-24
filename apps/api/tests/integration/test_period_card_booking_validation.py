"""F6.3 T6.3.2：期卡预约校验（D9 可约、预期窗口、冲突、归属、租户、有效期边界）。"""

from datetime import timedelta

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
    day_end,
    day_start,
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


async def _book(client: AsyncClient, token: str, schedule_id: int, card_id: int):
    return await client.post(
        f"{BASE}/bookings/",
        json={"schedule_id": schedule_id, "membership_card_id": card_id},
        headers=auth_headers(token),
    )


def _detail(resp) -> str:
    body = resp.json()
    return body.get("msg") or body.get("detail") or ""


@pytest.mark.asyncio
async def test_pending_period_card_can_book_without_deduct(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=7,
    )
    booking_id = None
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _book(client, token, schedule_id, card_id)
        assert resp.status_code == 201, resp.text
        booking_id = resp.json()["data"]["id"]

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.PENDING.value
        assert card.valid_from is None
        # 期卡预约不预扣次数、不写 CONSUME 流水
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 0
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            booking_ids=[booking_id] if booking_id else None,
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_period_card_out_of_expected_window_rejected(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    first_start = future_start(3)
    late_start = future_start(12)
    first_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=first_start,
    )
    late_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=late_start,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=7,
    )
    booking_id = None
    try:
        token = await login(client, SEED_STUDENT)
        first = await _book(client, token, first_schedule, card_id)
        assert first.status_code == 201, first.text
        booking_id = first.json()["data"]["id"]

        # 锚点 = 最早预约日（第 3 天）→ 窗口第 3~9 天，第 12 天超出
        late = await _book(client, token, late_schedule, card_id)
        assert late.status_code == 400, late.text
        assert "超出此期卡的有效期窗口" in _detail(late)

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.PENDING.value
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            booking_ids=[booking_id] if booking_id else None,
            schedule_ids=[first_schedule, late_schedule], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_pending_period_card_overlap_conflict_409(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(
        factory, ids["tenant_id"], course_type_code="regular"
    )
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    existing_card = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.ACTIVE.value,
        valid_from=day_start(future_start(0)),
        expire_at=day_end(future_start(10)),
        applicable_course_type_code="regular",
    )
    pending_card = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=7, applicable_course_type_code="regular",
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _book(client, token, schedule_id, pending_card)
        assert resp.status_code == 409, resp.text
        assert "重叠" in _detail(resp)

        card = await fetch_card(factory, ids["tenant_id"], pending_card)
        assert card.status == CardStatus.PENDING.value
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[existing_card, pending_card],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_other_student_card_forbidden(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    # 卡属于教师账号（同租户的其他用户）
    card_id = await create_card(
        factory, ids["tenant_id"], ids["teacher_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value,
        validity_days=30, total_credits=5,
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _book(client, token, schedule_id, card_id)
        assert resp.status_code == 403, resp.text
        assert "无权使用此会员卡" in _detail(resp)
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_unknown_card_404(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _book(client, token, schedule_id, 999_999_999)
        assert resp.status_code == 404, resp.text
        assert "会员卡不存在" in _detail(resp)
    finally:
        await cleanup(
            factory, ids["tenant_id"], schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_course_type_mismatch_rejected(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"], course_type_code=None)
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.ACTIVE.value,
        valid_from=day_start(future_start(0)),
        expire_at=day_end(future_start(10)),
        applicable_course_type_code="private",
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _book(client, token, schedule_id, card_id)
        assert resp.status_code == 400, resp.text
        assert "不适用于此课程类型" in _detail(resp)
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_expire_at_same_day_allowed(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.ACTIVE.value,
        valid_from=day_start(start_at - timedelta(days=2)),
        expire_at=day_end(start_at),
    )
    booking_id = None
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _book(client, token, schedule_id, card_id)
        assert resp.status_code == 201, resp.text
        booking_id = resp.json()["data"]["id"]
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            booking_ids=[booking_id] if booking_id else None,
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_expired_card_rejected(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.ACTIVE.value,
        valid_from=day_start(start_at - timedelta(days=5)),
        expire_at=day_end(start_at - timedelta(days=1)),
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _book(client, token, schedule_id, card_id)
        assert resp.status_code == 400, resp.text
        assert "已过期" in _detail(resp)
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )
