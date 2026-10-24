"""F6.4：预约跨排期时间段重叠校验（D10）。"""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import Booking, BookingStatus
from app.modules.booking.repository import BookingRepository
from app.modules.schedule.models import CourseSchedule
from app.modules.tenant.models import Tenant, TenantStatus
from tests.membership_support import (
    BASE,
    SEED_STUDENT,
    cleanup,
    create_booking,
    create_course,
    create_schedule,
    db_factory,
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


def _msg(resp) -> str:
    body = resp.json()
    return body.get("msg") or body.get("detail") or ""


async def _book(client: AsyncClient, token: str, schedule_id: int):
    return await client.post(
        f"{BASE}/bookings/",
        json={"schedule_id": schedule_id},
        headers=auth_headers(token),
    )


async def _count_bookings(factory, tenant_id: int, schedule_id: int) -> int:
    async with factory() as session:
        set_tenant_id(tenant_id)
        return (
            await session.execute(
                select(func.count())
                .select_from(Booking)
                .where(Booking.schedule_id == schedule_id)
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_overlap_rejected_with_course_and_window(client: AsyncClient, env):
    factory, ids = env
    base = future_start(3, hour=2)
    course_id = await create_course(factory, ids["tenant_id"], name="拉丁舞基础")
    other_course_id = await create_course(factory, ids["tenant_id"], name="芭蕾形体")
    first_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base,
    )
    second_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=other_course_id,
        teacher_id=ids["teacher_id"], start_at=base + timedelta(minutes=30),
    )
    try:
        token = await login(client, SEED_STUDENT)
        first = await _book(client, token, first_schedule)
        assert first.status_code == 201, first.text

        second = await _book(client, token, second_schedule)
        assert second.status_code == 400, second.text
        message = _msg(second)
        assert "冲突" in message
        assert "拉丁舞基础" in message
        assert "10:" in message  # 含时间段

        # 不落库、不占名额
        assert await _count_bookings(factory, ids["tenant_id"], second_schedule) == 0
        async with factory() as session:
            set_tenant_id(ids["tenant_id"])
            schedule = (
                await session.execute(
                    select(CourseSchedule).where(CourseSchedule.id == second_schedule)
                )
            ).scalar_one()
            assert schedule.booked_count == 0
    finally:
        await cleanup(
            factory, ids["tenant_id"],
            schedule_ids=[first_schedule, second_schedule],
            course_ids=[course_id, other_course_id],
        )


@pytest.mark.asyncio
async def test_boundary_touching_allowed(client: AsyncClient, env):
    factory, ids = env
    base = future_start(4, hour=2)
    course_id = await create_course(factory, ids["tenant_id"])
    first_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base,
    )
    # 首段 1 小时，目标从 11:00 开始：边界相接不算冲突
    second_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base + timedelta(hours=1),
    )
    try:
        token = await login(client, SEED_STUDENT)
        assert (await _book(client, token, first_schedule)).status_code == 201
        second = await _book(client, token, second_schedule)
        assert second.status_code == 201, second.text
    finally:
        await cleanup(
            factory, ids["tenant_id"],
            schedule_ids=[first_schedule, second_schedule], course_ids=[course_id],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [BookingStatus.CANCELLED.value, BookingStatus.COMPLETED.value, BookingStatus.NO_SHOW.value],
)
async def test_terminal_statuses_do_not_block(client: AsyncClient, env, status):
    factory, ids = env
    base = future_start(5, hour=2)
    course_id = await create_course(factory, ids["tenant_id"])
    existing_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base,
    )
    target_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base + timedelta(minutes=30),
    )
    await create_booking(
        factory, ids["tenant_id"], schedule_id=existing_schedule,
        student_id=ids["student_id"], status=status,
    )
    try:
        token = await login(client, SEED_STUDENT)
        target = await _book(client, token, target_schedule)
        assert target.status_code == 201, target.text
    finally:
        await cleanup(
            factory, ids["tenant_id"],
            schedule_ids=[existing_schedule, target_schedule], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_checked_in_blocks_overlap(client: AsyncClient, env):
    factory, ids = env
    base = future_start(6, hour=2)
    course_id = await create_course(factory, ids["tenant_id"])
    existing_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base,
    )
    target_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base + timedelta(minutes=30),
    )
    await create_booking(
        factory, ids["tenant_id"], schedule_id=existing_schedule,
        student_id=ids["student_id"], status=BookingStatus.CHECKED_IN.value,
    )
    try:
        token = await login(client, SEED_STUDENT)
        target = await _book(client, token, target_schedule)
        assert target.status_code == 400, target.text
        assert "冲突" in _msg(target)
    finally:
        await cleanup(
            factory, ids["tenant_id"],
            schedule_ids=[existing_schedule, target_schedule], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_cross_tenant_isolation(env):
    """C-3：另一租户上下文下查询不到本租户学员的冲突预约。"""
    factory, ids = env
    base = future_start(7, hour=2)
    course_id = await create_course(factory, ids["tenant_id"])
    schedule_id = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base,
    )
    await create_booking(
        factory, ids["tenant_id"], schedule_id=schedule_id,
        student_id=ids["student_id"], status=BookingStatus.BOOKED.value,
    )

    tenant_b_id = None
    try:
        async with factory() as session:
            tenant_b = Tenant(
                name="F6.4 隔离租户",
                slug=f"f64-isolation-{uuid4().hex[:8]}",
                status=TenantStatus.ACTIVE.value,
            )
            session.add(tenant_b)
            await session.flush()
            tenant_b_id = tenant_b.id
            await session.commit()

        # 同租户：可查到冲突
        async with factory() as session:
            set_tenant_id(ids["tenant_id"])
            repo = BookingRepository()
            conflict = await repo.find_overlapping_active_booking(
                session,
                student_id=ids["student_id"],
                start_at=base + timedelta(minutes=30),
                end_at=base + timedelta(minutes=90),
            )
            assert conflict is not None

        # 另一租户：查询为空（隔离生效）
        async with factory() as session:
            set_tenant_id(tenant_b_id)
            conflict = await BookingRepository().find_overlapping_active_booking(
                session,
                student_id=ids["student_id"],
                start_at=base + timedelta(minutes=30),
                end_at=base + timedelta(minutes=90),
            )
            assert conflict is None
    finally:
        if tenant_b_id:
            async with factory() as session:
                await session.execute(delete(Tenant).where(Tenant.id == tenant_b_id))
                await session.commit()
        await cleanup(
            factory, ids["tenant_id"], schedule_ids=[schedule_id], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_concurrent_overlapping_bookings_only_one_succeeds(
    client: AsyncClient, env
):
    factory, ids = env
    base = future_start(8, hour=2)
    course_id = await create_course(factory, ids["tenant_id"])
    first_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base,
    )
    second_schedule = await create_schedule(
        factory, ids["tenant_id"], course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base + timedelta(minutes=30),
    )
    try:
        token = await login(client, SEED_STUDENT)
        responses = await asyncio.gather(
            _book(client, token, first_schedule),
            _book(client, token, second_schedule),
        )
        codes = sorted(r.status_code for r in responses)
        assert codes == [201, 400], [r.text for r in responses]

        total = await _count_bookings(factory, ids["tenant_id"], first_schedule) + (
            await _count_bookings(factory, ids["tenant_id"], second_schedule)
        )
        assert total == 1
    finally:
        await cleanup(
            factory, ids["tenant_id"],
            schedule_ids=[first_schedule, second_schedule], course_ids=[course_id],
        )
