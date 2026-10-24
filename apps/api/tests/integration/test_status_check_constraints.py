"""
F4.4 核心表 status 字段 Check 约束 - 集成测试

验证目标（对应 Feature 4.4 Acceptance Criteria）：
- AC-1：ck_bookings_status 存在，CHECK (status IN (1,2,3,4,5))
- AC-2：ck_course_schedules_status 存在，CHECK (status IN (1,2,3))
- AC-3：ck_membership_cards_status 存在，CHECK (status IN (0,1,2,3,6))
- AC-4：bookings 插入非法 status → IntegrityError
- AC-5：course_schedules 插入非法 status → IntegrityError
- AC-6：membership_cards 插入非法 status → IntegrityError
- AC-7：bookings 合法边界（1/5）与中间值（3）→ 成功
- AC-8：course_schedules 合法值（1/2/3）→ 成功
- AC-9：membership_cards 合法边界（0/6）与中间值（1/2/3）→ 成功
- AC-10：migration 未破坏存量数据（三张表越界计数 == 0 且数据仍在）

事务/隔离设计（借鉴 F4.1 / F4.2）：
  - shared_data（session-scoped）在 session loop 内 dispose engine，只返回纯数据 dict。
  - local_db（function-scoped）为每用例独立 engine + session_factory。
  - 非法值用例：依赖行（schedule/card）先正常落库，非法 INSERT 抛 IntegrityError
    后 rollback，再独立 session 清理依赖行；非法行本身未落库无需清理。
  - 合法值用例：insert + commit + 重读验证，finally 清理全部测试行。

前置条件：
  - migration f44ab1c2d3e4 已 apply（alembic_version == f44ab1c2d3e4）
  - 种子数据已由 conftest.seed_test_database 初始化
    （super_admin=13800000001 / teacher=13800138001 / student=13900139001，密码 Test@123456）

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_status_check_constraints.py -v
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import Booking, BookingStatus
from app.modules.course.models import Course
from app.modules.membership.models import CardStatus, MembershipCard
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.tenant.models import Tenant
from app.modules.user.models import User

TENANT_SLUG = "dance-school"
SEED_STUDENT_PHONE = "13900139001"
SEED_TEACHER_PHONE = "13800138001"

CK_BOOKINGS = "ck_bookings_status"
CK_SCHEDULES = "ck_course_schedules_status"
CK_CARDS = "ck_membership_cards_status"

# (表名, 约束名, 合法值) —— 与 migration f44ab1c2d3e4 SPECS 一致
SPECS = (
    ("bookings", CK_BOOKINGS, (1, 2, 3, 4, 5)),
    ("course_schedules", CK_SCHEDULES, (1, 2, 3)),
    ("membership_cards", CK_CARDS, (0, 1, 2, 3, 6)),
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="session")
async def shared_data():
    """session-scoped：解析种子 IDs + 任一既有 course_id，返回纯数据 dict。

    engine 在本 fixture 内创建并 dispose，只返回纯数据 dict——避免 session
    loop 的 engine 被后续 function-scoped 用例跨 loop 复用。
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_size=3, max_overflow=5, pool_pre_ping=True
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        ).scalar_one()
        tenant_id = tenant.id
        student_id = (
            await session.execute(select(User).where(User.phone == SEED_STUDENT_PHONE))
        ).scalar_one().id
        teacher_id = (
            await session.execute(select(User).where(User.phone == SEED_TEACHER_PHONE))
        ).scalar_one().id
        # 复用任一既有课程作为新建排期的 course_id（FK 需要真实存在的行）
        course_id = (
            await session.execute(
                select(Course.id).where(Course.tenant_id == tenant_id).limit(1)
            )
        ).scalar_one()

    data = {
        "tenant_id": tenant_id,
        "student_id": student_id,
        "teacher_id": teacher_id,
        "course_id": course_id,
    }
    yield data

    # 兜底清理：可能残留的测试行（各用例正常应自行清理）
    async with session_factory() as session:
        set_tenant_id(data["tenant_id"])
        await session.execute(
            delete(MembershipCard).where(MembershipCard.card_no.like("TEST-%"))
        )
        # 清理本测试创建的排期（capacity=77 为测试标记值）及其 booking
        test_schedule_ids = (
            select(CourseSchedule.id)
            .where(
                CourseSchedule.tenant_id == data["tenant_id"],
                CourseSchedule.capacity == 77,
            )
            .scalar_subquery()
        )
        await session.execute(
            delete(Booking).where(Booking.schedule_id.in_(test_schedule_ids))
        )
        await session.execute(
            delete(CourseSchedule).where(
                CourseSchedule.tenant_id == data["tenant_id"],
                CourseSchedule.capacity == 77,
            )
        )
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
# Helper：直接落库构造 排期 / 预约 / 会员卡 数据
# ============================================================


