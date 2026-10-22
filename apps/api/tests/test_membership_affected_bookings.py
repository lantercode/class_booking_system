"""F6.7 受影响预约查询：单元（Service 口径/归属）+ 集成（HTTP 契约）+ 并发专项。

验收映射：acceptance.md B-1..B-12（Service 层，db_factory 直造数据）、
C-1..C-10（HTTP 契约）、C-11/C-12（作废/冻结 vs 改派竞态，账务守恒断言）、
E-1..E-4（RBAC 矩阵）。

偏离说明：acceptance C-9 写「page_size=0/101 → 400」，但项目未覆盖 FastAPI
内置 RequestValidationError handler（middleware/error_handler.py:82 注释），
Query 校验失败实际返回 422；本文件按真实行为断言 422（既有测试同约定，
见 test_tenant_update.py）。
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select

from app.core.exceptions import PermissionException
from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import BookingStatus
from app.modules.booking.service import BookingService
from app.modules.membership.models import (
    CardStatus,
    CardType,
    MembershipCardTransaction,
    TransactionType,
)
from app.modules.user.models import User
from tests.membership_support import (
    BASE,
    SEED_STUDENT,
    SEED_TEACHER,
    SUPER_ADMIN,
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
    future_start,
    get_seed_ids,
    login,
)
from tests.membership_support import headers as auth_headers

AFFECTED = f"{BASE}/membership/cards"
TIMEOUT = 15


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        yield factory, ids


def _msg(resp) -> str:
    body = resp.json()
    return body.get("msg") or body.get("detail") or ""


def _data(resp) -> dict:
    return resp.json()["data"]


async def _gather(*coros):
    return await asyncio.wait_for(asyncio.gather(*coros), timeout=TIMEOUT)


async def _admin_user_id(factory, tenant_id: int) -> int:
    """种子 super_admin 的 user_id（B 级归属用例的请求者）。"""
    async with factory() as session:
        set_tenant_id(tenant_id)
        return (
            await session.execute(select(User).where(User.phone == SUPER_ADMIN["phone"]))
        ).scalar_one().id


async def _svc_affected(
    factory,
    tenant_id: int,
    card_id: int,
    requester_user_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
):
    """B 级：直连 Service 查询受影响预约（只读，会话随取随还）。"""
    async with factory() as session:
        set_tenant_id(tenant_id)
        return await BookingService().get_affected_bookings_by_card(
            session,
            card_id=card_id,
            tenant_id=tenant_id,
            requester_user_id=requester_user_id,
            page=page,
            page_size=page_size,
        )


async def _http_affected(client: AsyncClient, token: str, card_id: int, **params):
    return await client.get(
        f"{AFFECTED}/{card_id}/affected-bookings",
        params=params or None,
        headers=auth_headers(token),
    )


async def _txns(factory, tenant_id: int, card_id: int) -> list[str]:
    async with factory() as session:
        set_tenant_id(tenant_id)
        rows = (
            await session.execute(
                select(MembershipCardTransaction).where(
                    MembershipCardTransaction.card_id == card_id
                )
            )
        ).scalars()
        return [row.operation_type for row in rows]


async def _fresh_student(client: AsyncClient, factory, tenant_id: int):
    student = await create_student(factory, tenant_id)
    token = await login(client, {"phone": student["phone"], "password": student["password"]})
    return student, token


# ============================================================
# B 级：Service 口径与归属（B-1 ~ B-12）
# ============================================================


@pytest.mark.asyncio
async def test_b1_b7_booked_future_counted_and_owner_allowed(client: AsyncClient, env):
    """B-1/B-7：BOOKED + 未来 start_at 计入；student 查本人卡放行，字段齐全。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid, name="F6.7口径课B1")
    sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=10),
    )
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=sid, student_id=student["user_id"],
        membership_card_id=card_id,
    )
    try:
        result = await _svc_affected(factory, tid, card_id, student["user_id"])
        assert result.card_id == card_id
        assert result.card_status == CardStatus.ACTIVE.value
        assert result.total == 1
        assert len(result.items) == 1
        item = result.items[0]
        assert item.booking_id == booking_id
        assert item.schedule_id == sid
        assert item.status == BookingStatus.BOOKED.value
        assert item.course_name == "F6.7口径课B1"
        assert item.start_at is not None and item.end_at is not None
        assert item.teacher_name is not None
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[sid], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_b2_checked_in_future_counted(client: AsyncClient, env):
    """B-2：CHECKED_IN + 未来 start_at 计入（夹具直改 status=3）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid)
    sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=12),
    )
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=sid, student_id=student["user_id"],
        membership_card_id=card_id, status=BookingStatus.CHECKED_IN.value,
    )
    try:
        result = await _svc_affected(factory, tid, card_id, student["user_id"])
        assert result.total == 1
        assert result.items[0].status == BookingStatus.CHECKED_IN.value
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[sid], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_b3_terminal_statuses_not_counted(client: AsyncClient, env):
    """B-3：CANCELLED / COMPLETED / NO_SHOW + 未来 start_at 均不计入。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid)
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    sids, bids = [], []
    for i, st in enumerate(
        [BookingStatus.CANCELLED.value, BookingStatus.COMPLETED.value, BookingStatus.NO_SHOW.value]
    ):
        sid = await create_schedule(
            factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
            start_at=future_start(3 + i, hour=14),
        )
        sids.append(sid)
        bids.append(
            await create_booking(
                factory, tid, schedule_id=sid, student_id=student["user_id"],
                membership_card_id=card_id, status=st,
            )
        )
    try:
        result = await _svc_affected(factory, tid, card_id, student["user_id"])
        assert result.total == 0
        assert result.items == []
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=bids,
            schedule_ids=sids, course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_b4_started_schedule_not_counted(client: AsyncClient, env):
    """B-4：start_at <= now（过去时刻）不计入（R-1 严格大于）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid)
    past_start = datetime.now(UTC) - timedelta(hours=2)
    sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=past_start,
    )
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=sid, student_id=student["user_id"],
        membership_card_id=card_id,
    )
    try:
        result = await _svc_affected(factory, tid, card_id, student["user_id"])
        assert result.total == 0
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[sid], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_b5_later_today_counted(client: AsyncClient, env):
    """B-5：start_at 为当天稍晚未来时刻计入（R-3）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid)
    later_today = datetime.now(UTC) + timedelta(hours=2)
    sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=later_today,
    )
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=sid, student_id=student["user_id"],
        membership_card_id=card_id,
    )
    try:
        result = await _svc_affected(factory, tid, card_id, student["user_id"])
        assert result.total == 1
        assert result.items[0].booking_id == booking_id
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[sid], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_b6_other_card_and_no_card_not_counted(client: AsyncClient, env):
    """B-6：他卡预约与无卡预约（membership_card_id IS NULL）不计入。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid)
    card_target = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    card_other = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    sid_a = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=10),
    )
    sid_b = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(4, hour=10),
    )
    bid_other = await create_booking(
        factory, tid, schedule_id=sid_a, student_id=student["user_id"],
        membership_card_id=card_other,
    )
    bid_none = await create_booking(
        factory, tid, schedule_id=sid_b, student_id=student["user_id"],
        membership_card_id=None,
    )
    try:
        result = await _svc_affected(factory, tid, card_target, student["user_id"])
        assert result.total == 0
    finally:
        await cleanup(
            factory, tid, card_ids=[card_target, card_other],
            booking_ids=[bid_other, bid_none],
            schedule_ids=[sid_a, sid_b], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_b8_student_other_card_forbidden(client: AsyncClient, env):
    """B-8：student 查同租户他人卡 → PermissionException（403）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    owner, _ = await _fresh_student(client, factory, tid)
    other, _ = await _fresh_student(client, factory, tid)
    card_id = await create_card(
        factory, tid, owner["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        with pytest.raises(PermissionException) as exc_info:
            await _svc_affected(factory, tid, card_id, other["user_id"])
        assert exc_info.value.code == 403
        assert "无权查看该卡的受影响预约" in exc_info.value.msg
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id],
            student_ids=[owner["user_id"], other["user_id"]],
        )


