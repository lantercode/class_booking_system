"""F6.3 T6.3.1/T6.3.3/T6.3.5：期卡发卡、冻结、取消、手动完成激活。

覆盖计划中的：
- test_issue_period_card_pending_without_validity
- test_issue_period_card_requires_validity_days
- test_issue_count_card_unchanged
- test_issue_card_forbidden_for_non_admin
- test_freeze_pending_rejected
- 手动完成激活 / 重复完成 400 / 期卡取消不回补 / 次卡取消回补
"""

import pytest
from httpx import AsyncClient

from app.modules.booking.models import BookingStatus
from app.modules.membership.models import CardStatus, CardType
from tests.membership_support import (
    BASE,
    SEED_STUDENT,
    SUPER_ADMIN,
    cleanup,
    count_transactions,
    create_booking,
    create_card,
    create_course,
    create_product,
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


async def _issue_card(client: AsyncClient, token: str, payload: dict):
    return await client.post(
        f"{BASE}/membership/cards", json=payload, headers=auth_headers(token)
    )


@pytest.mark.asyncio
async def test_issue_period_card_pending_without_validity(client: AsyncClient, env):
    factory, ids = env
    product_id = await create_product(
        factory, ids["tenant_id"], card_type=CardType.PERIOD.value, validity_days=30
    )
    card_id = None
    try:
        token = await login(client, SUPER_ADMIN)
        resp = await _issue_card(
            client,
            token,
            {
                "student_id": ids["student_id"],
                "product_id": product_id,
                "valid_from": "2026-10-30",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["code"] == 0
        card_id = body["data"]["id"]

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.PENDING.value
        assert card.valid_from is None
        assert card.expire_at is None
        assert card.validity_days == 30
        assert card.card_type == CardType.PERIOD.value
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id] if card_id else None,
                      product_ids=[product_id])


@pytest.mark.asyncio
async def test_issue_period_card_requires_validity_days(client: AsyncClient, env):
    factory, ids = env
    product_id = await create_product(
        factory, ids["tenant_id"], card_type=CardType.PERIOD.value, validity_days=None
    )
    try:
        token = await login(client, SUPER_ADMIN)
        resp = await _issue_card(
            client,
            token,
            {"student_id": ids["student_id"], "product_id": product_id},
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        # Service 抛 HTTPException 时走 FastAPI 默认处理器，信封键为 detail
        assert "有效天数" in (body.get("msg") or body.get("detail") or "")
    finally:
        await cleanup(factory, ids["tenant_id"], product_ids=[product_id])


@pytest.mark.asyncio
async def test_issue_count_card_unchanged(client: AsyncClient, env):
    factory, ids = env
    product_id = await create_product(
        factory,
        ids["tenant_id"],
        card_type=CardType.COUNT.value,
        validity_days=30,
        total_credits=10,
    )
    card_id = None
    try:
        token = await login(client, SUPER_ADMIN)
        resp = await _issue_card(
            client,
            token,
            {"student_id": ids["student_id"], "product_id": product_id},
        )
        assert resp.status_code == 201, resp.text
        card_id = resp.json()["data"]["id"]

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.card_type == CardType.COUNT.value
        assert card.status == CardStatus.ACTIVE.value
        assert card.valid_from is not None
        assert card.expire_at is not None
        assert card.validity_days is None
        assert card.total_credits == 10
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id] if card_id else None,
                      product_ids=[product_id])


