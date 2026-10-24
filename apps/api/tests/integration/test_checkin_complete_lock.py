"""
F2.3 签到/完成加行锁 - 集成测试

验证目标（对应 Feature 2.3 Acceptance Criteria）：
- AC-1：并发签到只成一个（一个 200，一个 400"无法签到"）
- AC-2：并发完成只成一个（一个 200，一个 400"无法完成"）
- AC-3：正常单签到成功（BOOKED → CHECKED_IN，checked_in_at 非空）
- AC-4：正常单完成成功（BOOKED → COMPLETED）
- AC-5：已签到再签到失败（400"无法签到"）
- AC-6：已完成再完成失败（400"无法完成"）

并发原理：
  live_server 是真实 Uvicorn 进程（独立线程 + 独立事件循环），FastAPI 在 DB IO `await`
  时切换协程；两个并发 HTTP 请求的 `SELECT ... FOR UPDATE` 会在 PostgreSQL 层面争抢行锁：
  第一个拿到锁 → 写 → commit 释放；第二个拿到锁后重新读 status → 业务异常拒绝。
  修复前（无锁）必能复现双签到；修复后（FOR UPDATE）必序列化为"一成一败"。

事件循环隔离设计（借鉴 F2.2）：
  - `lock_data`（session-scoped）在 session loop 内搭建共享 course+schedule 后即 dispose
    engine，只返回纯数据 dict（不含 engine/session_factory），避免跨 loop 残留。
  - `local_db`（function-scoped）为每个用例创建独立 engine + session_factory，绑定当前
    function loop，供 helper 做 setup/assert/cleanup。
  - HTTP 请求经 `client` fixture 到 live_server，由 live_server 自己的 loop + engine 处理；
    PG 行锁在数据库层面跨连接生效，与测试进程的 helper 不互相干扰。

前置条件：
  - 种子数据已由 conftest.seed_test_database 初始化
    （super_admin=13800000001 / teacher=13800138001 / student=13900139001，密码 Test@123456）
  - Redis 可用（RBAC 装饰器缓存）
  - PostgreSQL 支持 SELECT ... FOR UPDATE

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_checkin_complete_lock.py -v
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import Booking, BookingSource, BookingStatus
from app.modules.course.models import Course
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.tenant.models import Tenant
from app.modules.user.models import User

TENANT_HEADERS = {"x-tenant-slug": "dance-school"}
SUPER_ADMIN = {"phone": "13800000001", "password": "Test@123456"}  # super_admin（持 booking:manage）
SEED_STUDENT = {"phone": "13900139001", "password": "Test@123456"}  # 李同学（booking.student_id 来源）
SEED_TEACHER = {"phone": "13800138001", "password": "Test@123456"}  # 张老师（schedule.teacher_id 来源）

BASE = "/api/v1"


async def _login(client: AsyncClient, account: dict) -> str:
    resp = await client.post(
        f"{BASE}/auth/login",
        json={"tenant_slug": "dance-school", **account},
    )
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"登录业务失败: {body}"
    return body["data"]["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **TENANT_HEADERS}


@pytest.fixture(scope="session")
async def lock_data(live_server):
    """搭建共享数据（session 级）：1 课程 + 1 排期，返回纯数据 dict。

    engine 在本 fixture 内创建并 dispose，不向外暴露——避免 session loop 的 engine
    被后续 function-scoped 用例跨 loop 复用（asyncpg "attached to a different loop"）。
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_size=3, max_overflow=5, pool_pre_ping=True
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    course_ids: list[int] = []
    schedule_ids: list[int] = []
    tenant_id: int
    student_id: int
    teacher_id: int

    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == "dance-school"))
        ).scalar_one()
        tenant_id = tenant.id
        student_id = (
            await session.execute(select(User).where(User.phone == SEED_STUDENT["phone"]))
        ).scalar_one().id
        teacher_id = (
            await session.execute(select(User).where(User.phone == SEED_TEACHER["phone"]))
        ).scalar_one().id

        set_tenant_id(tenant_id)
        course = Course(
            tenant_id=tenant_id,
            name=f"加锁测试课程{uuid4().hex[:6]}",
            duration_minutes=60,
        )
        session.add(course)
        await session.flush()
        course_ids.append(course.id)

        start = datetime.now(UTC) + timedelta(days=3)
        schedule = CourseSchedule(
            tenant_id=tenant_id,
            course_id=course.id,
            teacher_id=teacher_id,
            start_at=start,
            end_at=start + timedelta(hours=1),
            capacity=10,
            status=ScheduleStatus.NORMAL.value,
        )
        session.add(schedule)
        await session.flush()
        schedule_ids.append(schedule.id)
        await session.commit()

    data = {
        "tenant_id": tenant_id,
        "student_id": student_id,
        "schedule_id": schedule_ids[0],
        "course_ids": course_ids,
        "schedule_ids": schedule_ids,
    }
    yield data

    # 清理共享 course/schedule（在 session loop 内，与创建同 loop）
    async with session_factory() as session:
        set_tenant_id(data["tenant_id"])
        await session.execute(
            delete(CourseSchedule).where(CourseSchedule.id.in_(data["schedule_ids"]))
        )
        await session.execute(delete(Course).where(Course.id.in_(data["course_ids"])))
        await session.commit()
    await engine.dispose()


