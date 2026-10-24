"""
F4.1 恢复 bookings.membership_card_id 外键 - 集成测试

验证目标（对应 Feature 4.1 Acceptance Criteria）：
- AC-1：FK 约束 fk_bookings_membership_card_id 存在且 ON DELETE SET NULL
- AC-2：创建 booking 引用存在的卡 → 成功（membership_card_id 落库）
- AC-3：创建 booking 引用不存在的 card_id → IntegrityError（FK 校验）
- AC-4：删除 card → 关联 booking.membership_card_id 变 NULL（ON DELETE SET NULL）
- AC-5：migration 已清理孤立数据（孤立计数 == 0）
- AC-6：migration 清理逻辑本身正确（drop FK → 插孤立 → 清理 UPDATE →
        card_id 变 NULL → re-add FK 成功；全程事务回滚不污染 DB）

事务/隔离设计（借鉴 F2.4）：
  - rollback_data（session-scoped）在 session loop 内 dispose engine，只返回纯数据 dict。
  - local_db（function-scoped）为每用例独立 engine + session_factory。
  - AC-6 在一个显式事务内 drop FK / 插孤立 / 清理 / re-add FK，最终 rollback；
    PostgreSQL DDL 事务化，rollback 还原原状，不污染 dev DB。

前置条件：
  - migration f41ab2c3d4e5 已 apply（alembic_version == f41ab2c3d4e5）
  - 种子数据已由 conftest.seed_test_database 初始化
    （super_admin=13800000001 / teacher=13800138001 / student=13900139001，密码 Test@123456）

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_booking_fk_membership_card.py -v
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import Booking, BookingSource, BookingStatus
from app.modules.course.models import Course
from app.modules.membership.models import CardStatus, MembershipCard
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.tenant.models import Tenant
from app.modules.user.models import User

TENANT_SLUG = "dance-school"
SEED_STUDENT_PHONE = "13900139001"
SEED_TEACHER_PHONE = "13800138001"
SEED_ADMIN_PHONE = "13800000001"
NONEXISTENT_CARD_ID = 999_999_999  # 不存在的会员卡 ID（FK 校验用）

FK_NAME = "fk_bookings_membership_card_id"


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="session")
async def shared_data():
    """session-scoped：解析种子 IDs + 创建 1 个共享 course，返回纯数据 dict。

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

    tenant_id: int
    student_id: int
    teacher_id: int
    admin_id: int
    course_ids: list[int] = []

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
        admin_id = (
            await session.execute(select(User).where(User.phone == SEED_ADMIN_PHONE))
        ).scalar_one().id

        set_tenant_id(tenant_id)
        course = Course(
            tenant_id=tenant_id,
            name=f"FK测试课程{uuid4().hex[:6]}",
            duration_minutes=60,
        )
        session.add(course)
        await session.flush()
        course_ids.append(course.id)
        await session.commit()

    data = {
        "tenant_id": tenant_id,
        "student_id": student_id,
        "teacher_id": teacher_id,
        "admin_id": admin_id,
        "course_ids": course_ids,
    }
    yield data

    # 清理共享 course（测试 booking/card/schedule 由各用例自行清理）
    async with session_factory() as session:
        set_tenant_id(data["tenant_id"])
        # 兜底清理可能残留的测试 booking / card / schedule
        await session.execute(
            delete(Booking).where(Booking.student_id == data["student_id"])
        )
        await session.execute(
            delete(CourseSchedule).where(CourseSchedule.course_id.in_(data["course_ids"]))
        )
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
# Helper：直接落库构造 schedule / card / booking 数据
# ============================================================


async def _create_schedule(sf, data: dict, *, status: int = ScheduleStatus.NORMAL.value) -> int:
    """直接落库 1 个 schedule，返回 id（调用方负责清理）。"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        start = datetime.now(UTC) + timedelta(hours=3)
        schedule = CourseSchedule(
            tenant_id=data["tenant_id"],
            course_id=data["course_ids"][0],
            teacher_id=data["teacher_id"],
            start_at=start,
            end_at=start + timedelta(hours=1),
            capacity=10,
            booked_count=0,
            status=status,
        )
        session.add(schedule)
        await session.flush()
        schedule_id = schedule.id
        await session.commit()
    return schedule_id


async def _create_card(sf, data: dict, student_id: int) -> int:
    """直接落库 1 个 ACTIVE 会员卡，返回 id（调用方负责清理）。"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        card = MembershipCard(
            tenant_id=data["tenant_id"],
            student_id=student_id,
            card_type="count",
            card_no=MembershipCard.generate_card_no(),
            total_credits=10,
            used_credits=0,
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
) -> int:
    """直接落库 1 个 BOOKED booking，返回 id（调用方负责清理）。"""
    async with sf() as session:
        set_tenant_id(data["tenant_id"])
        booking = Booking(
            tenant_id=data["tenant_id"],
            schedule_id=schedule_id,
            student_id=student_id,
            status=BookingStatus.BOOKED.value,
            source=BookingSource.SELF.value,
            membership_card_id=card_id,
        )
        session.add(booking)
        await session.flush()
        booking_id = booking.id
        await session.commit()
    return booking_id