@pytest.mark.asyncio
async def test_b9_admin_can_query_any_card(client: AsyncClient, env):
    """B-9：admin/super_admin 查本租户任意卡（含他人卡）放行。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    admin_id = await _admin_user_id(factory, tid)
    course_id = await create_course(factory, tid)
    sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=10),
    )
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=sid, student_id=student["user_id"],
        membership_card_id=card_id,
    )
    try:
        result = await _svc_affected(factory, tid, card_id, admin_id)
        assert result.total == 1
        assert result.items[0].booking_id == booking_id
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[sid], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_b10_card_not_found_404(client: AsyncClient, env):
    """B-10：卡不存在 → 404「会员卡不存在」。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await _svc_affected(factory, tid, 987654321, student["user_id"])
        assert exc_info.value.status_code == 404
        assert "会员卡不存在" in str(exc_info.value.detail)
    finally:
        await cleanup(factory, tid, student_ids=[student["user_id"]])


@pytest.mark.asyncio
async def test_b11_ordering_stable(client: AsyncClient, env):
    """B-11：多预约按 start_at ASC, id ASC 稳定排序（乱序创建）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid)
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    # 乱序创建：day5 → day3 → day4
    sids, bids = [], []
    for days in (5, 3, 4):
        sid = await create_schedule(
            factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
            start_at=future_start(days, hour=10),
        )
        sids.append(sid)
        bids.append(
            await create_booking(
                factory, tid, schedule_id=sid, student_id=student["user_id"],
                membership_card_id=card_id,
            )
        )
    try:
        result = await _svc_affected(factory, tid, card_id, student["user_id"])
        assert result.total == 3
        got = [item.booking_id for item in result.items]
        assert got == [bids[1], bids[2], bids[0]], "应按 start_at ASC（day3, day4, day5）"
        starts = [item.start_at for item in result.items]
        assert starts == sorted(starts)
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=bids,
            schedule_ids=sids, course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_b12_pagination_total_and_slice(client: AsyncClient, env):
    """B-12：total 跨页正确、items 切片正确。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid)
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    sids, bids = [], []
    for days in (3, 4, 5):
        sid = await create_schedule(
            factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
            start_at=future_start(days, hour=10),
        )
        sids.append(sid)
        bids.append(
            await create_booking(
                factory, tid, schedule_id=sid, student_id=student["user_id"],
                membership_card_id=card_id,
            )
        )
    try:
        page1 = await _svc_affected(factory, tid, card_id, student["user_id"], page=1, page_size=2)
        assert page1.total == 3
        assert [i.booking_id for i in page1.items] == [bids[0], bids[1]]
        assert page1.page == 1 and page1.page_size == 2

        page2 = await _svc_affected(factory, tid, card_id, student["user_id"], page=2, page_size=2)
        assert page2.total == 3
        assert [i.booking_id for i in page2.items] == [bids[2]]
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=bids,
            schedule_ids=sids, course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


