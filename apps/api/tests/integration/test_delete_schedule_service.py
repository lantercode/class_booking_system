"""
F2.5 delete_schedule 下沉到 Service - 集成测试

验证目标（对应 Feature 2.5 Acceptance Criteria）：
- AC-1：Service 直调删除已取消排期成功，关联 booking 被级联硬删（DB 断言）
- AC-2：Service 直调删除不存在排期 → NotFoundException（404 "排期不存在"）
- AC-3：Service 直调删除 NORMAL 且 booked_count>0 的排期 → BusinessException(400)，
        schedule 与 booking 在 DB 中均无变更
- AC-4：HTTP admin DELETE /schedules/{id} 成功 → 200 + 信封 msg="排期删除成功"
- AC-5：HTTP 无权限角色（student）DELETE → 403
- AC-6：HTTP 删除不存在排期 → 404 业务错误信封（code=404，msg 含"不存在"）
- AC-7：回归 test_cancel_schedule_rollback / test_checkin_complete_lock /
        test_booking_ownership / test_auth_api

重构性质：
  纯分层重构，行为零变化——原 router 内联逻辑（get_by_id → 存在性判断 →
  NORMAL+booked_count 业务规则 → BookingRepository.delete_by_schedule_id →
  repo.delete(hard_delete=True)）原样下沉到 ScheduleService.delete_schedule。
  本测试同时锁定"下沉前的行为契约"与"下沉后的分层合规"。

事务语义：
  delete_by_schedule_id 只执行 DELETE 不 commit；repo.delete(hard_delete=True,
  auto_commit=True) 在同一 AsyncSession 上统一 commit 两步删除；其内部异常时
  rollback 并 raise。

数据搭建（借鉴 F2.4 fixture 模式）：
  - delete_data（session-scoped）创建 1 共享 course + 解析种子 IDs，
    engine 在 fixture 内 dispose，只返回纯数据 dict。
  - local_db（function-scoped）为每用例创建独立 engine + session_factory。
  - 每用例独立搭建 schedule（+booking），用例结束清理；每用例 schedule_id 不同，
    不触发 uq_bookings_schedule_student_active 冲突，无需临时 student。

前置条件：
  - 种子数据已由 conftest.seed_test_database 初始化
    （super_admin=13800000001 / student=13900139001，密码 Test@123456）
  - Redis 可用（RBAC 装饰器缓存）

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_delete_schedule_service.py -v
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.exceptions import BusinessException, NotFoundException
from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import Booking, BookingSource, BookingStatus
from app.modules.course.models import Course
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.schedule.service import ScheduleService
from app.modules.tenant.models import Tenant
from app.modules.user.models import User

TENANT_HEADERS = {"x-tenant-slug": "dance-school"}
SUPER_ADMIN = {"phone": "13800000001", "password": "Test@123456"}  # super_admin（持 schedule:delete）
SEED_STUDENT = {"phone": "13900139001", "password": "Test@123456"}  # 李同学（仅 booking:view）

BASE = "/api/v1"


# ============================================================
# 公共 helper（登录、HTTP 头）
# ============================================================


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


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="session")
async def delete_data():
    """搭建共享数据（session 级）：1 共享 course + 解析种子 IDs。

    engine 在本 fixture 内创建并 dispose，只返回纯数据 dict——避免 session loop 的
    engine 被后续 function-scoped 用例跨 loop 复用（asyncpg "attached to a different loop"）。
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_size=3, max_overflow=5, pool_pre_ping=True
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    course_ids: list[int] = []

    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == "dance-school"))
        ).scalar_one()
        tenant_id = tenant.id
        student_id = (
            await session.execute(select(User).where(User.phone == SEED_STUDENT["phone"]))
        ).scalar_one().id
        admin_id = (
            await session.execute(select(User).where(User.phone == SUPER_ADMIN["phone"]))
        ).scalar_one().id

        set_tenant_id(tenant_id)
        course = Course(
            tenant_id=tenant_id,
            name=f"删除下沉测试课程{uuid4().hex[:6]}",
            duration_minutes=60,
        )
        session.add(course)
        await session.flush()
        course_ids.append(course.id)
        await session.commit()

    data = {
        "tenant_id": tenant_id,
        "student_id": student_id,
        "admin_id": admin_id,
        "course_ids": course_ids,
    }
    yield data

    # 清理共享 course（用例级 schedule/booking 已由各用例 _cleanup 清理）
    async with session_factory() as session:
        set_tenant_id(data["tenant_id"])
        await session.execute(delete(Course).where(Course.id.in_(data["course_ids"])))
        await session.commit()
    await engine.dispose()


