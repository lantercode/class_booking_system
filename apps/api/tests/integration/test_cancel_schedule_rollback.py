"""
F2.4 cancel_schedule 回补失败回滚 - 集成测试

验证目标（对应 Feature 2.4 Acceptance Criteria）：
- AC-1：正常取消（含 booking+card）→ 全部 booking CANCELLED + credit 恢复 + schedule CANCELLED
- AC-2：restore_credit 失败 → cancel_schedule raise BusinessException(500) → 整体回滚
        schedule 仍 NORMAL / booked_count 不变 / booking 仍 BOOKED / cancelled_at 仍 None
        / card.used_credits 不变（未恢复）
- AC-3：多 booking 场景，中途 restore_credit 失败 → 整体回滚 → 已处理成功的 booking 变更也回滚
- AC-4：schedule 无 BOOKED 预约 → cancel_schedule 直接成功
- AC-5：已 CANCELLED 排期再取消 → 400 "排期已取消"
- AC-6：HTTP 端点 POST /schedules/{id}/cancel 正常路径 → 200 + 信封字段正确
- AC-7：HTTP 端点失败路径（构造 used_credits=0 的卡触发 restore_credit 真实失败）
        → 500 + 信封 + 无 Traceback + DB 回滚
- AC-8：回归 test_checkin_complete_lock / test_booking_ownership / test_auth_api

事务回滚原理：
  Service 内任一异常直接 raise（不吞、不 try/except 外层兜底），db.commit() 永不执行，
  AsyncSession 由 with 语句或 FastAPI 依赖清理时被动 rollback → 全部变更不落地。

测试策略：
  - AC-1/AC-2/AC-3/AC-4/AC-5：Service 直调路径，精确控制 mock + 直接读 DB 断言
  - AC-6/AC-7：HTTP 端点路径（live_server 真实 Uvicorn），端到端契约 + 信封 + 不泄露
  - mock 失败仅作用于 Service 直调路径（monkeypatch 仅替换测试进程的类属性，
    对 live_server 独立进程不生效）；HTTP 失败路径改用真实失败场景（used_credits=0 触发
    restore_credit 真实抛 HTTPException(400) → 内层 except 包装为 BusinessException(500)）

数据搭建：
  - rollback_data（session-scoped）创建 1 共享 course + 2 个临时 student（student_a / student_b）
    供多 booking 场景使用（uq_bookings_schedule_student_active 唯一约束要求
    同 schedule + 同 student 只能 1 个 active booking）。
  - 每用例独立搭建 schedule + booking + card，用例结束清理。

事件循环隔离设计（借鉴 F2.2/F2.3）：
  - rollback_data 在 session loop 内 dispose engine，只返回纯数据 dict。
  - local_db（function-scoped）为每用例创建独立 engine + session_factory。

前置条件：
  - 种子数据已由 conftest.seed_test_database 初始化
    （super_admin=13800000001 / teacher=13800138001 / student=13900139001，密码 Test@123456）
  - Redis 可用（RBAC 装饰器缓存）
  - PostgreSQL 支持 SELECT ... FOR UPDATE

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_cancel_schedule_rollback.py -v
"""

import time
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
from app.modules.membership.models import CardStatus, MembershipCard, MembershipCardTransaction
from app.modules.membership.service import MembershipCardService
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.schedule.service import ScheduleService
from app.modules.tenant.models import Tenant
from app.modules.user.models import User

TENANT_HEADERS = {"x-tenant-slug": "dance-school"}
SUPER_ADMIN = {"phone": "13800000001", "password": "Test@123456"}  # super_admin（持 schedule:cancel）
SEED_STUDENT = {"phone": "13900139001", "password": "Test@123456"}  # 李同学
SEED_TEACHER = {"phone": "13800138001", "password": "Test@123456"}  # 张老师

BASE = "/api/v1"


# ============================================================
# 公共 helper（登录、HTTP 头、临时用户管理）
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


def _unique_phone() -> str:
    return f"139{(time.time_ns() // 1000 + uuid4().int) % 100000000:08d}"


async def _get_role_id(client: AsyncClient, token: str, code: str) -> int:
    resp = await client.get(f"{BASE}/roles", headers=_headers(token))
    assert resp.status_code == 200, f"获取角色列表失败: {resp.text}"
    items = resp.json()["data"]["items"]
    return next(r["id"] for r in items if r["code"] == code)