# ============================================================
# C 级：HTTP 契约（C-1 ~ C-10）与权限矩阵（E-1 ~ E-4）
# ============================================================


@pytest.mark.asyncio
async def test_c1_admin_total_excludes_terminal_statuses(client: AsyncClient, env):
    """C-1/E-1：admin 查本租户卡，BOOKED×2 未来 + COMPLETED×1 + CANCELLED×1 → total=2。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    admin_token = await login(client, SUPER_ADMIN)
    course_id = await create_course(factory, tid)
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=10,
    )
    sids, bids = [], []
    for i, st in enumerate(
        [BookingStatus.BOOKED.value, BookingStatus.BOOKED.value,
         BookingStatus.COMPLETED.value, BookingStatus.CANCELLED.value]
    ):
        sid = await create_schedule(
            factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
            start_at=future_start(3 + i, hour=10),
        )
        sids.append(sid)
        bids.append(
            await create_booking(
                factory, tid, schedule_id=sid, student_id=student["user_id"],
                membership_card_id=card_id, status=st,
            )
        )
    try:
        resp = await _http_affected(client, admin_token, card_id)
        assert resp.status_code == 200, resp.text
        data = _data(resp)
        assert data["card_id"] == card_id
        assert data["card_status"] == CardStatus.ACTIVE.value
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert all(item["status"] == BookingStatus.BOOKED.value for item in data["items"])
        assert {item["booking_id"] for item in data["items"]} == {bids[0], bids[1]}
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=bids,
            schedule_ids=sids, course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_c2_student_own_card_fields(client: AsyncClient, env):
    """C-2/E-2：student 查本人卡 → 200，字段齐全。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid, name="F6.7集成课C2")
    sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=10),
    )
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=sid, student_id=student["user_id"],
        membership_card_id=card_id,
    )
    try:
        resp = await _http_affected(client, token, card_id)
        assert resp.status_code == 200, resp.text
        data = _data(resp)
        for field in ("card_id", "card_status", "total", "page", "page_size", "items"):
            assert field in data
        assert data["total"] == 1
        item = data["items"][0]
        assert item["booking_id"] == booking_id
        assert item["schedule_id"] == sid
        assert item["course_name"] == "F6.7集成课C2"
        assert "start_at" in item and "end_at" in item
        assert "student_phone" not in item and "student_nickname" not in item
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[sid], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_c3_student_other_card_403(client: AsyncClient, env):
    """C-3/E-2：student 查同租户他人卡 → 403 信封，无 traceback。"""
    factory, ids = env
    tid = ids["tenant_id"]
    owner, _ = await _fresh_student(client, factory, tid)
    other, other_token = await _fresh_student(client, factory, tid)
    card_id = await create_card(
        factory, tid, owner["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        resp = await _http_affected(client, other_token, card_id)
        assert resp.status_code == 403, resp.text
        body = resp.json()
        assert body["code"] == 403
        assert "无权查看该卡的受影响预约" in _msg(resp)
        for leaked in ("Traceback", "SELECT", "postgresql", ".py"):
            assert leaked not in resp.text
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id],
            student_ids=[owner["user_id"], other["user_id"]],
        )


