"""F6.5 原子改期 / 原子改派：功能、权限、租户、幂等与回滚。

验收映射：acceptance.md B 组（B-1 ~ B-20）与 C 组（C-1 ~ C-8）。
断言按真实实现（booking/service.py reschedule_booking）行为编写：
- 改期 = 旧约 CANCELLED + 新约 BOOKED，名额 -1/+1；
- 纯改派 = 同 booking 原地换卡，名额与 booked_at 不变；
- 次卡同卡改期 = RESTORE + CONSUME 两笔流水，净额不变。
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select, update

from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import Booking, BookingReschedule, BookingStatus
from app.modules.membership.models import (
    CardStatus,
    CardType,
    MembershipCardTransaction,
    TransactionType,
)
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.tenant.models import Tenant, TenantStatus
from tests.membership_support import (
    BASE,
    SEED_STUDENT,
    TENANT_HEADERS,
    cleanup,
    create_booking,
    create_card,
    create_course,
    create_schedule,
    create_student,
    db_factory,
    fetch_booking,
    fetch_card,
    fetch_schedule,
    future_start,
    get_seed_ids,
    login,
)
from tests.membership_support import headers as auth_headers


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        yield factory, ids


def _msg(resp) -> str:
    body = resp.json()
    return body.get("msg") or body.get("detail") or ""


async def _book(client: AsyncClient, token: str, schedule_id: int, card_id: int | None = None):
    payload: dict = {"schedule_id": schedule_id}
    if card_id is not None:
        payload["membership_card_id"] = card_id
    return await client.post(f"{BASE}/bookings/", json=payload, headers=auth_headers(token))


async def _reschedule(
    client: AsyncClient,
    token: str,
    booking_id: int,
    *,
    new_schedule_id: int,
    new_card_id: int | None = None,
    key: str | None = None,
    extra: dict | None = None,
):
    payload: dict = {"new_schedule_id": new_schedule_id}
    if new_card_id is not None:
        payload["new_membership_card_id"] = new_card_id
    if extra:
        payload.update(extra)
    headers = auth_headers(token)
    if key:
        headers["Idempotency-Key"] = key
    return await client.post(
        f"{BASE}/bookings/{booking_id}/reschedule", json=payload, headers=headers
    )


async def _schedule_count(factory, tenant_id: int, schedule_id: int) -> int:
    return (await fetch_schedule(factory, tenant_id, schedule_id)).booked_count


async def _booking_count(factory, tenant_id: int, schedule_id: int) -> int:
    async with factory() as session:
        set_tenant_id(tenant_id)
        return (
            await session.execute(
                select(func.count()).select_from(Booking).where(Booking.schedule_id == schedule_id)
            )
        ).scalar_one()


async def _audits(factory, tenant_id: int, old_booking_id: int) -> list[BookingReschedule]:
    async with factory() as session:
        set_tenant_id(tenant_id)
        return list(
            (
                await session.execute(
                    select(BookingReschedule)
                    .where(BookingReschedule.old_booking_id == old_booking_id)
                    .order_by(BookingReschedule.id)
                )
            )
            .scalars()
            .all()
        )


async def _txns(factory, tenant_id: int, card_id: int) -> list[tuple[str, str | None]]:
    async with factory() as session:
        set_tenant_id(tenant_id)
        rows = (
            await session.execute(
                select(MembershipCardTransaction).where(
                    MembershipCardTransaction.card_id == card_id
                )
            )
        ).scalars()
        return [(row.operation_type, row.idempotency_key) for row in rows]


async def _patch_schedule(factory, tenant_id: int, schedule_id: int, **values) -> None:
    async with factory() as session:
        set_tenant_id(tenant_id)
        await session.execute(
            update(CourseSchedule)
            .where(CourseSchedule.id == schedule_id)
            .values(**values)
        )
        await session.commit()


async def _create_other_tenant(factory) -> int:
    async with factory() as session:
        tenant = Tenant(
            name=f"F6.5隔离租户{uuid4().hex[:8]}",
            slug=f"f65-{uuid4().hex[:12]}",
            status=TenantStatus.ACTIVE.value,
        )
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        await session.commit()
    return tenant_id


async def _delete_tenant(factory, tenant_id: int) -> None:
    async with factory() as session:
        await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
        await session.commit()


# ============================================================
# B. 功能
# ============================================================


@pytest.mark.asyncio
async def test_b1_count_card_same_card_reschedule(client: AsyncClient, env):
    """B-1：次卡同卡改期，净额不变、两笔流水、名额 -1/+1。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid, name="F6.5次卡同卡")
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=6),
    )
    card_id = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid, card_id)
        assert created.status_code == 201, created.text
        old_booking_id = created.json()["data"]["id"]
        assert (await fetch_card(factory, tid, card_id)).used_credits == 1

        resp = await _reschedule(client, token, old_booking_id, new_schedule_id=new_sid)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["mode"] == "reschedule"
        assert data["previous_booking_id"] == old_booking_id
        assert data["previous_status"] == BookingStatus.BOOKED.value
        new_booking_id = data["booking"]["id"]
        assert new_booking_id != old_booking_id
        assert data["booking"]["schedule_id"] == new_sid
        assert data["booking"]["status"] == BookingStatus.BOOKED.value
        assert data["booking"]["membership_card_id"] == card_id

        old = await fetch_booking(factory, tid, old_booking_id)
        assert old.status == BookingStatus.CANCELLED.value
        assert old.cancelled_at is not None
        assert await _schedule_count(factory, tid, old_sid) == 0
        assert await _schedule_count(factory, tid, new_sid) == 1

        card = await fetch_card(factory, tid, card_id)
        assert card.used_credits == 1, "同卡改期净额应不变"
        txns = await _txns(factory, tid, card_id)
        assert len(txns) == 3, f"应有约课扣次 + 回补 + 再扣，实际 {txns}"
        restores = [key for op, key in txns if op == TransactionType.RESTORE.value]
        consumes = [key for op, key in txns if op == TransactionType.CONSUME.value]
        assert len(restores) == 1
        assert restores[0] and restores[0].startswith("reschedule_")
        assert restores[0].endswith("_restore")
        assert f"booking_{new_booking_id}_deduct" in consumes

        audits = await _audits(factory, tid, old_booking_id)
        assert len(audits) == 1
        assert audits[0].operation_type == "reschedule"
        assert audits[0].new_booking_id == new_booking_id
        assert audits[0].old_schedule_id == old_sid
        assert audits[0].new_schedule_id == new_sid
        assert audits[0].new_membership_card_id == card_id
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_b2_count_card_cross_card_reschedule(client: AsyncClient, env):
    """B-2：次卡异卡改期，旧卡 +1、新卡 -1，新约绑定新卡。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4, hour=6),
    )
    old_card = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    new_card = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid, old_card)
        assert created.status_code == 201, created.text
        old_booking_id = created.json()["data"]["id"]

        resp = await _reschedule(
            client, token, old_booking_id, new_schedule_id=new_sid,
            new_card_id=new_card,
        )
        assert resp.status_code == 200, resp.text
        new_booking_id = resp.json()["data"]["booking"]["id"]
        assert resp.json()["data"]["booking"]["membership_card_id"] == new_card

        assert (await fetch_card(factory, tid, old_card)).used_credits == 0
        assert (await fetch_card(factory, tid, new_card)).used_credits == 1
        old_txns = await _txns(factory, tid, old_card)
        new_txns = await _txns(factory, tid, new_card)
        assert [op for op, _ in old_txns] == [
            TransactionType.CONSUME.value,
            TransactionType.RESTORE.value,
        ]
        assert new_txns == [(TransactionType.CONSUME.value, f"booking_{new_booking_id}_deduct")]
        assert await _schedule_count(factory, tid, old_sid) == 0
        assert await _schedule_count(factory, tid, new_sid) == 1
    finally:
        await cleanup(
            factory, tid, card_ids=[old_card, new_card],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_b3_period_active_reschedule_keeps_validity(client: AsyncClient, env):
    """B-3：期卡 ACTIVE 改期，无次数流水、有效期不变。"""
    factory, ids = env
    tid = ids["tenant_id"]
    now = datetime.now(UTC)
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(5, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(5, hour=6),
    )
    card_id = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.PERIOD.value,
        status=CardStatus.ACTIVE.value, validity_days=30,
        valid_from=now - timedelta(days=1), expire_at=now + timedelta(days=30),
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid, card_id)
        assert created.status_code == 201, created.text
        old_booking_id = created.json()["data"]["id"]
        before = await fetch_card(factory, tid, card_id)

        resp = await _reschedule(client, token, old_booking_id, new_schedule_id=new_sid)
        assert resp.status_code == 200, resp.text

        after = await fetch_card(factory, tid, card_id)
        assert after.status == CardStatus.ACTIVE.value
        assert after.valid_from == before.valid_from
        assert after.expire_at == before.expire_at
        assert await _txns(factory, tid, card_id) == [], "期卡改期不应产生次数流水"
        assert await _schedule_count(factory, tid, old_sid) == 0
        assert await _schedule_count(factory, tid, new_sid) == 1
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_b4_period_pending_reschedule_reanchors(client: AsyncClient, env):
    """B-4：期卡 PENDING 改到更晚排期，锚点重算、仍 PENDING、不写有效期。

    旧排期 day3 + validity_days=7 时窗口为 [day3, day9]；目标 day10 只有
    在「取消旧约后的剩余预约 + 新约」重算锚点后才能通过（锚点=day10）。
    """
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(10, hour=2),
    )
    card_id = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.PERIOD.value,
        status=CardStatus.PENDING.value, validity_days=7,
        valid_from=None, expire_at=None,
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid, card_id)
        assert created.status_code == 201, created.text
        old_booking_id = created.json()["data"]["id"]

        resp = await _reschedule(client, token, old_booking_id, new_schedule_id=new_sid)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["booking"]["membership_card_id"] == card_id

        card = await fetch_card(factory, tid, card_id)
        assert card.status == CardStatus.PENDING.value
        assert card.valid_from is None
        assert card.expire_at is None
        assert await _txns(factory, tid, card_id) == []
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_b6_pure_card_swap(client: AsyncClient, env):
    """B-6：纯改派，booking id / booked_at / 名额不变，无新 booking。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(6, hour=2),
    )
    card_a = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    card_b = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, sid, card_a)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]
        before = await fetch_booking(factory, tid, booking_id)

        resp = await _reschedule(
            client, token, booking_id, new_schedule_id=sid, new_card_id=card_b,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["mode"] == "card_swap"
        assert data["booking"]["id"] == booking_id
        assert data["booking"]["schedule_id"] == sid
        assert data["booking"]["status"] == BookingStatus.BOOKED.value
        assert data["booking"]["membership_card_id"] == card_b

        after = await fetch_booking(factory, tid, booking_id)
        assert after.booked_at == before.booked_at
        assert after.status == BookingStatus.BOOKED.value
        assert await _schedule_count(factory, tid, sid) == 1
        assert await _booking_count(factory, tid, sid) == 1, "改派不应产生新 booking"

        assert (await fetch_card(factory, tid, card_a)).used_credits == 0
        assert (await fetch_card(factory, tid, card_b)).used_credits == 1
        audits = await _audits(factory, tid, booking_id)
        assert len(audits) == 1
        assert audits[0].operation_type == "card_swap"
        assert audits[0].new_booking_id == booking_id
        assert audits[0].old_membership_card_id == card_a
        assert audits[0].new_membership_card_id == card_b

        card_a_txns = await _txns(factory, tid, card_a)
        card_b_txns = await _txns(factory, tid, card_b)
        assert len(card_a_txns) == 2
        assert card_b_txns[0][1] == f"reschedule_{audits[0].id}_deduct"
    finally:
        await cleanup(
            factory, tid, card_ids=[card_a, card_b],
            schedule_ids=[sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        BookingStatus.CHECKED_IN.value,
        BookingStatus.COMPLETED.value,
        BookingStatus.NO_SHOW.value,
        BookingStatus.CANCELLED.value,
    ],
)
async def test_failure_non_booked_status(client: AsyncClient, env, status):
    """B-12：仅 BOOKED 可改期。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=6),
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=old_sid, student_id=ids["student_id"], status=status,
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _reschedule(client, token, booking_id, new_schedule_id=new_sid)
        assert resp.status_code == 400, resp.text
        assert "当前预约状态无法改期" in _msg(resp)
        booking = await fetch_booking(factory, tid, booking_id)
        assert booking.status == status
        assert await _booking_count(factory, tid, new_sid) == 0
        assert await _audits(factory, tid, booking_id) == []
    finally:
        await cleanup(
            factory, tid, booking_ids=[booking_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_failure_old_schedule_started(client: AsyncClient, env):
    """B-11/B-13：旧排期已开始 → 400。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(-1, hour=10),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=old_sid, student_id=ids["student_id"],
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _reschedule(client, token, booking_id, new_schedule_id=new_sid)
        assert resp.status_code == 400, resp.text
        assert "课程已开始" in _msg(resp)
        assert (await fetch_booking(factory, tid, booking_id)).status == BookingStatus.BOOKED.value
        assert await _booking_count(factory, tid, new_sid) == 0
    finally:
        await cleanup(
            factory, tid, booking_ids=[booking_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_failure_cancel_window(client: AsyncClient, env):
    """B-13：旧排期进入取消窗口（默认 90 分钟）→ 400；纯改派不受限（见 B-6）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]

        resp = await _reschedule(client, token, booking_id, new_schedule_id=new_sid)
        assert resp.status_code == 400, resp.text
        assert "不可取消" in _msg(resp)
        assert (await fetch_booking(factory, tid, booking_id)).status == BookingStatus.BOOKED.value
        assert await _schedule_count(factory, tid, old_sid) == 1
        assert await _booking_count(factory, tid, new_sid) == 0
    finally:
        await cleanup(
            factory, tid, schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_failure_target_full(client: AsyncClient, env):
    """B-8：目标排期已满 → 400「该排期已约满」。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=6), capacity=1,
    )
    await _patch_schedule(factory, tid, new_sid, booked_count=1)
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]

        resp = await _reschedule(client, token, booking_id, new_schedule_id=new_sid)
        assert resp.status_code == 400, resp.text
        assert "已约满" in _msg(resp)
        assert (await fetch_booking(factory, tid, booking_id)).status == BookingStatus.BOOKED.value
        assert await _schedule_count(factory, tid, new_sid) == 1
        assert await _booking_count(factory, tid, new_sid) == 0
        assert await _audits(factory, tid, booking_id) == []
    finally:
        await cleanup(
            factory, tid, schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_failure_target_cancelled(client: AsyncClient, env):
    """B-11：目标排期已取消 → 400。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=6),
    )
    await _patch_schedule(factory, tid, new_sid, status=ScheduleStatus.CANCELLED.value)
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]

        resp = await _reschedule(client, token, booking_id, new_schedule_id=new_sid)
        assert resp.status_code == 400, resp.text
        assert "已取消或已完成" in _msg(resp)
        assert (await fetch_booking(factory, tid, booking_id)).status == BookingStatus.BOOKED.value
        assert await _schedule_count(factory, tid, old_sid) == 1
        assert await _booking_count(factory, tid, new_sid) == 0
    finally:
        await cleanup(
            factory, tid, schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_failure_duplicate_active_booking_on_target(client: AsyncClient, env):
    """B-9 前置：同一学员已预约目标排期 → 400「请勿重复预约」。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4, hour=2),
    )
    token = await login(client, SEED_STUDENT)
    created = await _book(client, token, old_sid)
    assert created.status_code == 201, created.text
    booking_id = created.json()["data"]["id"]
    duplicate_id = await create_booking(
        factory, tid, schedule_id=new_sid, student_id=ids["student_id"],
    )
    try:
        resp = await _reschedule(client, token, booking_id, new_schedule_id=new_sid)
        assert resp.status_code == 400, resp.text
        assert "重复预约" in _msg(resp)
        assert (await fetch_booking(factory, tid, booking_id)).status == BookingStatus.BOOKED.value
        assert await _audits(factory, tid, booking_id) == []
    finally:
        await cleanup(
            factory, tid, booking_ids=[duplicate_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_failure_overlap_with_other_booking(client: AsyncClient, env):
    """B-9：目标时间段与学员其他预约重叠 → 400，文案含课程名。"""
    factory, ids = env
    tid = ids["tenant_id"]
    base = future_start(6, hour=2)
    old_course = await create_course(factory, tid, name="F6.5旧课")
    other_course = await create_course(factory, tid, name="F6.5冲突课")
    old_sid = await create_schedule(
        factory, tid, course_id=old_course, teacher_id=ids["teacher_id"],
        start_at=base,
    )
    target_sid = await create_schedule(
        factory, tid, course_id=old_course, teacher_id=ids["teacher_id"],
        start_at=base + timedelta(hours=1),
    )
    other_sid = await create_schedule(
        factory, tid, course_id=other_course, teacher_id=ids["teacher_id"],
        start_at=base + timedelta(minutes=90),
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]
        other = await _book(client, token, other_sid)
        assert other.status_code == 201, other.text

        resp = await _reschedule(client, token, booking_id, new_schedule_id=target_sid)
        assert resp.status_code == 400, resp.text
        message = _msg(resp)
        assert "冲突" in message
        assert "F6.5冲突课" in message
        assert (await fetch_booking(factory, tid, booking_id)).status == BookingStatus.BOOKED.value
        assert await _schedule_count(factory, tid, old_sid) == 1
        assert await _booking_count(factory, tid, target_sid) == 0
    finally:
        await cleanup(
            factory, tid,
            schedule_ids=[old_sid, target_sid, other_sid],
            course_ids=[old_course, other_course],
        )


@pytest.mark.asyncio
async def test_boundary_touching_target_allowed(client: AsyncClient, env):
    """B-10：目标与旧约边界相接（排除自身后无冲突）应放行。"""
    factory, ids = env
    tid = ids["tenant_id"]
    base = future_start(7, hour=2)
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base,
    )
    target_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=base + timedelta(hours=1),
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]

        resp = await _reschedule(client, token, booking_id, new_schedule_id=target_sid)
        assert resp.status_code == 200, resp.text
        assert await _schedule_count(factory, tid, old_sid) == 0
        assert await _schedule_count(factory, tid, target_sid) == 1
    finally:
        await cleanup(
            factory, tid, schedule_ids=[old_sid, target_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_failure_no_card_booking_cannot_attach_card(client: AsyncClient, env):
    """B-16：原预约无卡 + 请求带新卡 → 400。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=6),
    )
    card_id = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=old_sid, student_id=ids["student_id"],
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _reschedule(
            client, token, booking_id, new_schedule_id=new_sid, new_card_id=card_id,
        )
        assert resp.status_code == 400, resp.text
        assert "暂不支持改派" in _msg(resp)
        assert (await fetch_booking(factory, tid, booking_id)).status == BookingStatus.BOOKED.value
        assert (await fetch_card(factory, tid, card_id)).used_credits == 0
        assert await _booking_count(factory, tid, new_sid) == 0
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_failure_same_schedule_same_card(client: AsyncClient, env):
    """B-7：同排期同卡 → 400「未发生改期或改派」，无写入。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    card_id = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, sid, card_id)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]

        for extra_card in (None, card_id):
            resp = await _reschedule(
                client, token, booking_id, new_schedule_id=sid, new_card_id=extra_card,
            )
            assert resp.status_code == 400, resp.text
            assert "未发生改期或改派" in _msg(resp)

        assert (await fetch_card(factory, tid, card_id)).used_credits == 1
        assert await _audits(factory, tid, booking_id) == []
        assert await _schedule_count(factory, tid, sid) == 1
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], schedule_ids=[sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_no_card_booking_reschedule_keeps_no_card(client: AsyncClient, env):
    """B-17：原预约无卡改期到另一排期（不带卡）→ 200，新旧 booking 均无卡。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=6),
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=old_sid, student_id=ids["student_id"],
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _reschedule(client, token, booking_id, new_schedule_id=new_sid)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["booking"]["membership_card_id"] is None
        assert await _schedule_count(factory, tid, old_sid) == 0
        assert await _schedule_count(factory, tid, new_sid) == 1
    finally:
        await cleanup(
            factory, tid, booking_ids=[booking_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_b18_rollback_when_target_card_deduct_fails(client: AsyncClient, env):
    """B-18：回补成功后扣次失败（目标次卡余额为 0）→ 整体回滚。

    服务端运行在独立 Uvicorn 线程/进程内，monkeypatch 不跨进程生效，
    因此用「余额不足的次卡」在真实事务内制造 deduct_credit 失败。
    """
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4, hour=6),
    )
    old_card = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    full_card = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=1, used_credits=1,
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid, old_card)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]

        resp = await _reschedule(
            client, token, booking_id, new_schedule_id=new_sid, new_card_id=full_card,
        )
        assert resp.status_code == 400, resp.text
        assert "次数已用完" in _msg(resp)

        assert (await fetch_booking(factory, tid, booking_id)).status == BookingStatus.BOOKED.value
        assert (await fetch_card(factory, tid, old_card)).used_credits == 1
        assert (await fetch_card(factory, tid, full_card)).used_credits == 1
        assert await _schedule_count(factory, tid, old_sid) == 1
        assert await _schedule_count(factory, tid, new_sid) == 0
        assert await _booking_count(factory, tid, new_sid) == 0
        assert await _audits(factory, tid, booking_id) == []
        assert len(await _txns(factory, tid, old_card)) == 1, "回补流水必须随事务回滚"
        assert await _txns(factory, tid, full_card) == []
    finally:
        await cleanup(
            factory, tid, card_ids=[old_card, full_card],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_b19_idempotency_key_replay(client: AsyncClient, env):
    """B-19：同 Idempotency-Key 重放 → 同一新 booking、仅 1 条审计/1 条新 booking。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(5, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(5, hour=6),
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=old_sid, student_id=ids["student_id"],
    )
    key = f"f65-{uuid4().hex}"
    try:
        token = await login(client, SEED_STUDENT)
        first = await _reschedule(
            client, token, booking_id, new_schedule_id=new_sid, key=key,
        )
        assert first.status_code == 200, first.text
        new_booking_id = first.json()["data"]["booking"]["id"]

        second = await _reschedule(
            client, token, booking_id, new_schedule_id=new_sid, key=key,
        )
        assert second.status_code == 200, second.text
        assert second.json()["data"]["booking"]["id"] == new_booking_id

        audits = await _audits(factory, tid, booking_id)
        assert len(audits) == 1
        assert audits[0].request_key == key
        assert audits[0].new_booking_id == new_booking_id
        assert await _booking_count(factory, tid, new_sid) == 1
    finally:
        await cleanup(
            factory, tid, booking_ids=[booking_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_b19_replay_without_key_uses_audit(client: AsyncClient, env):
    """B-19：同参数无幂等键重放（旧约已 CANCELLED + 审计命中）→ 重放同一结果。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(6, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(6, hour=6),
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=old_sid, student_id=ids["student_id"],
    )
    try:
        token = await login(client, SEED_STUDENT)
        first = await _reschedule(client, token, booking_id, new_schedule_id=new_sid)
        assert first.status_code == 200, first.text
        new_booking_id = first.json()["data"]["booking"]["id"]

        replay = await _reschedule(client, token, booking_id, new_schedule_id=new_sid)
        assert replay.status_code == 200, replay.text
        assert replay.json()["data"]["booking"]["id"] == new_booking_id
        assert len(await _audits(factory, tid, booking_id)) == 1
        assert await _booking_count(factory, tid, new_sid) == 1
    finally:
        await cleanup(
            factory, tid, booking_ids=[booking_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_b20_same_key_different_params_conflict(client: AsyncClient, env):
    """B-20：同 Idempotency-Key + 不同目标参数 → 409，不产生第二次变更。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(7, hour=2),
    )
    first_target = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(7, hour=6),
    )
    second_target = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(8, hour=2),
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=old_sid, student_id=ids["student_id"],
    )
    key = f"f65-{uuid4().hex}"
    try:
        token = await login(client, SEED_STUDENT)
        first = await _reschedule(
            client, token, booking_id, new_schedule_id=first_target, key=key,
        )
        assert first.status_code == 200, first.text
        new_booking_id = first.json()["data"]["booking"]["id"]

        conflict = await _reschedule(
            client, token, booking_id, new_schedule_id=second_target, key=key,
        )
        assert conflict.status_code == 409, conflict.text
        assert "幂等键" in _msg(conflict)

        assert await _booking_count(factory, tid, second_target) == 0
        assert await _schedule_count(factory, tid, second_target) == 0
        audits = await _audits(factory, tid, booking_id)
        assert len(audits) == 1
        assert audits[0].new_booking_id == new_booking_id
    finally:
        await cleanup(
            factory, tid, booking_ids=[booking_id],
            schedule_ids=[old_sid, first_target, second_target],
            course_ids=[course_id],
        )


