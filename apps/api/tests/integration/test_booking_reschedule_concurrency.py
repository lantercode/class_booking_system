"""F6.5 原子改期 / 原子改派：并发、锁序、死锁与幂等（D 组）。

并发模型：集成测试经真实 Uvicorn（8765）发起请求，数据库层行锁/advisory lock
跨连接生效。所有并发用例用 ``asyncio.wait_for(..., timeout=15)`` 兜底，
超时即视为死锁回归失败。
"""

import asyncio
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import Booking, BookingReschedule, BookingStatus
from app.modules.membership.models import (
    CardStatus,
    CardType,
    MembershipCardTransaction,
    TransactionType,
)
from app.modules.schedule.models import ScheduleStatus
from tests.membership_support import (
    BASE,
    SEED_STUDENT,
    SUPER_ADMIN,
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

TIMEOUT = 15


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


async def _reschedule(
    client: AsyncClient,
    token: str,
    booking_id: int,
    new_schedule_id: int,
    key: str | None = None,
):
    headers = auth_headers(token)
    if key:
        headers["Idempotency-Key"] = key
    return await client.post(
        f"{BASE}/bookings/{booking_id}/reschedule",
        json={"new_schedule_id": new_schedule_id},
        headers=headers,
    )


async def _gather(*coros):
    return await asyncio.wait_for(asyncio.gather(*coros), timeout=TIMEOUT)


async def _booking_count(factory, tenant_id: int, schedule_id: int) -> int:
    async with factory() as session:
        set_tenant_id(tenant_id)
        return (
            await session.execute(
                select(func.count()).select_from(Booking).where(Booking.schedule_id == schedule_id)
            )
        ).scalar_one()


async def _active_booking_count(factory, tenant_id: int, schedule_id: int) -> int:
    async with factory() as session:
        set_tenant_id(tenant_id)
        return (
            await session.execute(
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.schedule_id == schedule_id,
                    Booking.status.in_(
                        [
                            BookingStatus.BOOKED.value,
                            BookingStatus.CHECKED_IN.value,
                            BookingStatus.COMPLETED.value,
                        ]
                    ),
                )
            )
        ).scalar_one()