async def _cleanup(sf, data: dict, *, schedule_id: int | None = None,
                   card_id: int | None = None, booking_id: int | None = None) -> None:
    """按 id 清理测试数据；每步独立 session + commit，避免单步失败阻塞后续清理。"""
    targets = [("booking", booking_id), ("card", card_id), ("schedule", schedule_id)]
    for kind, _id in targets:
        if _id is None:
            continue
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            if kind == "booking":
                await session.execute(delete(Booking).where(Booking.id == _id))
            elif kind == "card":
                # 先删可能引用 card 的 txn，再删 card
                await session.execute(
                    text(
                        "DELETE FROM membership_card_transactions WHERE card_id = :cid"
                    ),
                    {"cid": _id},
                )
                await session.execute(
                    delete(MembershipCard).where(MembershipCard.id == _id)
                )
            elif kind == "schedule":
                await session.execute(
                    delete(CourseSchedule).where(CourseSchedule.id == _id)
                )
            await session.commit()


# ============================================================
# 测试用例
# ============================================================


class TestBookingFkMembershipCard:
    """F4.1 bookings.membership_card_id 外键约束行为验证。"""

    # AC-1：FK 约束存在且 ON DELETE SET NULL
    async def test_fk_constraint_exists_with_on_delete_set_null(self, local_db, shared_data):
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
                         WHERE conrelid = 'bookings'::regclass
                           AND conname = :name
                        """
                    ),
                    {"name": FK_NAME},
                )
            ).scalar_one_or_none()
            assert row is not None, f"FK {FK_NAME} 不存在"
            assert "FOREIGN KEY (membership_card_id) REFERENCES membership_cards(id)" in row
            assert "ON DELETE SET NULL" in row

    # AC-2：正常 booking 引用存在的卡 → 成功
    async def test_booking_with_valid_membership_card_succeeds(self, local_db, shared_data):
        sf = local_db
        data = shared_data
        schedule_id = await _create_schedule(sf, data)
        card_id = await _create_card(sf, data, data["student_id"])
        booking_id: int | None = None
        try:
            booking_id = await _create_booking(
                sf, data, schedule_id, data["student_id"], card_id=card_id
            )
            # 重新读取确认 membership_card_id 落库
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                fetched = (
                    await session.execute(select(Booking).where(Booking.id == booking_id))
                ).scalar_one()
                assert fetched.membership_card_id == card_id
        finally:
            await _cleanup(
                sf, data, schedule_id=schedule_id, card_id=card_id, booking_id=booking_id
            )

    # AC-3：booking 引用不存在的 card_id → IntegrityError
    async def test_booking_with_nonexistent_card_raises_integrity_error(
        self, local_db, shared_data
    ):
        sf = local_db
        data = shared_data
        schedule_id = await _create_schedule(sf, data)
        booking_id: int | None = None
        try:
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                booking = Booking(
                    tenant_id=data["tenant_id"],
                    schedule_id=schedule_id,
                    student_id=data["student_id"],
                    status=BookingStatus.BOOKED.value,
                    source=BookingSource.SELF.value,
                    membership_card_id=NONEXISTENT_CARD_ID,
                )
                session.add(booking)
                with pytest.raises(IntegrityError):
                    await session.commit()
                # commit 失败后回滚，booking 未落库
                await session.rollback()
            # 二次确认：该 booking 不存在
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                rows = (
                    await session.execute(
                        select(Booking).where(
                            Booking.membership_card_id == NONEXISTENT_CARD_ID
                        )
                    )
                ).scalars().all()
                assert rows == []
        finally:
            # commit 失败 → booking_id 为 None；仅需清理 schedule
            await _cleanup(sf, data, schedule_id=schedule_id)

    # AC-4：删除 card → 关联 booking.membership_card_id 变 NULL
    async def test_delete_card_sets_booking_card_id_null(self, local_db, shared_data):
        sf = local_db
        data = shared_data
        schedule_id = await _create_schedule(sf, data)
        card_id = await _create_card(sf, data, data["student_id"])
        booking_id = await _create_booking(
            sf, data, schedule_id, data["student_id"], card_id=card_id
        )
        try:
            # 删除 card（FK ON DELETE SET NULL 应把 booking.membership_card_id 置 NULL）
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                await session.execute(
                    delete(MembershipCard).where(MembershipCard.id == card_id)
                )
                await session.commit()
            # 确认 booking 仍存在且 membership_card_id 已被 SET NULL
            async with sf() as session:
                set_tenant_id(data["tenant_id"])
                fetched = (
                    await session.execute(select(Booking).where(Booking.id == booking_id))
                ).scalar_one()
                assert fetched is not None
                assert fetched.membership_card_id is None
            card_id = None  # 已删，避免 cleanup 重复删除
        finally:
            await _cleanup(
                sf, data, schedule_id=schedule_id, card_id=card_id, booking_id=booking_id
            )

    # AC-5：migration 已清理孤立数据（孤立计数 == 0）
    async def test_no_orphan_bookings_after_migration(self, local_db, shared_data):
        sf = local_db
        data = shared_data
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            conn = await session.connection()
            orphan_count = (
                await conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                          FROM bookings b
                          LEFT JOIN membership_cards m ON b.membership_card_id = m.id
                         WHERE b.membership_card_id IS NOT NULL
                           AND m.id IS NULL
                        """
                    )
                )
            ).scalar()
            assert orphan_count == 0, f"migration 后仍存在 {orphan_count} 条孤立 booking"