async def _lookup_user_id(client: AsyncClient, token: str, phone: str) -> int:
    resp = await client.get(
        f"{BASE}/admin/users", params={"keyword": phone}, headers=_headers(token)
    )
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    return next(u["id"] for u in items if u["phone"] == phone)


async def _create_temp_student(
    client: AsyncClient, admin_token: str, username: str
) -> tuple[int, str]:
    """通过 admin HTTP 创建临时 student 用户，返回 (user_id, phone)"""
    role_id = await _get_role_id(client, admin_token, "student")
    phone = _unique_phone()
    payload = {
        "username": username,
        "phone": phone,
        "password": "Test@123456",
        "is_active": True,
        "role_ids": [role_id],
    }
    resp = await client.post(
        f"{BASE}/admin/users", json=payload, headers=_headers(admin_token)
    )
    assert resp.status_code == 201, f"创建用户失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"创建用户业务失败: {body}"
    user_id = await _lookup_user_id(client, admin_token, phone)
    return user_id, phone


async def _delete_user(client: AsyncClient, admin_token: str, user_id: int) -> None:
    try:
        await client.delete(
            f"{BASE}/admin/users/{user_id}", headers=_headers(admin_token)
        )
    except Exception:
        pass


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="session")
async def rollback_data(live_server):
    """搭建共享数据（session 级）：1 共享 course + 2 个临时 student（供多 booking 场景）。

    临时 student_a / student_b 用于同一 schedule 下创建 2 个不同 student 的 booking，
    规避 ``uq_bookings_schedule_student_active`` 唯一约束
    （(schedule_id, student_id) 组合唯一）。

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

    # 1. 经 admin HTTP 创建 2 个临时 student（密码哈希 / 角色 / profile 由 Service 处理）
    async with AsyncClient(base_url=live_server) as setup_client:
        admin_token = await _login(setup_client, SUPER_ADMIN)
        student_a_id, student_a_phone = await _create_temp_student(
            setup_client, admin_token, f"回滚A{uuid4().hex[:4]}"
        )
        student_b_id, student_b_phone = await _create_temp_student(
            setup_client, admin_token, f"回滚B{uuid4().hex[:4]}"
        )

    course_ids: list[int] = []
    tenant_id: int
    student_id: int
    teacher_id: int
    admin_id: int

    # 2. 解析种子 IDs + 创建共享 course
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
        admin_id = (
            await session.execute(select(User).where(User.phone == SUPER_ADMIN["phone"]))
        ).scalar_one().id

        set_tenant_id(tenant_id)
        course = Course(
            tenant_id=tenant_id,
            name=f"回滚测试课程{uuid4().hex[:6]}",
            duration_minutes=60,
        )
        session.add(course)
        await session.flush()
        course_ids.append(course.id)
        await session.commit()

    data = {
        "tenant_id": tenant_id,
        "student_id": student_id,
        "student_a_id": student_a_id,
        "student_b_id": student_b_id,
        "teacher_id": teacher_id,
        "admin_id": admin_id,
        "course_ids": course_ids,
        "student_a_phone": student_a_phone,
        "student_b_phone": student_b_phone,
    }
    yield data

    # 3. 清理：先 DB 删 booking（避免阻塞用户软删）→ 删共享 course → 软删临时用户
    async with session_factory() as session:
        set_tenant_id(data["tenant_id"])
        # 兜底清理可能残留的测试 booking（防止用例 cleanup 失败留下脏数据阻塞用户软删）
        await session.execute(
            delete(Booking).where(
                Booking.student_id.in_(
                    [data["student_id"], data["student_a_id"], data["student_b_id"]]
                )
            )
        )
        await session.execute(delete(Course).where(Course.id.in_(data["course_ids"])))
        await session.commit()
    await engine.dispose()

    async with AsyncClient(base_url=live_server) as cleanup_client:
        tok = await _login(cleanup_client, SUPER_ADMIN)
        for uid in (data["student_a_id"], data["student_b_id"]):
            await _delete_user(cleanup_client, tok, uid)


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
# Helper：直接落库构造 schedule / booking / card 数据
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
            teacher_id=data["teacher_id"],
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


async def _create_card(
    sf,
    data: dict,
    student_id: int,
    *,
    used_credits: int = 1,
    total_credits: int = 10,
) -> int:
    """直接落库 1 个 ACTIVE 会员卡，返回 id（调用方负责清理）"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        card = MembershipCard(
            tenant_id=data["tenant_id"],
            student_id=student_id,
            card_type="count",
            card_no=MembershipCard.generate_card_no(),
            total_credits=total_credits,
            used_credits=used_credits,
            valid_from=datetime.now(UTC) - timedelta(days=1),
            expire_at=datetime.now(UTC) + timedelta(days=30),
            status=CardStatus.ACTIVE.value,
        )
        session.add(card)
        await session.flush()
        card_id = card.id
        await session.commit()
    return card_id


