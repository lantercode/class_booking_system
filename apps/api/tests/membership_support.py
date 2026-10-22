"""F6.3 会员卡状态机测试支撑工具（非生产代码）。

集成测试统一使用本模块搭建/清理数据，避免每个用例重复拼接 ORM 对象。
所有 helper 都显式 set_tenant_id，保证 TenantAware 查询与 ORM 自动注入一致。
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.core.tenant_context import set_tenant_id
from app.modules.auth.models import Role, UserRole
from app.modules.booking.models import (
    Booking,
    BookingReschedule,
    BookingSource,
    BookingStatus,
)
from app.modules.course.models import Course
from app.modules.membership.models import (
    CardStatus,
    CardType,
    MembershipCard,
    MembershipCardFreeze,
    MembershipCardProduct,
    MembershipCardTransaction,
)
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.tenant.models import Tenant
from app.modules.user.models import User, UserStatus

BASE = "/api/v1"
TENANT_SLUG = "dance-school"
TENANT_HEADERS = {"x-tenant-slug": TENANT_SLUG}

SUPER_ADMIN = {"phone": "13800000001", "password": "Test@123456"}
SEED_STUDENT = {"phone": "13900139001", "password": "Test@123456"}
SEED_TEACHER = {"phone": "13800138001", "password": "Test@123456"}


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **TENANT_HEADERS}


async def login(client, account: dict) -> str:
    resp = await client.post(f"{BASE}/auth/login", json={"tenant_slug": TENANT_SLUG, **account})
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"登录业务失败: {body}"
    return body["data"]["access_token"]


@asynccontextmanager
async def db_factory():
    """function-scoped engine + session_factory，绑定当前用例事件循环。"""
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False, pool_size=2, max_overflow=3, pool_pre_ping=True
    )
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def get_seed_ids(factory) -> dict:
    async with factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
        ).scalar_one()
        set_tenant_id(tenant.id)
        student = (
            await session.execute(select(User).where(User.phone == SEED_STUDENT["phone"]))
        ).scalar_one()
        teacher = (
            await session.execute(select(User).where(User.phone == SEED_TEACHER["phone"]))
        ).scalar_one()
        return {"tenant_id": tenant.id, "student_id": student.id, "teacher_id": teacher.id}


async def create_course(
    factory,
    tenant_id: int,
    *,
    course_type_code: str | None = None,
    name: str | None = None,
) -> int:
    async with factory() as session:
        set_tenant_id(tenant_id)
        course = Course(
            tenant_id=tenant_id,
            name=name or f"F6.3课程{uuid4().hex[:8]}",
            course_type_code=course_type_code,
            duration_minutes=60,
            price=0,
            required_credits=1,
        )
        session.add(course)
        await session.flush()
        course_id = course.id
        await session.commit()
    return course_id


async def create_schedule(
    factory,
    tenant_id: int,
    *,
    course_id: int,
    teacher_id: int,
    start_at: datetime,
    capacity: int = 10,
) -> int:
    async with factory() as session:
        set_tenant_id(tenant_id)
        schedule = CourseSchedule(
            tenant_id=tenant_id,
            course_id=course_id,
            teacher_id=teacher_id,
            start_at=start_at,
            end_at=start_at + timedelta(hours=1),
            capacity=capacity,
            status=ScheduleStatus.NORMAL.value,
        )
        session.add(schedule)
        await session.flush()
        schedule_id = schedule.id
        await session.commit()
    return schedule_id


async def create_product(
    factory,
    tenant_id: int,
    *,
    card_type: str,
    validity_days: int | None = 30,
    total_credits: int | None = None,
    applicable_course_type_code: str | None = None,
    applicable_course_ids: list[int] | None = None,
) -> int:
    async with factory() as session:
        product = MembershipCardProduct(
            tenant_id=tenant_id,
            name=f"F6.3产品{uuid4().hex[:8]}",
            card_type=card_type,
            price=0,
            validity_days=validity_days,
            total_credits=total_credits,
            applicable_course_type_code=applicable_course_type_code,
            applicable_course_ids=applicable_course_ids,
        )
        session.add(product)
        await session.flush()
        product_id = product.id
        await session.commit()
    return product_id


async def create_card(
    factory,
    tenant_id: int,
    student_id: int,
    *,
    card_type: str = CardType.PERIOD.value,
    status: int = CardStatus.PENDING.value,
    validity_days: int | None = 30,
    valid_from: datetime | None = None,
    expire_at: datetime | None = None,
    product_id: int | None = None,
    total_credits: int | None = None,
    used_credits: int = 0,
    applicable_course_type_code: str | None = None,
    applicable_course_ids: list[int] | None = None,
    created_at: datetime | None = None,
) -> int:
    async with factory() as session:
        set_tenant_id(tenant_id)
        kwargs = {}
        if created_at is not None:
            kwargs["created_at"] = created_at
        card = MembershipCard(
            tenant_id=tenant_id,
            student_id=student_id,
            card_type=card_type,
            status=status,
            validity_days=validity_days,
            valid_from=valid_from,
            expire_at=expire_at,
            product_id=product_id,
            total_credits=total_credits,
            used_credits=used_credits,
            applicable_course_type_code=applicable_course_type_code,
            applicable_course_ids=applicable_course_ids,
            **kwargs,
        )
        session.add(card)
        await session.flush()
        card_id = card.id
        await session.commit()
    return card_id


async def create_booking(
    factory,
    tenant_id: int,
    *,
    schedule_id: int,
    student_id: int,
    membership_card_id: int | None = None,
    status: int = BookingStatus.BOOKED.value,
) -> int:
    async with factory() as session:
        set_tenant_id(tenant_id)
        booking = Booking(
            tenant_id=tenant_id,
            schedule_id=schedule_id,
            student_id=student_id,
            status=status,
            source=BookingSource.SELF.value,
            membership_card_id=membership_card_id,
        )
        session.add(booking)
        await session.flush()
        booking_id = booking.id
        await session.commit()
    return booking_id


async def create_student(
    factory,
    tenant_id: int,
    *,
    role_code: str = "student",
    password: str = "Test@123456",
) -> dict:
    """在租户内创建一个可登录的学员（F6.5 并发/越权用例需要第二名学员）。"""
    phone = f"13{uuid4().int % 1_000_000_000:09d}"
    async with factory() as session:
        set_tenant_id(tenant_id)
        user = User(
            tenant_id=tenant_id,
            phone=phone,
            password_hash=hash_password(password),
            nickname=f"F6.5学员{uuid4().hex[:6]}",
            platform_role=role_code,
            status=UserStatus.ACTIVE.value,
        )
        session.add(user)
        await session.flush()
        role = (
            await session.execute(
                select(Role).where(Role.tenant_id == tenant_id, Role.code == role_code)
            )
        ).scalar_one()
        session.add(UserRole(user_id=user.id, role_id=role.id))
        await session.commit()
        return {"user_id": user.id, "phone": phone, "password": password}


async def fetch_card(factory, tenant_id: int, card_id: int) -> MembershipCard:
    async with factory() as session:
        set_tenant_id(tenant_id)
        return (
            await session.execute(
                select(MembershipCard).where(MembershipCard.id == card_id)
            )
        ).scalar_one()


async def fetch_booking(factory, tenant_id: int, booking_id: int) -> Booking:
    async with factory() as session:
        set_tenant_id(tenant_id)
        return (
            await session.execute(select(Booking).where(Booking.id == booking_id))
        ).scalar_one()


async def fetch_schedule(factory, tenant_id: int, schedule_id: int):
    async with factory() as session:
        set_tenant_id(tenant_id)
        return (
            await session.execute(
                select(CourseSchedule).where(CourseSchedule.id == schedule_id)
            )
        ).scalar_one()


async def count_bookings_for_schedule(factory, tenant_id: int, schedule_id: int) -> int:
    from sqlalchemy import func

    async with factory() as session:
        set_tenant_id(tenant_id)
        return (
            await session.execute(
                select(func.count())
                .select_from(Booking)
                .where(Booking.schedule_id == schedule_id)
            )
        ).scalar_one()


async def count_transactions(factory, tenant_id: int, card_id: int) -> int:
    from sqlalchemy import func

    async with factory() as session:
        set_tenant_id(tenant_id)
        return (
            await session.execute(
                select(func.count())
                .select_from(MembershipCardTransaction)
                .where(MembershipCardTransaction.card_id == card_id)
            )
        ).scalar_one()


async def cleanup(
    factory,
    tenant_id: int,
    *,
    card_ids: list[int] | None = None,
    booking_ids: list[int] | None = None,
    schedule_ids: list[int] | None = None,
    course_ids: list[int] | None = None,
    product_ids: list[int] | None = None,
    student_ids: list[int] | None = None,
) -> None:
    """按外键依赖顺序清理测试数据。

    顺序：transactions → reschedule 审计 → bookings → schedules → courses
    → cards → products → users。
    """
    async with factory() as session:
        set_tenant_id(tenant_id)
        if card_ids:
            await session.execute(
                delete(MembershipCardTransaction).where(
                    MembershipCardTransaction.card_id.in_(card_ids)
                )
            )
            await session.execute(
                delete(MembershipCardFreeze).where(
                    MembershipCardFreeze.card_id.in_(card_ids)
                )
            )
        # F6.5：booking_reschedules 无外键，必须在删除 booking 前按 id 清理；
        # 只传 schedule_ids 时先查出这些排期下的 booking id（含改期新约）。
        scoped_booking_ids = list(booking_ids or [])
        if schedule_ids:
            scoped_booking_ids.extend(
                (
                    await session.execute(
                        select(Booking.id).where(Booking.schedule_id.in_(schedule_ids))
                    )
                )
                .scalars()
                .all()
            )
        scoped_booking_ids = list(dict.fromkeys(scoped_booking_ids))
        if scoped_booking_ids:
            await session.execute(
                delete(BookingReschedule).where(
                    BookingReschedule.tenant_id == tenant_id,
                    or_(
                        BookingReschedule.old_booking_id.in_(scoped_booking_ids),
                        BookingReschedule.new_booking_id.in_(scoped_booking_ids),
                    ),
                )
            )
        if booking_ids:
            await session.execute(delete(Booking).where(Booking.id.in_(booking_ids)))
        if schedule_ids:
            # 兼容测试未显式记录 booking_id 的场景（如并发用例）
            await session.execute(
                delete(Booking).where(Booking.schedule_id.in_(schedule_ids))
            )
            await session.execute(
                delete(CourseSchedule).where(CourseSchedule.id.in_(schedule_ids))
            )
        if course_ids:
            await session.execute(delete(Course).where(Course.id.in_(course_ids)))
        if card_ids:
            await session.execute(
                delete(MembershipCard).where(MembershipCard.id.in_(card_ids))
            )
        if product_ids:
            await session.execute(
                delete(MembershipCardProduct).where(
                    MembershipCardProduct.id.in_(product_ids)
                )
            )
        if student_ids:
            # user_roles 为 ON DELETE CASCADE；booking/card FK 已先行清理
            await session.execute(delete(User).where(User.id.in_(student_ids)))
        await session.commit()


def future_start(days: int = 3, *, hour: int = 10) -> datetime:
    """未来某天的整点（UTC），用于排期。"""
    now = datetime.now(UTC)
    return (now + timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


def day_start(value: datetime) -> datetime:
    """返回指定时间当天 00:00:00（保留 tzinfo）。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def day_end(value: datetime) -> datetime:
    """返回指定时间当天 23:59:59（保留 tzinfo）。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.replace(hour=23, minute=59, second=59, microsecond=0)