class TestBookingFkMigrationLogic:
    """F4.1 migration 清理逻辑本身正确（在事务内复刻，最终回滚不污染 DB）。

    复刻 migration upgrade 的两步：
      1. UPDATE 清理孤立引用
      2. ALTER TABLE ADD CONSTRAINT fk ... ON DELETE SET NULL

    为构造孤立引用，需先临时 DROP 约束（PostgreSQL DDL 事务化，
    整体 rollback 后还原原状）。
    """

    async def test_migration_cleanup_clears_orphan_and_readds_fk(
        self, local_db, shared_data
    ):
        sf = local_db
        data = shared_data

        # 复用一个已存在的 booking 的 schedule_id/student_id/tenant_id（status=CANCELLED
        # 规避 uq_bookings_schedule_student_active 唯一约束）插入孤立 booking。
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            existing = (
                await session.execute(
                    select(Booking).where(Booking.tenant_id == data["tenant_id"]).limit(1)
                )
            ).scalars().first()
            assert existing is not None, "种子数据缺少 booking，无法复用 ID"
            ref_schedule_id = existing.schedule_id
            ref_student_id = existing.student_id

        settings = get_settings()
        engine = create_async_engine(settings.DATABASE_URL, pool_size=2)
        booking_id: int | None = None
        try:
            async with engine.connect() as conn:
                trans = await conn.begin()
                try:
                    # 1. 临时 drop FK（DDL 事务化，rollback 还原）
                    await conn.execute(
                        text(
                            f"ALTER TABLE bookings DROP CONSTRAINT IF EXISTS {FK_NAME}"
                        )
                    )

                    # 2. 插入孤立 booking（card_id 指向不存在的卡）
                    insert_sql = text(
                        """
                        INSERT INTO bookings
                            (public_id, tenant_id, schedule_id, student_id,
                             status, source, membership_card_id, booked_at)
                        VALUES
                            (:public_id, :tenant_id, :schedule_id, :student_id,
                             :status, :source, :card_id, NOW())
                        RETURNING id
                        """
                    )
                    result = await conn.execute(
                        insert_sql,
                        {
                            "public_id": str(uuid4()),
                            "tenant_id": data["tenant_id"],
                            "schedule_id": ref_schedule_id,
                            "student_id": ref_student_id,
                            "status": BookingStatus.CANCELLED.value,
                            "source": BookingSource.SELF.value,
                            "card_id": NONEXISTENT_CARD_ID,
                        },
                    )
                    booking_id = result.scalar()

                    # 3. 验证孤立引用已落库
                    pre = (
                        await conn.execute(
                            text(
                                "SELECT membership_card_id FROM bookings WHERE id = :id"
                            ),
                            {"id": booking_id},
                        )
                    ).scalar()
                    assert pre == NONEXISTENT_CARD_ID

                    # 4. 复刻 migration 的清理 UPDATE
                    await conn.execute(
                        text(
                            """
                            UPDATE bookings
                               SET membership_card_id = NULL
                             WHERE membership_card_id IS NOT NULL
                               AND membership_card_id NOT IN (SELECT id FROM membership_cards)
                            """
                        )
                    )

                    # 5. 验证孤立引用被清理
                    post = (
                        await conn.execute(
                            text(
                                "SELECT membership_card_id FROM bookings WHERE id = :id"
                            ),
                            {"id": booking_id},
                        )
                    ).scalar()
                    assert post is None, "清理 UPDATE 未把孤立 membership_card_id 置 NULL"

                    # 6. 复刻 migration 的 re-add FK（清理后应成功）
                    await conn.execute(
                        text(
                            f"""
                            ALTER TABLE bookings
                            ADD CONSTRAINT {FK_NAME}
                            FOREIGN KEY (membership_card_id)
                            REFERENCES membership_cards(id)
                            ON DELETE SET NULL
                            """
                        )
                    )
                finally:
                    # 整体回滚：DDL + DML 全部还原，dev DB 不受影响
                    await trans.rollback()
        finally:
            await engine.dispose()

        # 二次确认：rollback 后孤立 booking 未落库（dev DB 无残留）
        async with sf() as session:
            set_tenant_id(data["tenant_id"])
            rows = (
                await session.execute(
                    select(Booking).where(Booking.id == (booking_id or -1))
                )
            ).scalars().all()
            assert rows == [], "回滚后测试 booking 不应残留"