# ============================================================
# C. 权限与租户
# ============================================================


@pytest.mark.asyncio
async def test_c1_unauthenticated_returns_401(client: AsyncClient):
    resp = await client.post(
        f"{BASE}/bookings/999999999/reschedule",
        json={"new_schedule_id": 1},
        headers=TENANT_HEADERS,
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_c2_teacher_forbidden(client: AsyncClient, env):
    """C-2：teacher 角色调用 → 403（@require_roles("student")）。

    使用本用例新建的 teacher（仅 teacher 角色），避免共享种子用户被其他
    测试追加角色造成污染。
    """
    factory, ids = env
    teacher = await create_student(factory, ids["tenant_id"], role_code="teacher")
    try:
        token = await login(client, teacher)
        resp = await _reschedule(client, token, 999999999, new_schedule_id=1)
        assert resp.status_code == 403, resp.text
    finally:
        await cleanup(
            factory, ids["tenant_id"], student_ids=[teacher["user_id"]]
        )


@pytest.mark.asyncio
async def test_c3_admin_forbidden(client: AsyncClient, env):
    """C-3：admin/super_admin 调用 → 403（本版不做代改）。"""
    factory, ids = env
    admin = await create_student(factory, ids["tenant_id"], role_code="admin")
    try:
        token = await login(client, admin)
        resp = await _reschedule(client, token, 999999999, new_schedule_id=1)
        assert resp.status_code == 403, resp.text
    finally:
        await cleanup(factory, ids["tenant_id"], student_ids=[admin["user_id"]])


@pytest.mark.asyncio
async def test_c4_non_owner_forbidden(client: AsyncClient, env):
    """C-4：学员 A 改学员 B 的预约 → 403，且预约不变。"""
    factory, ids = env
    tid = ids["tenant_id"]
    other = await create_student(factory, tid)
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=6),
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=old_sid, student_id=other["user_id"],
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _reschedule(client, token, booking_id, new_schedule_id=new_sid)
        assert resp.status_code == 403, resp.text
        assert "只能改期自己的预约" in _msg(resp)
        assert (await fetch_booking(factory, tid, booking_id)).status == BookingStatus.BOOKED.value
        assert await _audits(factory, tid, booking_id) == []
    finally:
        await cleanup(
            factory, tid, booking_ids=[booking_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
            student_ids=[other["user_id"]],
        )


@pytest.mark.asyncio
async def test_c5_cross_tenant_booking_returns_404(client: AsyncClient, env):
    """C-5：A 租户 token 改 B 租户 booking → 404（TenantAwareRepository 过滤）。"""
    factory, ids = env
    tenant_b = await _create_other_tenant(factory)
    course_b = await create_course(factory, tenant_b)
    schedule_b = await create_schedule(
        factory, tenant_b, course_id=course_b, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    booking_b = await create_booking(
        factory, tenant_b, schedule_id=schedule_b, student_id=ids["student_id"],
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _reschedule(client, token, booking_b, new_schedule_id=schedule_b)
        assert resp.status_code == 404, resp.text
        assert "预约不存在" in _msg(resp)
    finally:
        await cleanup(
            factory, tenant_b, booking_ids=[booking_b],
            schedule_ids=[schedule_b], course_ids=[course_b],
        )
        await _delete_tenant(factory, tenant_b)


@pytest.mark.asyncio
async def test_c6_other_student_card_forbidden(client: AsyncClient, env):
    """C-6：使用其他学员的卡作为目标卡 → 403。"""
    factory, ids = env
    tid = ids["tenant_id"]
    other = await create_student(factory, tid)
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4, hour=6),
    )
    my_card = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    other_card = await create_card(
        factory, tid, other["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid, my_card)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]

        resp = await _reschedule(
            client, token, booking_id, new_schedule_id=new_sid, new_card_id=other_card,
        )
        assert resp.status_code == 403, resp.text
        assert "无权使用此会员卡" in _msg(resp)
        assert (await fetch_card(factory, tid, my_card)).used_credits == 1
        assert (await fetch_card(factory, tid, other_card)).used_credits == 0
        assert (await fetch_booking(factory, tid, booking_id)).status == BookingStatus.BOOKED.value
        assert await _booking_count(factory, tid, new_sid) == 0
    finally:
        await cleanup(
            factory, tid, card_ids=[my_card, other_card],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
            student_ids=[other["user_id"]],
        )


@pytest.mark.asyncio
async def test_c7_cross_tenant_card_returns_404(client: AsyncClient, env):
    """C-7：使用其他租户的卡 → 404（租户过滤为「不存在」）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    tenant_b = await _create_other_tenant(factory)
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(5, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(5, hour=6),
    )
    my_card = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    foreign_card = await create_card(
        factory, tenant_b, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid, my_card)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]

        resp = await _reschedule(
            client, token, booking_id, new_schedule_id=new_sid,
            new_card_id=foreign_card,
        )
        assert resp.status_code == 404, resp.text
        assert "会员卡不存在" in _msg(resp)
        assert (await fetch_booking(factory, tid, booking_id)).status == BookingStatus.BOOKED.value
        assert await _booking_count(factory, tid, new_sid) == 0
    finally:
        await cleanup(
            factory, tid, card_ids=[my_card],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )
        await cleanup(factory, tenant_b, card_ids=[foreign_card])
        await _delete_tenant(factory, tenant_b)


@pytest.mark.asyncio
async def test_c8_forged_identity_fields_ignored(client: AsyncClient, env):
    """C-8：请求体伪造 student_id / tenant_id 被忽略，身份仍来自 JWT。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(6, hour=2),
    )
    new_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(6, hour=6),
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=old_sid, student_id=ids["student_id"],
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _reschedule(
            client, token, booking_id, new_schedule_id=new_sid,
            extra={"student_id": 999999, "tenant_id": 999999},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["booking"]["student_id"] == ids["student_id"]
        audits = await _audits(factory, tid, booking_id)
        assert audits[0].operator_id == ids["student_id"]
    finally:
        await cleanup(
            factory, tid, booking_ids=[booking_id],
            schedule_ids=[old_sid, new_sid], course_ids=[course_id],
        )