@pytest.fixture(scope="function")
async def local_db():
    """function-scoped engine + session_factory，绑定当前用例事件循环。"""
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_size=2, max_overflow=3, pool_pre_ping=True
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    yield session_factory
    await engine.dispose()


# ============================================================
# Helper：直接落库构造 schedule / booking + 存在性断言 + 清理
# ============================================================


async def _create_schedule(
    sf,
    data: dict,
    *,
    booked_count: int = 0,
    status: int = ScheduleStatus.NORMAL.value,
    capacity: int = 10,
    start_offset_hours: int = 3,
) -> int:
    """直接落库 1 个 schedule，返回 id（调用方负责清理）"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        start = datetime.now(UTC) + timedelta(hours=start_offset_hours)
        schedule = CourseSchedule(
            tenant_id=data["tenant_id"],
            course_id=data["course_ids"][0],
            teacher_id=data["admin_id"],
            start_at=start,
            end_at=start + timedelta(hours=1),
            capacity=capacity,
            booked_count=booked_count,
            status=status,
        )
        session.add(schedule)
        await session.flush()
        schedule_id = schedule.id
        await session.commit()
    return schedule_id


async def _create_booking(
    sf,
    data: dict,
    schedule_id: int,
    *,
    status: int = BookingStatus.BOOKED.value,
) -> int:
    """直接落库 1 个 booking，返回 id（调用方负责清理）"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        booking = Booking(
            tenant_id=data["tenant_id"],
            schedule_id=schedule_id,
            student_id=data["student_id"],
            status=status,
            source=BookingSource.SELF.value,
        )
        session.add(booking)
        await session.flush()
        booking_id = booking.id
        await session.commit()
    return booking_id