def _gen_card_no() -> str:
    """生成测试用 card_no（TEST- 前缀便于兜底清理识别；限长 17）。"""
    return f"TEST-{uuid4().hex[:12]}"


async def _create_schedule(sf, data: dict, status: int) -> int:
    """直接落库 1 个排期（capacity=77 为测试标记值），返回 id（调用方负责清理）。"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        start = datetime.now(UTC) + timedelta(days=30)
        schedule = CourseSchedule(
            tenant_id=data["tenant_id"],
            course_id=data["course_id"],
            teacher_id=data["teacher_id"],
            start_at=start,
            end_at=start + timedelta(hours=1),
            capacity=77,
            booked_count=0,
            status=status,
        )
        session.add(schedule)
        await session.flush()
        schedule_id = schedule.id
        await session.commit()
    return schedule_id


async def _create_booking(sf, data: dict, schedule_id: int, status: int) -> int:
    """直接落库 1 个 booking，返回 id（调用方负责清理）。"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        booking = Booking(
            tenant_id=data["tenant_id"],
            schedule_id=schedule_id,
            student_id=data["student_id"],
            status=status,
        )
        session.add(booking)
        await session.flush()
        booking_id = booking.id
        await session.commit()
    return booking_id


async def _create_card(sf, data: dict, status: int) -> int:
    """直接落库 1 个会员卡，返回 id（调用方负责清理）。"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        card = MembershipCard(
            tenant_id=data["tenant_id"],
            student_id=data["student_id"],
            card_type="count",
            card_no=_gen_card_no(),
            total_credits=10,
            used_credits=0,
            valid_from=datetime.now(UTC) - timedelta(days=1),
            expire_at=datetime.now(UTC) + timedelta(days=30),
            status=status,
        )
        session.add(card)
        await session.flush()
        card_id = card.id
        await session.commit()
    return card_id


async def _cleanup(
    sf,
    data: dict,
    *,
    booking_ids: list[int] | None = None,
    schedule_ids: list[int] | None = None,
    card_ids: list[int] | None = None,
) -> None:
    """按 id 清理测试数据；先 booking 再 schedule（FK RESTRICT），card 独立。"""
    for model, ids in (
        (Booking, booking_ids),
        (CourseSchedule, schedule_ids),
        (MembershipCard, card_ids),
    ):
        if not ids:
            continue
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            await session.execute(delete(model).where(model.id.in_(ids)))
            await session.commit()


# ============================================================
# 测试用例
# ============================================================


class TestStatusCheckConstraintsExist:
    """F4.4 三个 Check 约束存在性验证（AC-1/AC-2/AC-3）。"""

    @pytest.mark.parametrize(
        ("table", "name", "values"),
        SPECS,
        ids=[s[1] for s in SPECS],
    )
    async def test_check_constraint_exists(
        self, local_db, shared_data, table, name, values
    ):
        sf = local_db
        data = shared_data
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            conn = await session.connection()
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT pg_get_constraintdef(oid)
                          FROM pg_constraint
                         WHERE conrelid = CAST(:table AS regclass)
                           AND conname = :name
                           AND contype = 'c'
                        """
                    ),
                    {"table": table, "name": name},
                )
            ).scalar_one_or_none()
            assert row is not None, f"Check 约束 {name} 不存在于 {table}"
            assert "CHECK" in row
            assert "status" in row
            # PG 会把 IN (...) 规范化为 = ANY (ARRAY[...])，逐一核对合法值
            for v in values:
                assert str(v) in row, f"{name} 定义缺少合法值 {v}：{row}"