@pytest.mark.asyncio
async def test_issue_card_forbidden_for_non_admin(client: AsyncClient, env):
    factory, ids = env
    product_id = await create_product(
        factory, ids["tenant_id"], card_type=CardType.PERIOD.value, validity_days=30
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _issue_card(
            client,
            token,
            {"student_id": ids["student_id"], "product_id": product_id},
        )
        assert resp.status_code == 403, resp.text
    finally:
        await cleanup(factory, ids["tenant_id"], product_ids=[product_id])


@pytest.mark.asyncio
async def test_freeze_pending_rejected(client: AsyncClient, env):
    factory, ids = env
    card_id = await create_card(
        factory,
        ids["tenant_id"],
        ids["student_id"],
        card_type=CardType.PERIOD.value,
        status=CardStatus.PENDING.value,
        validity_days=30,
    )
    try:
        token = await login(client, SUPER_ADMIN)
        resp = await client.post(
            f"{BASE}/membership/cards/{card_id}/freeze",
            json={"reason": "测试冻结", "freeze_days": 7},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert "未激活卡不可冻结" in (body.get("msg") or body.get("detail") or "")

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.PENDING.value
        assert card.frozen_until is None
        assert card.expire_at is None
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_manual_complete_activates_period_card_once(client: AsyncClient, env):
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
    booking_id = await create_booking(
        factory, ids["tenant_id"], schedule_id=schedule_id, student_id=ids["student_id"],
        membership_card_id=card_id,
    )
    try:
        token = await login(client, SUPER_ADMIN)
        resp = await client.post(
            f"{BASE}/bookings/{booking_id}/complete", headers=auth_headers(token)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == BookingStatus.COMPLETED.value

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.ACTIVE.value
        assert card.valid_from is not None
        assert card.valid_from.date() == start_at.date()
        assert card.expire_at is not None
        # 7 天窗口：valid_from 当天算第 1 天
        assert (card.expire_at.date() - card.valid_from.date()).days == 6

        repeats = await count_transactions(factory, ids["tenant_id"], card_id)
        assert repeats == 1

        # 重复完成保持既有 400 语义（C-19）
        again = await client.post(
            f"{BASE}/bookings/{booking_id}/complete", headers=auth_headers(token)
        )
        assert again.status_code == 400
        assert "无法完成" in again.json()["msg"]
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_period_card_cancel_no_restore(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    product_id = await create_product(
        factory, ids["tenant_id"], card_type=CardType.PERIOD.value, validity_days=30
    )
    card_id = None
    booking_id = None
    try:
        admin_token = await login(client, SUPER_ADMIN)
        issued = await _issue_card(
            client, admin_token,
            {"student_id": ids["student_id"], "product_id": product_id},
        )
        assert issued.status_code == 201, issued.text
        card_id = issued.json()["data"]["id"]

        student_token = await login(client, SEED_STUDENT)
        booked = await client.post(
            f"{BASE}/bookings/",
            json={"schedule_id": schedule_id, "membership_card_id": card_id},
            headers=auth_headers(student_token),
        )
        assert booked.status_code == 201, booked.text
        booking_id = booked.json()["data"]["id"]

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.PENDING.value
        # 期卡预约不扣次、不写 CONSUME
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1  # 仅 ISSUE

        cancelled = await client.post(
            f"{BASE}/bookings/{booking_id}/cancel?reason=测试取消",
            headers=auth_headers(student_token),
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["data"]["status"] == BookingStatus.CANCELLED.value

        # 期卡取消不写 RESTORE、不 400
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.PENDING.value
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id] if card_id else None,
            booking_ids=[booking_id] if booking_id else None,
            schedule_ids=[schedule_id], course_ids=[course_id], product_ids=[product_id],
        )


@pytest.mark.asyncio
async def test_count_card_deduct_and_cancel_restore(client: AsyncClient, env):
    factory, ids = env
    course_id = await create_course(factory, ids["tenant_id"])
    start_at = future_start(3)
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=start_at,
    )
    product_id = await create_product(
        factory, ids["tenant_id"], card_type=CardType.COUNT.value,
        validity_days=30, total_credits=5,
    )
    card_id = None
    booking_id = None
    try:
        admin_token = await login(client, SUPER_ADMIN)
        issued = await _issue_card(
            client, admin_token,
            {"student_id": ids["student_id"], "product_id": product_id},
        )
        assert issued.status_code == 201, issued.text
        card_id = issued.json()["data"]["id"]

        student_token = await login(client, SEED_STUDENT)
        booked = await client.post(
            f"{BASE}/bookings/",
            json={"schedule_id": schedule_id, "membership_card_id": card_id},
            headers=auth_headers(student_token),
        )
        assert booked.status_code == 201, booked.text
        booking_id = booked.json()["data"]["id"]

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.used_credits == 1

        cancelled = await client.post(
            f"{BASE}/bookings/{booking_id}/cancel?reason=测试取消",
            headers=auth_headers(student_token),
        )
        assert cancelled.status_code == 200, cancelled.text

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.used_credits == 0
    finally:
        await cleanup(
            factory, ids["tenant_id"], card_ids=[card_id] if card_id else None,
            booking_ids=[booking_id] if booking_id else None,
            schedule_ids=[schedule_id], course_ids=[course_id], product_ids=[product_id],
        )