async def _audit_count(factory, tenant_id: int, old_booking_id: int) -> int:
    async with factory() as session:
        set_tenant_id(tenant_id)
        return (
            await session.execute(
                select(func.count())
                .select_from(BookingReschedule)
                .where(BookingReschedule.old_booking_id == old_booking_id)
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_d1_same_booking_two_targets_only_one_succeeds(client: AsyncClient, env):
    """D-1：同一 booking 并发改到两个不同目标 → 恰一个成功，1 审计 / 1 新 booking。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    target_a = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=6),
    )
    target_b = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4, hour=6),
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]

        first, second = await _gather(
            _reschedule(client, token, booking_id, target_a),
            _reschedule(client, token, booking_id, target_b),
        )
        codes = sorted([first.status_code, second.status_code])
        assert codes == [200, 409], [first.text, second.text]
        loser = first if first.status_code == 409 else second
        assert "改期" in _msg(loser) or "幂等" in _msg(loser)

        assert await _audit_count(factory, tid, booking_id) == 1
        assert await _booking_count(factory, tid, target_a) + (
            await _booking_count(factory, tid, target_b)
        ) == 1
        assert await _active_booking_count(factory, tid, old_sid) == 0
        assert (await fetch_booking(factory, tid, booking_id)).status == (
            BookingStatus.CANCELLED.value
        )
    finally:
        await cleanup(
            factory, tid, schedule_ids=[old_sid, target_a, target_b],
            course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_d2_same_student_two_bookings_two_targets(client: AsyncClient, env):
    """D-2（验收）：同一学员并发把两笔预约改到不同目标 → advisory lock 串行，均成功。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    s1 = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=2),
    )
    s2 = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=6),
    )
    t1 = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4, hour=2),
    )
    t2 = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(5, hour=2),
    )
    try:
        token = await login(client, SEED_STUDENT)
        created_a = await _book(client, token, s1)
        assert created_a.status_code == 201, created_a.text
        booking_a = created_a.json()["data"]["id"]
        created_b = await _book(client, token, s2)
        assert created_b.status_code == 201, created_b.text
        booking_b = created_b.json()["data"]["id"]

        resp_a, resp_b = await _gather(
            _reschedule(client, token, booking_a, t1),
            _reschedule(client, token, booking_b, t2),
        )
        assert resp_a.status_code == 200, resp_a.text
        assert resp_b.status_code == 200, resp_b.text

        assert (await fetch_schedule(factory, tid, t1)).booked_count == 1
        assert (await fetch_schedule(factory, tid, t2)).booked_count == 1
        assert (await fetch_schedule(factory, tid, s1)).booked_count == 0
        assert (await fetch_schedule(factory, tid, s2)).booked_count == 0
        assert await _active_booking_count(factory, tid, t1) == 1
        assert await _active_booking_count(factory, tid, t2) == 1
        assert await _audit_count(factory, tid, booking_a) == 1
        assert await _audit_count(factory, tid, booking_b) == 1
    finally:
        await cleanup(
            factory, tid, schedule_ids=[s1, s2, t1, t2], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_d3_same_student_create_vs_reschedule(client: AsyncClient, env):
    """D-3（验收）：同一学员并发「创建预约」与「改期」到重叠时段 → 仅一个成功。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4, hour=2),
    )
    create_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(5, hour=2),
    )
    target = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(5, hour=2),
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await _book(client, token, old_sid)
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]

        resp_create, resp_reschedule = await _gather(
            _book(client, token, create_sid),
            _reschedule(client, token, booking_id, target),
        )
        codes = sorted([resp_create.status_code, resp_reschedule.status_code])
        successes = [code for code in codes if code < 400]
        assert len(successes) == 1, (
            f"重叠时段并发应恰一个成功，实际 {codes}; "
            f"create 排期名额={await _active_booking_count(factory, tid, create_sid)}, "
            f"target 排期名额={await _active_booking_count(factory, tid, target)}"
        )
        loser = resp_create if resp_create.status_code >= 400 else resp_reschedule
        assert loser.status_code == 400, loser.text
        assert "冲突" in _msg(loser), loser.text

        # 最终只存在一条 day5 02:00 的进行中预约
        assert (
            await _active_booking_count(factory, tid, create_sid)
            + await _active_booking_count(factory, tid, target)
        ) == 1
        if resp_reschedule.status_code == 200:
            assert await _active_booking_count(factory, tid, old_sid) == 0
        else:
            assert await _active_booking_count(factory, tid, old_sid) == 1
    finally:
        await cleanup(
            factory, tid, schedule_ids=[old_sid, create_sid, target],
            course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_d4_reverse_reschedule_no_deadlock(client: AsyncClient, env):
    """D-4（验收）：学员 A：S1→S2；学员 B：S2→S1 并发，全部成功且无死锁。"""
    factory, ids = env
    tid = ids["tenant_id"]
    other = await create_student(factory, tid)
    course_id = await create_course(factory, tid)
    s1 = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(5, hour=2),
    )
    s2 = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(5, hour=6),
    )
    try:
        token_a = await login(client, SEED_STUDENT)
        token_b = await login(client, other)
        created_a = await _book(client, token_a, s1)
        assert created_a.status_code == 201, created_a.text
        booking_a = created_a.json()["data"]["id"]
        created_b = await _book(client, token_b, s2)
        assert created_b.status_code == 201, created_b.text
        booking_b = created_b.json()["data"]["id"]

        resp_a, resp_b = await _gather(
            _reschedule(client, token_a, booking_a, s2),
            _reschedule(client, token_b, booking_b, s1),
        )
        assert resp_a.status_code == 200, resp_a.text
        assert resp_b.status_code == 200, resp_b.text

        counts = (
            (await fetch_schedule(factory, tid, s1)).booked_count,
            (await fetch_schedule(factory, tid, s2)).booked_count,
        )
        active = (
            await _active_booking_count(factory, tid, s1),
            await _active_booking_count(factory, tid, s2),
        )
        assert counts == (1, 1), (
            f"反向改期后名额应各为 1，实际 {counts}; 活跃 booking 数={active}"
        )
        assert (await fetch_booking(factory, tid, booking_a)).status == (
            BookingStatus.CANCELLED.value
        )
        assert (await fetch_booking(factory, tid, booking_b)).status == (
            BookingStatus.CANCELLED.value
        )
        assert await _audit_count(factory, tid, booking_a) == 1
        assert await _audit_count(factory, tid, booking_b) == 1
        assert await _active_booking_count(factory, tid, s1) == 1
        assert await _active_booking_count(factory, tid, s2) == 1
    finally:
        await cleanup(
            factory, tid, schedule_ids=[s1, s2], course_ids=[course_id],
            student_ids=[other["user_id"]],
        )


@pytest.mark.asyncio
async def test_d3_extra_last_seat_cross_student_only_one_wins(client: AsyncClient, env):
    """D-3 补充（容量）：两个学员并发抢目标排期最后一个名额 → 至多一个成功，booked_count<=capacity。"""
    factory, ids = env
    tid = ids["tenant_id"]
    other = await create_student(factory, tid)
    course_id = await create_course(factory, tid)
    s_a = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(6, hour=2),
    )
    s_b = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(6, hour=6),
    )
    target = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(6, hour=10), capacity=1,
    )
    try:
        token_a = await login(client, SEED_STUDENT)
        token_b = await login(client, other)
        created_a = await _book(client, token_a, s_a)
        assert created_a.status_code == 201, created_a.text
        booking_a = created_a.json()["data"]["id"]
        created_b = await _book(client, token_b, s_b)
        assert created_b.status_code == 201, created_b.text
        booking_b = created_b.json()["data"]["id"]

        resp_a, resp_b = await _gather(
            _reschedule(client, token_a, booking_a, target),
            _reschedule(client, token_b, booking_b, target),
        )
        target_schedule = await fetch_schedule(factory, tid, target)
        active_on_target = await _active_booking_count(factory, tid, target)
        codes = sorted([resp_a.status_code, resp_b.status_code])
        assert codes == [200, 400], (
            f"抢最后一个名额应至多一个成功，实际 {codes}; "
            f"target.booked_count={target_schedule.booked_count}, "
            f"target 活跃 booking={active_on_target}"
        )
        loser = resp_a if resp_a.status_code == 400 else resp_b
        assert "已约满" in _msg(loser)

        assert target_schedule.booked_count == 1
        assert target_schedule.booked_count <= target_schedule.capacity
        assert active_on_target == 1
        assert await _audit_count(factory, tid, booking_a) + (
            await _audit_count(factory, tid, booking_b)
        ) == 1

        # 失败方旧约保持 BOOKED，旧排期名额未被误减
        statuses = [
            (await fetch_booking(factory, tid, booking_a)).status,
            (await fetch_booking(factory, tid, booking_b)).status,
        ]
        assert sorted(statuses) == [BookingStatus.BOOKED.value, BookingStatus.CANCELLED.value]
        assert (await fetch_schedule(factory, tid, s_a)).booked_count + (
            await fetch_schedule(factory, tid, s_b)
        ).booked_count == 1
    finally:
        await cleanup(
            factory, tid, schedule_ids=[s_a, s_b, target], course_ids=[course_id],
            student_ids=[other["user_id"]],
        )


@pytest.mark.asyncio
async def test_d5_reschedule_vs_cancel_same_booking(client: AsyncClient, env):
    """D-5（验收）：改期 vs 取消同一 booking → 恰一个成功，无双重回补。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(7, hour=2),
    )
    target = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(7, hour=6),
    )
    card_id = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    try:
        token = await login(client, SEED_STUDENT)
        created = await client.post(
            f"{BASE}/bookings/",
            json={"schedule_id": old_sid, "membership_card_id": card_id},
            headers=auth_headers(token),
        )
        assert created.status_code == 201, created.text
        booking_id = created.json()["data"]["id"]

        resp_reschedule, resp_cancel = await _gather(
            _reschedule(client, token, booking_id, target),
            client.post(
                f"{BASE}/bookings/{booking_id}/cancel", headers=auth_headers(token)
            ),
        )
        card = await fetch_card(factory, tid, card_id)
        async with factory() as session:
            set_tenant_id(tid)
            rows = (
                await session.execute(
                    select(MembershipCardTransaction).where(
                        MembershipCardTransaction.card_id == card_id
                    )
                )
            ).scalars()
            ops = [row.operation_type for row in rows]

        codes = sorted([resp_reschedule.status_code, resp_cancel.status_code])
        assert codes == [200, 400], (
            f"改期与取消应恰一成功，实际 {codes}; "
            f"card.used_credits={card.used_credits}, operations={ops}"
        )

        reschedule_won = resp_reschedule.status_code == 200
        if reschedule_won:
            # 初始 CONSUME + RESTORE + 新约 CONSUME
            assert card.used_credits == 1
            assert await _booking_count(factory, tid, target) == 1
        else:
            # 初始 CONSUME + 取消 RESTORE
            assert card.used_credits == 0
            assert await _booking_count(factory, tid, target) == 0
        assert (await fetch_booking(factory, tid, booking_id)).status == (
            BookingStatus.CANCELLED.value
        )
        assert (await fetch_schedule(factory, tid, old_sid)).booked_count == 0
        assert (await fetch_schedule(factory, tid, target)).booked_count == (
            1 if reschedule_won else 0
        )

        assert ops.count(TransactionType.RESTORE.value) == 1, f"不得双重回补: {ops}"
        assert len(ops) == (3 if reschedule_won else 2), ops
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id],
            schedule_ids=[old_sid, target], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_d10_same_idempotency_key_concurrent_replay(client: AsyncClient, env):
    """D-10 补充：同 Idempotency-Key 并发重放 → 均返回同一结果，1 审计 / 1 新 booking。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid)
    old_sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(8, hour=2),
    )
    target = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(8, hour=6),
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=old_sid, student_id=ids["student_id"],
    )
    key = f"f65-{uuid4().hex}"
    try:
        token = await login(client, SEED_STUDENT)
        first, second = await _gather(
            _reschedule(client, token, booking_id, target, key),
            _reschedule(client, token, booking_id, target, key),
        )
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        first_id = first.json()["data"]["booking"]["id"]
        second_id = second.json()["data"]["booking"]["id"]
        assert first_id == second_id

        assert await _audit_count(factory, tid, booking_id) == 1
        assert await _booking_count(factory, tid, target) == 1
    finally:
        await cleanup(
            factory, tid, booking_ids=[booking_id],
            schedule_ids=[old_sid, target], course_ids=[course_id],
        )


# ============================================================
# D-6：改期 vs 排期取消（T6.5.11 锁硬化）
# ============================================================


async def _cancel_schedule(client: AsyncClient, admin_token: str, schedule_id: int):
    return await client.post(
        f"{BASE}/schedules/{schedule_id}/cancel",
        json={"cancel_reason": "F6.5 D-6 并发取消"},
        headers=auth_headers(admin_token),
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


@pytest.mark.asyncio
async def test_d6_reschedule_vs_schedule_cancel_no_double_restore(client: AsyncClient, env):
    """D-6：改期 S→T 与取消 S 并发 → 仅一次回补，不出现双重回补。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid, name="F6.5 D6 回补")
    src = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(9, hour=2),
    )
    dst = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(9, hour=6),
    )
    card_id = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5, used_credits=1,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=src, student_id=ids["student_id"],
        membership_card_id=card_id,
    )
    try:
        student_token = await login(client, SEED_STUDENT)
        admin_token = await login(client, SUPER_ADMIN)

        moved, cancelled = await _gather(
            _reschedule(client, student_token, booking_id, dst),
            _cancel_schedule(client, admin_token, src),
        )

        assert cancelled.status_code == 200, cancelled.text
        assert (await fetch_schedule(factory, tid, src)).status == ScheduleStatus.CANCELLED.value
        assert await _active_booking_count(factory, tid, src) == 0

        txns = await _txns(factory, tid, card_id)
        restores = [t for t in txns if t[0] == TransactionType.RESTORE.value]
        consumes = [t for t in txns if t[0] == TransactionType.CONSUME.value]
        assert len(restores) == 1, f"同一 booking 不应重复回补，实际流水 {txns}"

        card = await fetch_card(factory, tid, card_id)
        assert card.used_credits >= 0
        if moved.status_code == 200:
            new_id = moved.json()["data"]["booking"]["id"]
            assert (await fetch_booking(factory, tid, new_id)).status == BookingStatus.BOOKED.value
            assert len(consumes) == 1
            assert card.used_credits == 1
        else:
            assert moved.status_code in (400, 409), moved.text
            assert len(consumes) == 0
            assert card.used_credits == 0
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[src, dst], course_ids=[course_id],
        )