@pytest.mark.asyncio
async def test_e3_teacher_non_owner_card_403(client: AsyncClient, env):
    """E-3：teacher 查非本人卡 → 403（视同非本人）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    owner, _ = await _fresh_student(client, factory, tid)
    teacher_token = await login(client, SEED_TEACHER)
    card_id = await create_card(
        factory, tid, owner["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        resp = await _http_affected(client, teacher_token, card_id)
        assert resp.status_code == 403, resp.text
    finally:
        await cleanup(factory, tid, card_ids=[card_id], student_ids=[owner["user_id"]])


@pytest.mark.asyncio
async def test_c4_cross_tenant_card_404(client: AsyncClient, env):
    """C-4/E-1：其他租户的卡 id + 本租户 token/slug → 404（不泄露存在性）。"""
    factory, ids = env
    from uuid import uuid4

    from app.modules.tenant.models import Tenant, TenantStatus

    async with factory() as session:
        tenant_b = Tenant(
            name=f"F6.7隔离租户{uuid4().hex[:8]}",
            slug=f"f67-{uuid4().hex[:12]}",
            status=TenantStatus.ACTIVE.value,
        )
        session.add(tenant_b)
        await session.flush()
        tenant_b_id = tenant_b.id
        await session.commit()

    card_b = await create_card(
        factory, tenant_b_id, ids["student_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    try:
        token = await login(client, SEED_STUDENT)
        resp = await _http_affected(client, token, card_b)
        assert resp.status_code == 404, resp.text
        assert str(card_b) not in resp.text
        for leaked in ("Traceback", "SELECT", "postgresql"):
            assert leaked not in resp.text
    finally:
        await cleanup(factory, tenant_b_id, card_ids=[card_b])
        async with factory() as session:
            from sqlalchemy import delete

            await session.execute(delete(Tenant).where(Tenant.id == tenant_b_id))
            await session.commit()


@pytest.mark.asyncio
async def test_c5_unauthenticated_401(client: AsyncClient, env):
    """C-5/E-4：未认证 → 401。"""
    resp = await client.get(f"{AFFECTED}/1/affected-bookings", headers=TENANT_HEADERS)
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_c6_card_not_found_404(client: AsyncClient, env):
    """C-6：本租户内卡不存在 → 404「会员卡不存在」。"""
    token = await login(client, SUPER_ADMIN)
    resp = await _http_affected(client, token, 987654321)
    assert resp.status_code == 404, resp.text
    assert "会员卡不存在" in _msg(resp)
    for leaked in ("Traceback", "SELECT", "postgresql", ".py"):
        assert leaked not in resp.text


@pytest.mark.asyncio
async def test_c7_checked_in_future_in_items(client: AsyncClient, env):
    """C-7：CHECKED_IN + 未来排期计入 items 且 status=3。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid)
    sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=10),
    )
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=sid, student_id=student["user_id"],
        membership_card_id=card_id, status=BookingStatus.CHECKED_IN.value,
    )
    try:
        resp = await _http_affected(client, token, card_id)
        assert resp.status_code == 200, resp.text
        data = _data(resp)
        assert data["total"] == 1
        assert data["items"][0]["booking_id"] == booking_id
        assert data["items"][0]["status"] == BookingStatus.CHECKED_IN.value
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[sid], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_c8_past_schedule_not_counted(client: AsyncClient, env):
    """C-8：排期 start_at 已过（昨天）+ BOOKED → 不计入。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid)
    sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=datetime.now(UTC) - timedelta(days=1),
    )
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=sid, student_id=student["user_id"],
        membership_card_id=card_id,
    )
    try:
        resp = await _http_affected(client, token, card_id)
        assert resp.status_code == 200, resp.text
        assert _data(resp)["total"] == 0
        assert _data(resp)["items"] == []
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[sid], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_c9_pagination_and_invalid_params(client: AsyncClient, env):
    """C-9：page=2&page_size=1（total=2）返回第 2 条；page_size=0/101 → 参数拒绝。

    注：acceptance 写 400，项目实际由 FastAPI 内置 handler 返回 422
    （middleware/error_handler.py 明确不覆盖 RequestValidationError）。
    """
    factory, ids = env
    tid = ids["tenant_id"]
    student, token = await _fresh_student(client, factory, tid)
    course_id = await create_course(factory, tid)
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    sids, bids = [], []
    for days in (3, 4):
        sid = await create_schedule(
            factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
            start_at=future_start(days, hour=10),
        )
        sids.append(sid)
        bids.append(
            await create_booking(
                factory, tid, schedule_id=sid, student_id=student["user_id"],
                membership_card_id=card_id,
            )
        )
    try:
        resp = await _http_affected(client, token, card_id, page=2, page_size=1)
        assert resp.status_code == 200, resp.text
        data = _data(resp)
        assert data["total"] == 2
        assert data["page"] == 2 and data["page_size"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["booking_id"] == bids[1]

        resp_zero = await _http_affected(client, token, card_id, page_size=0)
        assert resp_zero.status_code == 422, resp_zero.text
        resp_over = await _http_affected(client, token, card_id, page_size=101)
        assert resp_over.status_code == 422, resp_over.text
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=bids,
            schedule_ids=sids, course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_c10_read_only_after_freeze(client: AsyncClient, env):
    """C-10：冻结后再查 → 仍返回相同 N（只读、与卡状态无关，R-8），card_status=3。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, _ = await _fresh_student(client, factory, tid)
    admin_token = await login(client, SUPER_ADMIN)
    course_id = await create_course(factory, tid)
    sid = await create_schedule(
        factory, tid, course_id=course_id, teacher_id=ids["teacher_id"],
        start_at=future_start(3, hour=10),
    )
    card_id = await create_card(
        factory, tid, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=5,
    )
    booking_id = await create_booking(
        factory, tid, schedule_id=sid, student_id=student["user_id"],
        membership_card_id=card_id,
    )
    try:
        before = await _http_affected(client, admin_token, card_id)
        assert before.status_code == 200, before.text
        assert _data(before)["total"] == 1
        assert _data(before)["card_status"] == CardStatus.ACTIVE.value

        freeze = await client.post(
            f"{AFFECTED}/{card_id}/freeze",
            json={"reason": "F6.7只读验证", "freeze_days": 30, "auto_unfreeze": False},
            headers=auth_headers(admin_token),
        )
        assert freeze.status_code == 200, freeze.text

        after = await _http_affected(client, admin_token, card_id)
        assert after.status_code == 200, after.text
        assert _data(after)["total"] == 1
        assert _data(after)["card_status"] == CardStatus.FROZEN.value
        assert _data(after)["items"][0]["booking_id"] == booking_id
    finally:
        await cleanup(
            factory, tid, card_ids=[card_id], booking_ids=[booking_id],
            schedule_ids=[sid], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


# ============================================================
# C 级并发专项：作废/冻结 vs 改派竞态（C-11 / C-12）
# ============================================================


async def _setup_swap_race(client: AsyncClient, factory, tenant_id: int, teacher_id: int):
    """前置：学员 + 卡 C（ACTIVE）+ 卡 D（ACTIVE 可替代）+ 预约 B（BOOKED 未来，用卡 C）。

    预约经真实 API 创建，卡 C 产生 CONSUME 流水（used_credits=1），
    保证改派回补路径（restore_credit 要求 used_credits>0）可真实触达。
    """
    student, token = await _fresh_student(client, factory, tenant_id)
    course_id = await create_course(factory, tenant_id)
    sid = await create_schedule(
        factory, tenant_id, course_id=course_id, teacher_id=teacher_id,
        start_at=future_start(6, hour=10),
    )
    card_c = await create_card(
        factory, tenant_id, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    card_d = await create_card(
        factory, tenant_id, student["user_id"], card_type=CardType.COUNT.value,
        status=CardStatus.ACTIVE.value, total_credits=2,
    )
    created = await client.post(
        f"{BASE}/bookings/",
        json={"schedule_id": sid, "membership_card_id": card_c},
        headers=auth_headers(token),
    )
    assert created.status_code == 201, created.text
    booking_id = created.json()["data"]["id"]
    return student, token, course_id, sid, card_c, card_d, booking_id


def _assert_race_conservation(
    cancel_resp,
    swap_resp,
    booking_card_id: int,
    card_c: int,
    card_d: int,
    c_txns: list[str],
    d_txns: list[str],
) -> str:
    """账务守恒断言：无 500、无死锁、不双扣双补。返回实际路径（swap_ok/swap_fail）。"""
    for resp in (cancel_resp, swap_resp):
        assert resp.status_code != 500, resp.text
    assert cancel_resp.status_code in (200, 400, 409), cancel_resp.text
    assert swap_resp.status_code in (200, 400, 409), swap_resp.text

    c_restores = c_txns.count(TransactionType.RESTORE.value)
    d_consumes = d_txns.count(TransactionType.CONSUME.value)
    assert c_restores <= 1, f"卡 C 回补次数不得重复: {c_txns}"
    assert d_consumes <= 1, f"卡 D 扣次次数不得重复: {d_txns}"

    if swap_resp.status_code == 200:
        assert booking_card_id == card_d
        assert c_restores == 1 and d_consumes == 1, "改派成功必须一补一扣"
        return "swap_ok"
    # 改派失败：预约不得悬空（仍指向原卡 C），且不得出现部分账务
    assert booking_card_id == card_c
    assert c_restores == 0 and d_consumes == 0, "改派失败不得产生任何补/扣流水"
    return "swap_fail"


@pytest.mark.asyncio
async def test_c11_cancel_vs_swap_race(client: AsyncClient, env):
    """C-11：作废 vs 改派竞态——结果可解释 + 账务守恒（不双扣双补、无悬空）。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token, course_id, sid, card_c, card_d, booking_id = await _setup_swap_race(
        client, factory, tid, ids["teacher_id"]
    )
    admin_token = await login(client, SUPER_ADMIN)
    try:
        cancel_resp, swap_resp = await _gather(
            client.post(
                f"{AFFECTED}/{card_c}/cancel",
                json={"reason": "F6.7并发作废"},
                headers=auth_headers(admin_token),
            ),
            client.post(
                f"{BASE}/bookings/{booking_id}/reschedule",
                json={"new_schedule_id": sid, "new_membership_card_id": card_d},
                headers=auth_headers(token),
            ),
        )

        booking = await fetch_booking(factory, tid, booking_id)
        card_c_after = await fetch_card(factory, tid, card_c)
        card_d_after = await fetch_card(factory, tid, card_d)
        c_txns = await _txns(factory, tid, card_c)
        d_txns = await _txns(factory, tid, card_d)

        path = _assert_race_conservation(
            cancel_resp, swap_resp, booking.membership_card_id,
            card_c, card_d, c_txns, d_txns,
        )
        # 余额守恒：两张卡已用次数均 ∈ {0,1,2} 且与流水一致
        assert card_c_after.used_credits in (0, 1, 2)
        assert card_d_after.used_credits in (0, 1, 2)
        assert card_d_after.used_credits == d_txns.count(TransactionType.CONSUME.value)

        if cancel_resp.status_code == 200:
            assert card_c_after.status == CardStatus.CANCELLED.value

        # 改派成功 → 卡 C 不再受影响；失败 → 仍受影响（无论卡 C 是否已作废）
        affected = await _http_affected(client, admin_token, card_c)
        assert affected.status_code == 200, affected.text
        expected_total = 0 if path == "swap_ok" else 1
        assert _data(affected)["total"] == expected_total
    finally:
        await cleanup(
            factory, tid, card_ids=[card_c, card_d],
            schedule_ids=[sid], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )


@pytest.mark.asyncio
async def test_c12_freeze_vs_swap_race(client: AsyncClient, env):
    """C-12：冻结 vs 改派竞态——与 C-11 同构的守恒断言。"""
    factory, ids = env
    tid = ids["tenant_id"]
    student, token, course_id, sid, card_c, card_d, booking_id = await _setup_swap_race(
        client, factory, tid, ids["teacher_id"]
    )
    admin_token = await login(client, SUPER_ADMIN)
    try:
        freeze_resp, swap_resp = await _gather(
            client.post(
                f"{AFFECTED}/{card_c}/freeze",
                json={"reason": "F6.7并发冻结", "freeze_days": 30, "auto_unfreeze": False},
                headers=auth_headers(admin_token),
            ),
            client.post(
                f"{BASE}/bookings/{booking_id}/reschedule",
                json={"new_schedule_id": sid, "new_membership_card_id": card_d},
                headers=auth_headers(token),
            ),
        )

        booking = await fetch_booking(factory, tid, booking_id)
        card_c_after = await fetch_card(factory, tid, card_c)
        card_d_after = await fetch_card(factory, tid, card_d)
        c_txns = await _txns(factory, tid, card_c)
        d_txns = await _txns(factory, tid, card_d)

        path = _assert_race_conservation(
            freeze_resp, swap_resp, booking.membership_card_id,
            card_c, card_d, c_txns, d_txns,
        )
        assert card_d_after.used_credits == d_txns.count(TransactionType.CONSUME.value)

        if freeze_resp.status_code == 200:
            assert card_c_after.status == CardStatus.FROZEN.value

        affected = await _http_affected(client, admin_token, card_c)
        assert affected.status_code == 200, affected.text
        expected_total = 0 if path == "swap_ok" else 1
        assert _data(affected)["total"] == expected_total
    finally:
        await cleanup(
            factory, tid, card_ids=[card_c, card_d],
            schedule_ids=[sid], course_ids=[course_id],
            student_ids=[student["user_id"]],
        )
