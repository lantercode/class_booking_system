"""预约创建 Idempotency-Key 幂等测试。

覆盖：
1. 同 key 同参数重试：返回同一 booking.id，不重复占名额 / 扣次 / 写幂等记录；
2. 同 key 不同参数：409，不产生第二笔预约；
3. 不带 key 重复创建：仍按原行为返回 400「请勿重复预约」。

测试直连 Service 层（与 Router 解耦），数据通过 tests.membership_support
的 helper 搭建与清理，避免污染开发库。
"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import delete, text

from app.core.exceptions import BusinessException
from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import IdempotencyKey
from app.modules.booking.schemas import BookingCreate
from app.modules.booking.service import BookingService
from app.modules.membership.models import CardStatus, CardType
from tests.membership_support import (
    cleanup,
    count_bookings_for_schedule,
    count_transactions,
    create_card,
    create_course,
    create_schedule,
    db_factory,
    fetch_card,
    fetch_schedule,
    future_start,
    get_seed_ids,
)


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        yield factory, ids


async def _book(
    factory,
    ids: dict,
    *,
    schedule_id: int,
    card_id: int | None = None,
    key: str | None = None,
):
    """以学员身份直调 Service 创建预约（独立 session，模拟一次请求）。"""
    async with factory() as db:
        set_tenant_id(ids["tenant_id"])
        return await BookingService().create_booking(
            db,
            BookingCreate(schedule_id=schedule_id, membership_card_id=card_id),
            student_id=ids["student_id"],
            idempotency_key=key,
        )


async def _cleanup_idempotency(factory, tenant_id: int, keys: list[str]) -> None:
    async with factory() as session:
        await session.execute(
            delete(IdempotencyKey).where(
                IdempotencyKey.tenant_id == tenant_id,
                IdempotencyKey.key.in_(keys),
            )
        )
        await session.commit()


async def _cleanup_schedule_jobs(
    factory, tenant_id: int, schedule_ids: list[int]
) -> None:
    async with factory() as session:
        for schedule_id in schedule_ids:
            await session.execute(
                text(
                    "DELETE FROM job_queue WHERE tenant_id = :tid "
                    "AND idempotency_key LIKE :key"
                ),
                {"tid": tenant_id, "key": f"schedule:{schedule_id}:%"},
            )
        await session.commit()


@pytest.mark.asyncio
async def test_same_key_same_request_returns_first_booking(env):
    factory, ids = env
    tenant_id = ids["tenant_id"]
    course_id = await create_course(factory, tenant_id)
    schedule_id = await create_schedule(
        factory,
        tenant_id,
        course_id=course_id,
        teacher_id=ids["teacher_id"],
        start_at=future_start(3),
    )
    card_id = await create_card(
        factory,
        tenant_id,
        ids["student_id"],
        card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value,
        total_credits=3,
        validity_days=30,
    )
    key = f"idem-{uuid4().hex[:12]}"
    try:
        first = await _book(
            factory, ids, schedule_id=schedule_id, card_id=card_id, key=key
        )
        second = await _book(
            factory, ids, schedule_id=schedule_id, card_id=card_id, key=key
        )

        # 幂等重放：同一笔预约
        assert second.id == first.id

        # 只落一条有效预约、名额只 +1、扣次流水只有 1 条
        assert await count_bookings_for_schedule(factory, tenant_id, schedule_id) == 1
        schedule = await fetch_schedule(factory, tenant_id, schedule_id)
        assert schedule.booked_count == 1
        assert await count_transactions(factory, tenant_id, card_id) == 1
        card = await fetch_card(factory, tenant_id, card_id)
        assert card.used_credits == 1
    finally:
        await _cleanup_idempotency(factory, tenant_id, [key])
        await _cleanup_schedule_jobs(factory, tenant_id, [schedule_id])
        await cleanup(
            factory,
            tenant_id,
            card_ids=[card_id],
            schedule_ids=[schedule_id],
            course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_same_key_different_request_conflicts(env):
    factory, ids = env
    tenant_id = ids["tenant_id"]
    course_id = await create_course(factory, tenant_id)
    first_schedule = await create_schedule(
        factory,
        tenant_id,
        course_id=course_id,
        teacher_id=ids["teacher_id"],
        start_at=future_start(3),
    )
    second_schedule = await create_schedule(
        factory,
        tenant_id,
        course_id=course_id,
        teacher_id=ids["teacher_id"],
        start_at=future_start(4),
    )
    key = f"idem-{uuid4().hex[:12]}"
    try:
        await _book(factory, ids, schedule_id=first_schedule, key=key)

        with pytest.raises(BusinessException) as exc:
            await _book(factory, ids, schedule_id=second_schedule, key=key)
        assert exc.value.code == 409
        assert "幂等键" in exc.value.msg

        # 第二笔不得落库
        assert (
            await count_bookings_for_schedule(factory, tenant_id, second_schedule) == 0
        )
    finally:
        await _cleanup_idempotency(factory, tenant_id, [key])
        await _cleanup_schedule_jobs(factory, tenant_id, [first_schedule, second_schedule])
        await cleanup(
            factory,
            tenant_id,
            schedule_ids=[first_schedule, second_schedule],
            course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_concurrent_same_key_only_creates_one_booking(env):
    """并发同 key 同参数：两个请求都返回同一笔预约，只落 1 条预约 / 1 次扣次。"""
    factory, ids = env
    tenant_id = ids["tenant_id"]
    course_id = await create_course(factory, tenant_id)
    schedule_id = await create_schedule(
        factory,
        tenant_id,
        course_id=course_id,
        teacher_id=ids["teacher_id"],
        start_at=future_start(5),
    )
    card_id = await create_card(
        factory,
        tenant_id,
        ids["student_id"],
        card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value,
        total_credits=3,
        validity_days=30,
    )
    key = f"idem-{uuid4().hex[:12]}"
    try:
        first, second = await asyncio.gather(
            _book(factory, ids, schedule_id=schedule_id, card_id=card_id, key=key),
            _book(factory, ids, schedule_id=schedule_id, card_id=card_id, key=key),
        )
        assert first.id == second.id
        assert await count_bookings_for_schedule(factory, tenant_id, schedule_id) == 1
        schedule = await fetch_schedule(factory, tenant_id, schedule_id)
        assert schedule.booked_count == 1
        assert await count_transactions(factory, tenant_id, card_id) == 1
    finally:
        await _cleanup_idempotency(factory, tenant_id, [key])
        await _cleanup_schedule_jobs(factory, tenant_id, [schedule_id])
        await cleanup(
            factory,
            tenant_id,
            card_ids=[card_id],
            schedule_ids=[schedule_id],
            course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_repeat_without_key_still_rejected(env):
    factory, ids = env
    tenant_id = ids["tenant_id"]
    course_id = await create_course(factory, tenant_id)
    schedule_id = await create_schedule(
        factory,
        tenant_id,
        course_id=course_id,
        teacher_id=ids["teacher_id"],
        start_at=future_start(3),
    )
    try:
        await _book(factory, ids, schedule_id=schedule_id, key=None)

        with pytest.raises(BusinessException) as exc:
            await _book(factory, ids, schedule_id=schedule_id, key=None)
        assert exc.value.code == 400
        assert "请勿重复预约" in exc.value.msg

        assert await count_bookings_for_schedule(factory, tenant_id, schedule_id) == 1
        schedule = await fetch_schedule(factory, tenant_id, schedule_id)
        assert schedule.booked_count == 1
    finally:
        await _cleanup_schedule_jobs(factory, tenant_id, [schedule_id])
        await cleanup(
            factory,
            tenant_id,
            schedule_ids=[schedule_id],
            course_ids=[course_id],
        )