@pytest.mark.asyncio
async def test_d6_reschedule_into_cancelled_schedule_no_orphan(client: AsyncClient, env):
    """D-6：改期 T→S 与取消 S 并发 → S 不得残留进行中预约。"""
    factory, ids = env
    tid = ids["tenant_id"]
    course_id = await create_course(factory, tid, name="F6.5 D6 逃逸")
    src = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(10, hour=2),
    )
    victim = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(10, hour=6),
    )
    card_id = await create_card(
        factory, tid, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5, used_credits=1,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=src, student_id=ids["student_id"],
        membership_card_id=card_id,
    )
    try:
        student_token = await login(client, SEED_STUDENT)
        admin_token = await login(client, SUPER_ADMIN)

        moved, cancelled = await _gather(
            _reschedule(client, student_token, booking_id, victim),
            _cancel_schedule(client, admin_token, victim),
        )

        assert cancelled.status_code == 200, cancelled.text
        assert (await fetch_schedule(factory, tid, victim)).status == ScheduleStatus.CANCELLED.value
        assert await _active_booking_count(factory, tid, victim) == 0, "取消后的排期不得残留 BOOKED 预约"

        txns = await _txns(factory, tid, card_id)
        restores = [t for t in txns if t[0] == TransactionType.RESTORE.value]
        if moved.status_code == 200:
            new_id = moved.json()["data"]["booking"]["id"]
            assert (await fetch_booking(factory, tid, new_id)).status == BookingStatus.CANCELLED.value
            # 回补旧约 + 扣新约 + 取消新约回补 = 2 次回补、1 次扣次
            assert len(restores) == 2, f"预期旧约与新约各回补一次，实际 {txns}"
            assert (await fetch_card(factory, tid, card_id)).used_credits == 0
        else:
            assert moved.status_code in (400, 409), moved.text
            assert len(restores) == 0
            assert (await fetch_card(factory, tid, card_id)).used_credits == 1
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[src, victim], course_ids=[course_id],
        )