@pytest.fixture(scope="function")
async def local_db():
    """function-scoped engine + session_factory，绑定当前用例事件循环。

    供 helper 做 booking 的 setup/assert/cleanup。用例结束后 dispose，无跨 loop 残留。
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_size=2, max_overflow=3, pool_pre_ping=True
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    yield session_factory
    await engine.dispose()


async def _create_booking(sf, data: dict, status: int = BookingStatus.BOOKED.value) -> int:
    """直接落库一个指定状态的 booking，返回 id（调用方负责清理）"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        booking = Booking(
            tenant_id=data["tenant_id"],
            schedule_id=data["schedule_id"],
            student_id=data["student_id"],
            status=status,
            source=BookingSource.SELF.value,
        )
        session.add(booking)
        await session.flush()
        booking_id = booking.id
        await session.commit()
    return booking_id


async def _get_booking_field(sf, data: dict, booking_id: int, field):
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        result = await session.execute(select(field).where(Booking.id == booking_id))
        return result.scalar_one()


async def _cleanup_booking(sf, data: dict, booking_id: int) -> None:
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        await session.execute(delete(Booking).where(Booking.id == booking_id))
        await session.commit()


@pytest.mark.asyncio
class TestCheckInCompleteLock:
    """F2.3 签到/完成加行锁"""

    async def test_single_check_in_ok(self, client: AsyncClient, lock_data, local_db):
        """AC-3：正常单签到 BOOKED → CHECKED_IN"""
        booking_id = await _create_booking(local_db, lock_data, BookingStatus.BOOKED.value)
        try:
            token = await _login(client, SUPER_ADMIN)
            resp = await client.post(
                f"{BASE}/bookings/{booking_id}/check-in", headers=_headers(token)
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["code"] == 0
            assert body["data"]["status"] == BookingStatus.CHECKED_IN.value
            assert await _get_booking_field(
                local_db, lock_data, booking_id, Booking.status
            ) == BookingStatus.CHECKED_IN.value
            checked_in_at = await _get_booking_field(
                local_db, lock_data, booking_id, Booking.checked_in_at
            )
            assert checked_in_at is not None
        finally:
            await _cleanup_booking(local_db, lock_data, booking_id)

    async def test_single_complete_ok(self, client: AsyncClient, lock_data, local_db):
        """AC-4：正常单完成 BOOKED → COMPLETED"""
        booking_id = await _create_booking(local_db, lock_data, BookingStatus.BOOKED.value)
        try:
            token = await _login(client, SUPER_ADMIN)
            resp = await client.post(
                f"{BASE}/bookings/{booking_id}/complete", headers=_headers(token)
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["code"] == 0
            assert body["data"]["status"] == BookingStatus.COMPLETED.value
            assert await _get_booking_field(
                local_db, lock_data, booking_id, Booking.status
            ) == BookingStatus.COMPLETED.value
        finally:
            await _cleanup_booking(local_db, lock_data, booking_id)

    async def test_concurrent_check_in_only_one_succeeds(
        self, client: AsyncClient, lock_data, local_db
    ):
        """AC-1：并发签到只成一个（FOR UPDATE 序列化）

        修复前：两个请求都读到 BOOKED，都签到成功（双签到）。
        修复后：第一个拿锁签到成功，第二个拿锁后读到 CHECKED_IN → 400"无法签到"。
        """
        booking_id = await _create_booking(local_db, lock_data, BookingStatus.BOOKED.value)
        try:
            token = await _login(client, SUPER_ADMIN)
            h = _headers(token)

            # 同时发起两个签到请求（httpx AsyncClient 支持连接池并发）
            r1, r2 = await asyncio.gather(
                client.post(f"{BASE}/bookings/{booking_id}/check-in", headers=h),
                client.post(f"{BASE}/bookings/{booking_id}/check-in", headers=h),
            )

            codes = sorted([r1.status_code, r2.status_code])
            assert codes == [200, 400], (
                f"并发签到应一成一败（200/400），实际 {codes}; r1={r1.text} r2={r2.text}"
            )

            failed = r1 if r1.status_code == 400 else r2
            fbody = failed.json()
            assert fbody["code"] == 400
            assert "无法签到" in fbody["msg"], f"失败 msg 应含'无法签到'，实际: {fbody['msg']}"
            assert "Traceback" not in fbody["msg"]

            assert await _get_booking_field(
                local_db, lock_data, booking_id, Booking.status
            ) == BookingStatus.CHECKED_IN.value
        finally:
            await _cleanup_booking(local_db, lock_data, booking_id)

    async def test_concurrent_complete_only_one_succeeds(
        self, client: AsyncClient, lock_data, local_db
    ):
        """AC-2：并发完成只成一个（FOR UPDATE 序列化）"""
        booking_id = await _create_booking(local_db, lock_data, BookingStatus.BOOKED.value)
        try:
            token = await _login(client, SUPER_ADMIN)
            h = _headers(token)

            r1, r2 = await asyncio.gather(
                client.post(f"{BASE}/bookings/{booking_id}/complete", headers=h),
                client.post(f"{BASE}/bookings/{booking_id}/complete", headers=h),
            )

            codes = sorted([r1.status_code, r2.status_code])
            assert codes == [200, 400], (
                f"并发完成应一成一败（200/400），实际 {codes}; r1={r1.text} r2={r2.text}"
            )

            failed = r1 if r1.status_code == 400 else r2
            fbody = failed.json()
            assert fbody["code"] == 400
            assert "无法完成" in fbody["msg"], f"失败 msg 应含'无法完成'，实际: {fbody['msg']}"

            assert await _get_booking_field(
                local_db, lock_data, booking_id, Booking.status
            ) == BookingStatus.COMPLETED.value
        finally:
            await _cleanup_booking(local_db, lock_data, booking_id)

    async def test_check_in_already_checked_in_fails(
        self, client: AsyncClient, lock_data, local_db
    ):
        """AC-5：已 CHECKED_IN 再签到 → 400"无法签到" """
        booking_id = await _create_booking(
            local_db, lock_data, BookingStatus.CHECKED_IN.value
        )
        try:
            token = await _login(client, SUPER_ADMIN)
            resp = await client.post(
                f"{BASE}/bookings/{booking_id}/check-in", headers=_headers(token)
            )
            assert resp.status_code == 400, resp.text
            body = resp.json()
            assert body["code"] == 400
            assert "无法签到" in body["msg"]
            assert await _get_booking_field(
                local_db, lock_data, booking_id, Booking.status
            ) == BookingStatus.CHECKED_IN.value
        finally:
            await _cleanup_booking(local_db, lock_data, booking_id)

    async def test_complete_already_completed_fails(
        self, client: AsyncClient, lock_data, local_db
    ):
        """AC-6：已 COMPLETED 再完成 → 400"无法完成" """
        booking_id = await _create_booking(
            local_db, lock_data, BookingStatus.COMPLETED.value
        )
        try:
            token = await _login(client, SUPER_ADMIN)
            resp = await client.post(
                f"{BASE}/bookings/{booking_id}/complete", headers=_headers(token)
            )
            assert resp.status_code == 400, resp.text
            body = resp.json()
            assert body["code"] == 400
            assert "无法完成" in body["msg"]
            assert await _get_booking_field(
                local_db, lock_data, booking_id, Booking.status
            ) == BookingStatus.COMPLETED.value
        finally:
            await _cleanup_booking(local_db, lock_data, booking_id)

    async def test_complete_from_checked_in_ok(self, client: AsyncClient, lock_data, local_db):
        """补充：CHECKED_IN → COMPLETED 也应成功（complete 接受 BOOKED|CHECKED_IN）"""
        booking_id = await _create_booking(
            local_db, lock_data, BookingStatus.CHECKED_IN.value
        )
        try:
            token = await _login(client, SUPER_ADMIN)
            resp = await client.post(
                f"{BASE}/bookings/{booking_id}/complete", headers=_headers(token)
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["data"]["status"] == BookingStatus.COMPLETED.value
            assert await _get_booking_field(
                local_db, lock_data, booking_id, Booking.status
            ) == BookingStatus.COMPLETED.value
        finally:
            await _cleanup_booking(local_db, lock_data, booking_id)

    async def test_check_in_cancelled_fails(self, client: AsyncClient, lock_data, local_db):
        """补充：CANCELLED 预约签到 → 400"无法签到"（状态校验覆盖）"""
        booking_id = await _create_booking(
            local_db, lock_data, BookingStatus.CANCELLED.value
        )
        try:
            token = await _login(client, SUPER_ADMIN)
            resp = await client.post(
                f"{BASE}/bookings/{booking_id}/check-in", headers=_headers(token)
            )
            assert resp.status_code == 400
            assert "无法签到" in resp.json()["msg"]
        finally:
            await _cleanup_booking(local_db, lock_data, booking_id)

    async def test_check_in_nonexistent_returns_404(self, client: AsyncClient, lock_data):
        """补充：不存在的 booking 签到 → 404（不泄露存在性，含租户过滤）"""
        token = await _login(client, SUPER_ADMIN)
        resp = await client.post(
            f"{BASE}/bookings/999999999/check-in", headers=_headers(token)
        )
        assert resp.status_code == 404
        assert "不存在" in resp.json()["msg"]