async def _create_booking(
    sf,
    data: dict,
    schedule_id: int,
    student_id: int,
    *,
    card_id: int | None = None,
    status: int = BookingStatus.BOOKED.value,
) -> int:
    """直接落库 1 个 booking，返回 id（调用方负责清理）"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        booking = Booking(
            tenant_id=data["tenant_id"],
            schedule_id=schedule_id,
            student_id=student_id,
            status=status,
            source=BookingSource.SELF.value,
            membership_card_id=card_id,
        )
        session.add(booking)
        await session.flush()
        booking_id = booking.id
        await session.commit()
    return booking_id


async def _get_field(sf, data: dict, model, entity_id: int, field) -> object:
    """读单字段（独立 session，避免读到未提交的脏数据）"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        result = await session.execute(select(field).where(model.id == entity_id))
        return result.scalar_one()


async def _cleanup(
    sf,
    data: dict,
    *,
    schedule_ids=None,
    booking_ids=None,
    card_ids=None,
) -> None:
    """清理测试数据。

    顺序：txn（按 card_id）→ booking → card → schedule；每步独立 session + commit，
    避免单步失败导致整个 session abort 阻塞后续清理（restore_credit 成功路径会
    创建 MembershipCardTransaction 引用 card，删 card 前必须先删 txn，否则 FK 违反）。
    """
    # 1. 清理 card 关联的 txn（restore_credit 创建的）
    if card_ids:
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            await session.execute(
                delete(MembershipCardTransaction).where(
                    MembershipCardTransaction.card_id.in_(card_ids)
                )
            )
            await session.commit()

    # 2. 删 booking
    if booking_ids:
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            await session.execute(delete(Booking).where(Booking.id.in_(booking_ids)))
            await session.commit()

    # 3. 删 card
    if card_ids:
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            await session.execute(
                delete(MembershipCard).where(MembershipCard.id.in_(card_ids))
            )
            await session.commit()

    # 4. 删 schedule
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
class TestCancelScheduleRollbackService:
    """F2.4 cancel_schedule 回补失败回滚（Service 直调路径）"""

    async def test_cancel_schedule_normal_ok(self, rollback_data, local_db):
        """AC-1：正常取消（含 booking+card）→ 全部 CANCELLED + credit 恢复 + schedule CANCELLED"""
        data = rollback_data
        schedule_id = await _create_schedule(local_db, data, booked_count=1)
        card_id = await _create_card(local_db, data, data["student_id"], used_credits=1)
        booking_id = await _create_booking(
            local_db, data, schedule_id, data["student_id"], card_id=card_id
        )
        try:
            async with local_db() as session:
                set_tenant_id(data["tenant_id"])
                service = ScheduleService()
                result = await service.cancel_schedule(
                    session,
                    schedule_id,
                    cancel_reason="测试取消",
                    operator_id=data["admin_id"],
                )
                assert result["total_bookings"] == 1
                assert result["success_count"] == 1
                assert result["failed_count"] == 0
                assert result["failed_bookings"] == []

            # 验证 DB 终态（新 session 读，避免读到 dirty session）
            assert (
                await _get_field(
                    local_db, data, CourseSchedule, schedule_id, CourseSchedule.status
                )
                == ScheduleStatus.CANCELLED.value
            )
            assert (
                await _get_field(
                    local_db,
                    data,
                    CourseSchedule,
                    schedule_id,
                    CourseSchedule.booked_count,
                )
                == 0
            )
            assert (
                await _get_field(local_db, data, Booking, booking_id, Booking.status)
                == BookingStatus.CANCELLED.value
            )
            assert (
                await _get_field(
                    local_db, data, Booking, booking_id, Booking.cancelled_at
                )
                is not None
            )
            assert (
                await _get_field(
                    local_db,
                    data,
                    MembershipCard,
                    card_id,
                    MembershipCard.used_credits,
                )
                == 0
            )  # 恢复 1→0
        finally:
            await _cleanup(
                local_db,
                data,
                schedule_ids=[schedule_id],
                booking_ids=[booking_id],
                card_ids=[card_id],
            )

    async def test_cancel_schedule_restore_credit_failure_rolls_back_all(
        self, rollback_data, local_db, monkeypatch
    ):
        """AC-2：mock restore_credit 抛异常 → cancel_schedule raise BusinessException(500)
        → 整体回滚（schedule 仍 NORMAL / booked_count 仍 1 / booking 仍 BOOKED /
        cancelled_at 仍 None / card.used_credits 仍 1）
        """
        data = rollback_data
        schedule_id = await _create_schedule(local_db, data, booked_count=1)
        card_id = await _create_card(local_db, data, data["student_id"], used_credits=1)
        booking_id = await _create_booking(
            local_db, data, schedule_id, data["student_id"], card_id=card_id
        )

        call_count = {"n": 0}

        async def _fail_restore(self, *args, **kwargs):
            call_count["n"] += 1
            raise RuntimeError("simulated restore failure")

        monkeypatch.setattr(MembershipCardService, "restore_credit", _fail_restore)

        try:
            async with local_db() as session:
                set_tenant_id(data["tenant_id"])
                service = ScheduleService()
                with pytest.raises(BusinessException) as exc_info:
                    await service.cancel_schedule(
                        session,
                        schedule_id,
                        cancel_reason="测试取消",
                        operator_id=data["admin_id"],
                    )
                assert exc_info.value.code == 500
                assert "会员卡恢复次数失败" in str(exc_info.value)
                assert "取消排期操作已撤销" in str(exc_info.value)

            assert call_count["n"] == 1, "restore_credit 应被调用 1 次后即 raise"

            # 验证 DB 无任何变更（事务回滚）
            assert (
                await _get_field(
                    local_db, data, CourseSchedule, schedule_id, CourseSchedule.status
                )
                == ScheduleStatus.NORMAL.value
            )
            assert (
                await _get_field(
                    local_db,
                    data,
                    CourseSchedule,
                    schedule_id,
                    CourseSchedule.booked_count,
                )
                == 1
            )
            assert (
                await _get_field(local_db, data, Booking, booking_id, Booking.status)
                == BookingStatus.BOOKED.value
            )
            assert (
                await _get_field(
                    local_db, data, Booking, booking_id, Booking.cancelled_at
                )
                is None
            )
            assert (
                await _get_field(
                    local_db,
                    data,
                    MembershipCard,
                    card_id,
                    MembershipCard.used_credits,
                )
                == 1
            )  # 未恢复
        finally:
            # restore_credit mock 失败 → 事务回滚 → 无 txn 创建 → card 无 FK 引用
            await _cleanup(
                local_db,
                data,
                schedule_ids=[schedule_id],
                booking_ids=[booking_id],
                card_ids=[card_id],
            )

    async def test_cancel_schedule_partial_failure_rolls_back_prior_success(
        self, rollback_data, local_db, monkeypatch
    ):
        """AC-3：2 个 booking；第一个 restore 成功，第二个 restore 失败 → 整体回滚
        → 第一个的变更（booking.status / decrement / card.used_credits）也回滚

        构造：1 schedule（booked_count=2）+ 2 个不同 student 的 BOOKED booking
              + 2 个 ACTIVE card（各 used_credits=1）
        mock：第 2 次调用 restore_credit 抛异常
        预期：cancel_schedule raise BusinessException；call_count==2；
              schedule 仍 NORMAL / booked_count 仍 2 / 两 booking 都仍 BOOKED /
              两 booking 的 cancelled_at 都仍 None / 两 card.used_credits 都仍 1
        """
        data = rollback_data
        schedule_id = await _create_schedule(local_db, data, booked_count=2, capacity=10)
        card_id_1 = await _create_card(local_db, data, data["student_a_id"], used_credits=1)
        card_id_2 = await _create_card(local_db, data, data["student_b_id"], used_credits=1)
        booking_id_1 = await _create_booking(
            local_db, data, schedule_id, data["student_a_id"], card_id=card_id_1
        )
        booking_id_2 = await _create_booking(
            local_db, data, schedule_id, data["student_b_id"], card_id=card_id_2
        )

        call_count = {"n": 0}

        async def _fail_on_second(self, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise RuntimeError("simulated restore failure on second")

        monkeypatch.setattr(MembershipCardService, "restore_credit", _fail_on_second)

        try:
            async with local_db() as session:
                set_tenant_id(data["tenant_id"])
                service = ScheduleService()
                with pytest.raises(BusinessException) as exc_info:
                    await service.cancel_schedule(
                        session,
                        schedule_id,
                        cancel_reason="测试取消",
                        operator_id=data["admin_id"],
                    )
                assert exc_info.value.code == 500
                assert "会员卡恢复次数失败" in str(exc_info.value)

            assert call_count["n"] == 2, "restore_credit 应被调用 2 次（第 2 次失败）"

            # 验证整体回滚（第一个 booking 的变更也回滚）
            assert (
                await _get_field(
                    local_db, data, CourseSchedule, schedule_id, CourseSchedule.status
                )
                == ScheduleStatus.NORMAL.value
            )
            assert (
                await _get_field(
                    local_db,
                    data,
                    CourseSchedule,
                    schedule_id,
                    CourseSchedule.booked_count,
                )
                == 2
            )  # 未减
            for bid in (booking_id_1, booking_id_2):
                assert (
                    await _get_field(local_db, data, Booking, bid, Booking.status)
                    == BookingStatus.BOOKED.value
                ), f"booking {bid} 状态未回滚"
                assert (
                    await _get_field(local_db, data, Booking, bid, Booking.cancelled_at)
                    is None
                ), f"booking {bid} cancelled_at 未回滚"
            for cid in (card_id_1, card_id_2):
                assert (
                    await _get_field(
                        local_db,
                        data,
                        MembershipCard,
                        cid,
                        MembershipCard.used_credits,
                    )
                    == 1
                ), f"card {cid} used_credits 未回滚"
        finally:
            # 第二次 mock 失败 → 事务回滚 → restore_credit 内部 INSERT 的 txn 也回滚
            # → 两张 card 都无 txn 引用 → cleanup 可直接删 card
            await _cleanup(
                local_db,
                data,
                schedule_ids=[schedule_id],
                booking_ids=[booking_id_1, booking_id_2],
                card_ids=[card_id_1, card_id_2],
            )

    async def test_cancel_schedule_no_bookings_ok(self, rollback_data, local_db):
        """AC-4：schedule 无 BOOKED 预约 → cancel_schedule 直接成功，不调 restore_credit"""
        data = rollback_data
        schedule_id = await _create_schedule(local_db, data, booked_count=0)
        try:
            async with local_db() as session:
                set_tenant_id(data["tenant_id"])
                service = ScheduleService()
                result = await service.cancel_schedule(
                    session,
                    schedule_id,
                    cancel_reason="无预约取消",
                    operator_id=data["admin_id"],
                )
                assert result["total_bookings"] == 0
                assert result["success_count"] == 0

            assert (
                await _get_field(
                    local_db, data, CourseSchedule, schedule_id, CourseSchedule.status
                )
                == ScheduleStatus.CANCELLED.value
            )
        finally:
            await _cleanup(local_db, data, schedule_ids=[schedule_id])

    async def test_cancel_schedule_already_cancelled_fails(self, rollback_data, local_db):
        """AC-5：已 CANCELLED 排期再取消 → 400 "排期已取消"（状态校验前置）"""
        data = rollback_data
        schedule_id = await _create_schedule(
            local_db, data, status=ScheduleStatus.CANCELLED.value
        )
        try:
            async with local_db() as session:
                set_tenant_id(data["tenant_id"])
                service = ScheduleService()
                with pytest.raises(BusinessException) as exc_info:
                    await service.cancel_schedule(
                        session,
                        schedule_id,
                        cancel_reason="再次取消",
                        operator_id=data["admin_id"],
                    )
                assert exc_info.value.code == 400
                assert "已取消" in str(exc_info.value)
        finally:
            await _cleanup(local_db, data, schedule_ids=[schedule_id])

    async def test_cancel_schedule_finished_fails(self, rollback_data, local_db):
        """补充：已 FINISHED 排期取消 → 400 "已完成，无法取消" """
        data = rollback_data
        schedule_id = await _create_schedule(
            local_db, data, status=ScheduleStatus.FINISHED.value
        )
        try:
            async with local_db() as session:
                set_tenant_id(data["tenant_id"])
                service = ScheduleService()
                with pytest.raises(BusinessException) as exc_info:
                    await service.cancel_schedule(
                        session,
                        schedule_id,
                        cancel_reason="错误取消",
                        operator_id=data["admin_id"],
                    )
                assert exc_info.value.code == 400
                assert "已完成" in str(exc_info.value)
        finally:
            await _cleanup(local_db, data, schedule_ids=[schedule_id])

    async def test_cancel_schedule_nonexistent_returns_404(self, rollback_data, local_db):
        """补充：不存在 schedule → 404 "排期不存在" """
        data = rollback_data
        async with local_db() as session:
            set_tenant_id(data["tenant_id"])
            service = ScheduleService()
            with pytest.raises(NotFoundException):
                await service.cancel_schedule(
                    session,
                    999999999,
                    cancel_reason="不存在",
                    operator_id=data["admin_id"],
                )


# ============================================================
# HTTP 端点路径测试（live_server 真实 Uvicorn）
# ============================================================


@pytest.mark.asyncio
class TestCancelScheduleRollbackHTTP:
    """F2.4 cancel_schedule 回补失败回滚（HTTP 端点路径，端到端契约）"""

    async def test_http_cancel_schedule_normal_ok(
        self, client: AsyncClient, rollback_data, local_db
    ):
        """AC-6：HTTP 端点正常取消 → 200 + 信封字段正确 + DB 终态正确"""
        data = rollback_data
        schedule_id = await _create_schedule(local_db, data, booked_count=1)
        card_id = await _create_card(local_db, data, data["student_id"], used_credits=1)
        booking_id = await _create_booking(
            local_db, data, schedule_id, data["student_id"], card_id=card_id
        )
        try:
            token = await _login(client, SUPER_ADMIN)
            resp = await client.post(
                f"{BASE}/schedules/{schedule_id}/cancel",
                json={"cancel_reason": "HTTP 正常取消"},
                headers=_headers(token),
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["code"] == 0
            assert body["msg"]
            assert "Traceback" not in body["msg"]
            assert "Traceback" not in str(body)
            payload = body["data"]
            assert payload["schedule_id"] == schedule_id
            assert payload["total_bookings"] == 1
            assert payload["success_count"] == 1
            assert payload["failed_count"] == 0

            # 验证 DB 终态
            assert (
                await _get_field(
                    local_db, data, CourseSchedule, schedule_id, CourseSchedule.status
                )
                == ScheduleStatus.CANCELLED.value
            )
            assert (
                await _get_field(local_db, data, Booking, booking_id, Booking.status)
                == BookingStatus.CANCELLED.value
            )
            assert (
                await _get_field(
                    local_db,
                    data,
                    MembershipCard,
                    card_id,
                    MembershipCard.used_credits,
                )
                == 0
            )
        finally:
            await _cleanup(
                local_db,
                data,
                schedule_ids=[schedule_id],
                booking_ids=[booking_id],
                card_ids=[card_id],
            )

    async def test_http_cancel_schedule_restore_failure_rolls_back(
        self, client: AsyncClient, rollback_data, local_db
    ):
        """AC-7：HTTP 端点失败路径 → 500 + 信封 + 无 Traceback + DB 整体回滚

        无法在 live_server 独立进程内 monkeypatch，改用真实失败场景：
        构造 used_credits=0 的卡 → restore_credit 内部
        ``if card.used_credits <= 0: raise HTTPException(400)`` → 被内层 except 捕获 →
        重新 raise BusinessException(500) → 全局异常处理器返回 500 信封。
        """
        data = rollback_data
        schedule_id = await _create_schedule(local_db, data, booked_count=1)
        # used_credits=0 触发 restore_credit 真实失败
        card_id = await _create_card(local_db, data, data["student_id"], used_credits=0)
        booking_id = await _create_booking(
            local_db, data, schedule_id, data["student_id"], card_id=card_id
        )
        try:
            token = await _login(client, SUPER_ADMIN)
            resp = await client.post(
                f"{BASE}/schedules/{schedule_id}/cancel",
                json={"cancel_reason": "HTTP 失败取消"},
                headers=_headers(token),
            )
            assert resp.status_code == 500, (
                f"期望 500，实际 {resp.status_code}: {resp.text}"
            )
            body = resp.json()
            assert body["code"] == 500
            assert "会员卡恢复次数失败" in body["msg"], (
                f"msg 应含'会员卡恢复次数失败'，实际: {body['msg']}"
            )
            assert "取消排期操作已撤销" in body["msg"]
            assert "Traceback" not in body["msg"]
            assert "Traceback" not in str(body)
            # 不回显内部异常类型（RuntimeError/HTTPException 等不应出现在响应）
            assert "RuntimeError" not in body["msg"]
            assert "HTTPException" not in body["msg"]

            # 验证 DB 整体回滚
            assert (
                await _get_field(
                    local_db, data, CourseSchedule, schedule_id, CourseSchedule.status
                )
                == ScheduleStatus.NORMAL.value
            )
            assert (
                await _get_field(
                    local_db,
                    data,
                    CourseSchedule,
                    schedule_id,
                    CourseSchedule.booked_count,
                )
                == 1
            )  # 未减
            assert (
                await _get_field(local_db, data, Booking, booking_id, Booking.status)
                == BookingStatus.BOOKED.value
            )
            assert (
                await _get_field(
                    local_db, data, Booking, booking_id, Booking.cancelled_at
                )
                is None
            )
            assert (
                await _get_field(
                    local_db,
                    data,
                    MembershipCard,
                    card_id,
                    MembershipCard.used_credits,
                )
                == 0
            )  # 未变化（原本就是 0）
        finally:
            # restore_credit 真实失败前未 INSERT txn → card 无 txn 引用 → cleanup 可直接删
            await _cleanup(
                local_db,
                data,
                schedule_ids=[schedule_id],
                booking_ids=[booking_id],
                card_ids=[card_id],
            )

    async def test_http_cancel_schedule_already_cancelled_fails(
        self, client: AsyncClient, rollback_data, local_db
    ):
        """补充：HTTP 已 CANCELLED 排期再取消 → 400 + 信封 + msg 含'已取消'"""
        data = rollback_data
        schedule_id = await _create_schedule(
            local_db, data, status=ScheduleStatus.CANCELLED.value
        )
        try:
            token = await _login(client, SUPER_ADMIN)
            resp = await client.post(
                f"{BASE}/schedules/{schedule_id}/cancel",
                json={"cancel_reason": "再次取消"},
                headers=_headers(token),
            )
            assert resp.status_code == 400
            body = resp.json()
            assert body["code"] == 400
            assert "已取消" in body["msg"]
        finally:
            await _cleanup(local_db, data, schedule_ids=[schedule_id])

    async def test_http_cancel_schedule_nonexistent_returns_404(
        self, client: AsyncClient, rollback_data
    ):
        """补充：HTTP 不存在 schedule → 404 + msg 含'不存在'"""
        token = await _login(client, SUPER_ADMIN)
        resp = await client.post(
            f"{BASE}/schedules/999999999/cancel",
            json={"cancel_reason": "不存在"},
            headers=_headers(token),
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == 404
        assert "不存在" in body["msg"]

    async def test_http_cancel_schedule_unauthorized_fails(
        self, client: AsyncClient, rollback_data, local_db
    ):
        """补充：学员（无 schedule:cancel 权限）取消排期 → 403"""
        data = rollback_data
        schedule_id = await _create_schedule(local_db, data)
        try:
            token = await _login(client, SEED_STUDENT)
            resp = await client.post(
                f"{BASE}/schedules/{schedule_id}/cancel",
                json={"cancel_reason": "学员越权取消"},
                headers=_headers(token),
            )
            assert resp.status_code == 403, (
                f"学员无 schedule:cancel 权限应 403，实际 {resp.status_code}: {resp.text}"
            )
        finally:
            await _cleanup(local_db, data, schedule_ids=[schedule_id])