async def _exists(sf, data: dict, model, entity_id: int) -> bool:
    """行是否仍存在（独立 session 读取已提交数据）"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        result = await session.execute(select(model.id).where(model.id == entity_id))
        return result.scalar_one_or_none() is not None


async def _cleanup(sf, data: dict, *, schedule_ids=None, booking_ids=None) -> None:
    """清理测试数据：先 booking 后 schedule（bookings.schedule_id 外键 RESTRICT）。"""
    if booking_ids:
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            await session.execute(delete(Booking).where(Booking.id.in_(booking_ids)))
            await session.commit()

    if schedule_ids:
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            await session.execute(
                delete(CourseSchedule).where(CourseSchedule.id.in_(schedule_ids))
            )
            await session.commit()


# ============================================================
# Service 直调路径测试
# ============================================================


@pytest.mark.asyncio
class TestDeleteScheduleService:
    """F2.5 delete_schedule 下沉（Service 直调路径）"""

    async def test_delete_cancelled_schedule_ok_cascades_bookings(
        self, delete_data, local_db
    ):
        """AC-1：删除已取消排期成功，关联 booking 被级联硬删（DB 断言）"""
        data = delete_data
        schedule_id = await _create_schedule(
            local_db, data, status=ScheduleStatus.CANCELLED.value, booked_count=0
        )
        booking_id = await _create_booking(
            local_db,
            data,
            schedule_id,
            status=BookingStatus.CANCELLED.value,
        )
        try:
            async with local_db() as session:
                set_tenant_id(data["tenant_id"])
                service = ScheduleService()
                result = await service.delete_schedule(session, schedule_id)
                assert result == {"schedule_id": schedule_id}

            # DB 断言：schedule 与关联 booking 均被硬删
            assert await _exists(local_db, data, CourseSchedule, schedule_id) is False
            assert await _exists(local_db, data, Booking, booking_id) is False
        finally:
            # 兜底清理（删除成功后通常无残留；失败路径防脏数据）
            await _cleanup(
                local_db,
                data,
                schedule_ids=[schedule_id],
                booking_ids=[booking_id],
            )

    async def test_delete_nonexistent_schedule_raises_not_found(
        self, delete_data, local_db
    ):
        """AC-2：删除不存在排期 → NotFoundException（404 "排期不存在"）"""
        data = delete_data
        async with local_db() as session:
            set_tenant_id(data["tenant_id"])
            service = ScheduleService()
            with pytest.raises(NotFoundException) as exc_info:
                await service.delete_schedule(session, 999999999)
            assert "不存在" in str(exc_info.value)

    async def test_delete_normal_schedule_with_bookings_raises_business_no_change(
        self, delete_data, local_db
    ):
        """AC-3：NORMAL 且 booked_count>0 → BusinessException(400)，DB 无变更"""
        data = delete_data
        schedule_id = await _create_schedule(
            local_db, data, status=ScheduleStatus.NORMAL.value, booked_count=1
        )
        booking_id = await _create_booking(
            local_db, data, schedule_id, status=BookingStatus.BOOKED.value
        )
        try:
            async with local_db() as session:
                set_tenant_id(data["tenant_id"])
                service = ScheduleService()
                with pytest.raises(BusinessException) as exc_info:
                    await service.delete_schedule(session, schedule_id)
                assert exc_info.value.code == 400
                assert "仍有学员预约" in str(exc_info.value)
                assert "先取消排期后再删除" in str(exc_info.value)

            # DB 断言：无任何变更（schedule 与 booking 均仍存在）
            assert await _exists(local_db, data, CourseSchedule, schedule_id) is True
            assert await _exists(local_db, data, Booking, booking_id) is True
        finally:
            await _cleanup(
                local_db,
                data,
                schedule_ids=[schedule_id],
                booking_ids=[booking_id],
            )

    async def test_delete_normal_schedule_without_bookings_ok(
        self, delete_data, local_db
    ):
        """补充：NORMAL 但 booked_count=0 且无 booking 行 → 允许删除"""
        data = delete_data
        schedule_id = await _create_schedule(
            local_db, data, status=ScheduleStatus.NORMAL.value, booked_count=0
        )
        try:
            async with local_db() as session:
                set_tenant_id(data["tenant_id"])
                service = ScheduleService()
                result = await service.delete_schedule(session, schedule_id)
                assert result == {"schedule_id": schedule_id}

            assert await _exists(local_db, data, CourseSchedule, schedule_id) is False
        finally:
            await _cleanup(local_db, data, schedule_ids=[schedule_id])

    async def test_delete_finished_schedule_ok_cascades_bookings(
        self, delete_data, local_db
    ):
        """补充：FINISHED 排期不在拦截分支（仅 NORMAL+booked_count>0 拦截）→ 允许删除，
        关联 booking 一并级联硬删"""
        data = delete_data
        schedule_id = await _create_schedule(
            local_db, data, status=ScheduleStatus.FINISHED.value, booked_count=0
        )
        booking_id = await _create_booking(
            local_db,
            data,
            schedule_id,
            status=BookingStatus.COMPLETED.value,
        )
        try:
            async with local_db() as session:
                set_tenant_id(data["tenant_id"])
                service = ScheduleService()
                result = await service.delete_schedule(session, schedule_id)
                assert result == {"schedule_id": schedule_id}

            assert await _exists(local_db, data, CourseSchedule, schedule_id) is False
            assert await _exists(local_db, data, Booking, booking_id) is False
        finally:
            await _cleanup(
                local_db,
                data,
                schedule_ids=[schedule_id],
                booking_ids=[booking_id],
            )


# ============================================================
# HTTP 端点路径测试（live_server 真实 Uvicorn）
# ============================================================


@pytest.mark.asyncio
class TestDeleteScheduleHTTP:
    """F2.5 delete_schedule 下沉（HTTP 端点路径，端到端契约）"""

    async def test_http_delete_cancelled_schedule_ok(
        self, client: AsyncClient, delete_data, local_db
    ):
        """AC-4：admin DELETE /schedules/{id} → 200 + 信封 + schedule/booking 被硬删"""
        data = delete_data
        schedule_id = await _create_schedule(
            local_db, data, status=ScheduleStatus.CANCELLED.value, booked_count=0
        )
        booking_id = await _create_booking(
            local_db,
            data,
            schedule_id,
            status=BookingStatus.CANCELLED.value,
        )
        try:
            token = await _login(client, SUPER_ADMIN)
            resp = await client.delete(
                f"{BASE}/schedules/{schedule_id}",
                headers=_headers(token),
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["code"] == 0
            assert body["msg"] == "排期删除成功"
            assert "Traceback" not in str(body)

            assert await _exists(local_db, data, CourseSchedule, schedule_id) is False
            assert await _exists(local_db, data, Booking, booking_id) is False
        finally:
            await _cleanup(
                local_db,
                data,
                schedule_ids=[schedule_id],
                booking_ids=[booking_id],
            )

    async def test_http_delete_schedule_forbidden_for_student(
        self, client: AsyncClient, delete_data, local_db
    ):
        """AC-5：student（无 schedule:delete 权限）→ 403，schedule 不被删除"""
        data = delete_data
        schedule_id = await _create_schedule(
            local_db, data, status=ScheduleStatus.CANCELLED.value, booked_count=0
        )
        try:
            token = await _login(client, SEED_STUDENT)
            resp = await client.delete(
                f"{BASE}/schedules/{schedule_id}",
                headers=_headers(token),
            )
            assert resp.status_code == 403, (
                f"学员无 schedule:delete 权限应 403，实际 {resp.status_code}: {resp.text}"
            )

            # 鉴权拦截在业务逻辑之前 → schedule 仍存在
            assert await _exists(local_db, data, CourseSchedule, schedule_id) is True
        finally:
            await _cleanup(local_db, data, schedule_ids=[schedule_id])

    async def test_http_delete_nonexistent_returns_business_error(
        self, client: AsyncClient, delete_data
    ):
        """AC-6：删除不存在排期 → 404 业务错误信封（code=404，msg 含"不存在"）"""
        token = await _login(client, SUPER_ADMIN)
        resp = await client.delete(
            f"{BASE}/schedules/999999999",
            headers=_headers(token),
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 404
        assert "不存在" in body["msg"]
        assert "Traceback" not in str(body)

    async def test_http_delete_normal_with_bookings_returns_400(
        self, client: AsyncClient, delete_data, local_db
    ):
        """补充：HTTP 删除 NORMAL 且 booked_count>0 的排期 → 400 信封，DB 无变更"""
        data = delete_data
        schedule_id = await _create_schedule(
            local_db, data, status=ScheduleStatus.NORMAL.value, booked_count=1
        )
        booking_id = await _create_booking(
            local_db, data, schedule_id, status=BookingStatus.BOOKED.value
        )
        try:
            token = await _login(client, SUPER_ADMIN)
            resp = await client.delete(
                f"{BASE}/schedules/{schedule_id}",
                headers=_headers(token),
            )
            assert resp.status_code == 400
            body = resp.json()
            assert body["code"] == 400
            assert "仍有学员预约" in body["msg"]
            assert "先取消排期后再删除" in body["msg"]
            assert "Traceback" not in str(body)

            assert await _exists(local_db, data, CourseSchedule, schedule_id) is True
            assert await _exists(local_db, data, Booking, booking_id) is True
        finally:
            await _cleanup(
                local_db,
                data,
                schedule_ids=[schedule_id],
                booking_ids=[booking_id],
            )