class TestStatusCheckConstraintsEnforced:
    """F4.4 非法值拒绝 + 合法值放行（AC-4 ~ AC-9）。"""

    # AC-4：bookings 插入非法 status → IntegrityError
    @pytest.mark.parametrize("bad_status", [0, 6, 99], ids=["0", "6", "99"])
    async def test_booking_invalid_status_rejected(
        self, local_db, shared_data, bad_status
    ):
        sf = local_db
        data = shared_data
        schedule_id = await _create_schedule(sf, data, ScheduleStatus.NORMAL.value)
        try:
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                booking = Booking(
                    tenant_id=data["tenant_id"],
                    schedule_id=schedule_id,
                    student_id=data["student_id"],
                    status=bad_status,
                )
                session.add(booking)
                with pytest.raises(IntegrityError):
                    await session.commit()
                await session.rollback()
            # 二次确认：非法 booking 未落库
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                cnt = (
                    await session.execute(
                        select(func.count())
                        .select_from(Booking)
                        .where(Booking.schedule_id == schedule_id)
                    )
                ).scalar()
                assert cnt == 0, f"status={bad_status} 的非法 booking 不应落库"
        finally:
            await _cleanup(sf, data, schedule_ids=[schedule_id])

    # AC-5：course_schedules 插入非法 status → IntegrityError
    @pytest.mark.parametrize("bad_status", [0, 4, 99], ids=["0", "4", "99"])
    async def test_schedule_invalid_status_rejected(
        self, local_db, shared_data, bad_status
    ):
        sf = local_db
        data = shared_data
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            start = datetime.now(UTC) + timedelta(days=30)
            schedule = CourseSchedule(
                tenant_id=data["tenant_id"],
                course_id=data["course_id"],
                teacher_id=data["teacher_id"],
                start_at=start,
                end_at=start + timedelta(hours=1),
                capacity=77,
                booked_count=0,
                status=bad_status,
            )
            session.add(schedule)
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
        # 二次确认：非法 schedule 未落库（capacity=77 为测试标记值）
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            cnt = (
                await session.execute(
                    select(func.count())
                    .select_from(CourseSchedule)
                    .where(
                        CourseSchedule.tenant_id == data["tenant_id"],
                        CourseSchedule.capacity == 77,
                        CourseSchedule.status == bad_status,
                    )
                )
            ).scalar()
            assert cnt == 0, f"status={bad_status} 的非法 schedule 不应落库"

    # AC-6：membership_cards 插入非法 status → IntegrityError
    @pytest.mark.parametrize("bad_status", [4, 5, 99], ids=["4", "5", "99"])
    async def test_card_invalid_status_rejected(self, local_db, shared_data, bad_status):
        sf = local_db
        data = shared_data
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            card = MembershipCard(
                tenant_id=data["tenant_id"],
                student_id=data["student_id"],
                card_type="count",
                card_no=_gen_card_no(),
                total_credits=10,
                used_credits=0,
                status=bad_status,
            )
            session.add(card)
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
        # 二次确认：TEST- 前缀卡 0 残留
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            cnt = (
                await session.execute(
                    select(func.count())
                    .select_from(MembershipCard)
                    .where(MembershipCard.card_no.like("TEST-%"))
                )
            ).scalar()
            assert cnt == 0, f"status={bad_status} 的非法 card 不应落库"

    # AC-7：bookings 合法边界（1/5）与中间值（3）→ 成功
    async def test_booking_valid_statuses_succeed(self, local_db, shared_data):
        sf = local_db
        data = shared_data
        valid_statuses = [
            BookingStatus.BOOKED.value,  # 边界 1
            BookingStatus.CHECKED_IN.value,  # 中间 3
            BookingStatus.NO_SHOW.value,  # 边界 5
        ]
        schedule_ids: list[int] = []
        booking_ids: list[int] = []
        try:
            # 每个 booking 用独立排期（status 1/3 落在部分唯一索引
            # uq_bookings_schedule_student_active 范围内，独立 schedule 避免冲突）
            for st in valid_statuses:
                schedule_ids.append(
                    await _create_schedule(sf, data, ScheduleStatus.NORMAL.value)
                )
                booking_ids.append(
                    await _create_booking(sf, data, schedule_ids[-1], st)
                )
            # 重读验证终态
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                rows = (
                    await session.execute(
                        select(Booking.status)
                        .where(Booking.id.in_(booking_ids))
                        .order_by(Booking.id)
                    )
                ).scalars().all()
                assert sorted(rows) == sorted(valid_statuses)
        finally:
            await _cleanup(
                sf, data, booking_ids=booking_ids, schedule_ids=schedule_ids
            )

    # AC-8：course_schedules 合法值（1/2/3）→ 成功
    async def test_schedule_valid_statuses_succeed(self, local_db, shared_data):
        sf = local_db
        data = shared_data
        valid_statuses = [
            ScheduleStatus.NORMAL.value,  # 1
            ScheduleStatus.CANCELLED.value,  # 2
            ScheduleStatus.FINISHED.value,  # 3
        ]
        schedule_ids: list[int] = []
        try:
            for st in valid_statuses:
                schedule_ids.append(await _create_schedule(sf, data, st))
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                rows = (
                    await session.execute(
                        select(CourseSchedule.status)
                        .where(CourseSchedule.id.in_(schedule_ids))
                        .order_by(CourseSchedule.id)
                    )
                ).scalars().all()
                assert sorted(rows) == sorted(valid_statuses)
        finally:
            await _cleanup(sf, data, schedule_ids=schedule_ids)

    # AC-9：membership_cards 合法边界（0/6）与中间值（1/2/3）→ 成功
    async def test_card_valid_statuses_succeed(self, local_db, shared_data):
        sf = local_db
        data = shared_data
        valid_statuses = [
            CardStatus.PENDING.value,  # 边界 0
            CardStatus.ACTIVE.value,  # 中间 1
            CardStatus.EXPIRED.value,  # 中间 2
            CardStatus.FROZEN.value,  # 中间 3
            CardStatus.CANCELLED.value,  # 边界 6
        ]
        card_ids: list[int] = []
        try:
            for st in valid_statuses:
                card_ids.append(await _create_card(sf, data, st))
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                rows = (
                    await session.execute(
                        select(MembershipCard.status)
                        .where(MembershipCard.id.in_(card_ids))
                        .order_by(MembershipCard.id)
                    )
                ).scalars().all()
                assert sorted(rows) == sorted(valid_statuses)
        finally:
            await _cleanup(sf, data, card_ids=card_ids)


class TestExistingDataIntact:
    """F4.4 migration 未破坏存量数据（AC-10）。"""

    @pytest.mark.parametrize(
        ("table", "name", "values"),
        SPECS,
        ids=[s[0] for s in SPECS],
    )
    async def test_no_out_of_range_status_and_data_present(
        self, local_db, shared_data, table, name, values
    ):
        sf = local_db
        data = shared_data
        allowed = ", ".join(str(v) for v in values)
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            conn = await session.connection()
            violation = (
                await conn.execute(
                    text(
                        f"SELECT COUNT(*) FROM {table} "  # noqa: S608
                        f"WHERE status NOT IN ({allowed})"
                    )
                )
            ).scalar()
            total = (
                await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))  # noqa: S608
            ).scalar()
            assert violation == 0, f"{table} 仍存在 {violation} 行越界 status"
            # migration 前实测三表均非空（11/33/17 行）；存量数据未被破坏
            assert total > 0, f"{table} 存量数据不应为空（migration 不应丢数据）"
