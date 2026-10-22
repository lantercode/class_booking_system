"""
Booking Repository - 预约数据访问层

提供预约相关的数据库操作，继承 TenantAwareRepository 实现自动多租户隔离。
"""

from datetime import UTC, datetime

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.booking.models import Booking, BookingReschedule, BookingStatus
from app.modules.schedule.models import CourseSchedule


class BookingRepository(TenantAwareRepository[Booking]):
    """预约数据访问层"""

    model_class = Booking

    async def search(
        self,
        db: AsyncSession,
        *,
        schedule_id: int | None = None,
        student_id: int | None = None,
        teacher_id: int | None = None,
        status: int | None = None,
        statuses: list[int] | None = None,
        upcoming: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Booking], int]:
        """搜索预约（支持多条件筛选）

        归属过滤参数：
          - student_id：按学员过滤（学员角色由 Service 强制为 current_user.user_id）
          - teacher_id：按排期教师过滤（教师角色由 Service 强制为 current_user.user_id；
            提供时 JOIN course_schedules，命中 idx_schedules_teacher_start 索引）
        """
        base_query = select(Booking)
        count_query = select(func.count()).select_from(Booking)

        # 需要 JOIN 排期表：upcoming（按 start_at 过滤）或 teacher_id（按排期教师过滤）
        needs_schedule_join = upcoming or teacher_id is not None
        if needs_schedule_join:
            base_query = base_query.join(
                CourseSchedule, Booking.schedule_id == CourseSchedule.id
            )
            count_query = count_query.join(
                CourseSchedule, Booking.schedule_id == CourseSchedule.id
            )

        if schedule_id:
            base_query = base_query.where(Booking.schedule_id == schedule_id)
            count_query = count_query.where(Booking.schedule_id == schedule_id)

        if student_id:
            base_query = base_query.where(Booking.student_id == student_id)
            count_query = count_query.where(Booking.student_id == student_id)

        if teacher_id:
            base_query = base_query.where(CourseSchedule.teacher_id == teacher_id)
            count_query = count_query.where(CourseSchedule.teacher_id == teacher_id)

        if statuses:
            base_query = base_query.where(Booking.status.in_(statuses))
            count_query = count_query.where(Booking.status.in_(statuses))
        elif status is not None:
            base_query = base_query.where(Booking.status == status)
            count_query = count_query.where(Booking.status == status)

        # 待上课筛选：只返回还未开始的预约
        if upcoming:
            now = datetime.now(UTC)
            base_query = base_query.where(CourseSchedule.start_at > now)
            count_query = count_query.where(CourseSchedule.start_at > now)

        from app.core.tenant_context import get_tenant_id

        tenant_id = get_tenant_id()
        if tenant_id:
            base_query = base_query.where(Booking.tenant_id == tenant_id)
            count_query = count_query.where(Booking.tenant_id == tenant_id)

        base_query = base_query.order_by(Booking.booked_at.desc())

        offset_val = (page - 1) * page_size
        base_query = base_query.offset(offset_val).limit(page_size)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        result = await db.execute(base_query)
        items = list(result.scalars().all())

        return items, total

    async def find_by_schedule_and_student(
        self,
        db: AsyncSession,
        schedule_id: int,
        student_id: int,
    ) -> Booking | None:
        """通过排期ID和学员ID查找预约"""
        from app.core.tenant_context import get_tenant_id

        query = select(Booking).where(
            and_(
                Booking.schedule_id == schedule_id,
                Booking.student_id == student_id,
            )
        )

        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Booking.tenant_id == tenant_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def find_active_booking(
        self,
        db: AsyncSession,
        schedule_id: int,
        student_id: int,
        *,
        exclude_booking_id: int | None = None,
    ) -> Booking | None:
        """查找学员在指定排期的有效预约（已预约/已签到/已完成）

        ``exclude_booking_id``：F6.5 改期场景排除自身，其余语义不变。
        """
        from app.core.tenant_context import get_tenant_id

        conditions = [
            Booking.schedule_id == schedule_id,
            Booking.student_id == student_id,
            Booking.status.in_(
                [
                    BookingStatus.BOOKED.value,
                    BookingStatus.CHECKED_IN.value,
                    BookingStatus.COMPLETED.value,
                ]
            ),
        ]

        if exclude_booking_id is not None:
            conditions.append(Booking.id != exclude_booking_id)

        query = select(Booking).where(and_(*conditions))

        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Booking.tenant_id == tenant_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def lock_student_booking_scope(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        student_id: int,
    ) -> None:
        """对 (tenant_id, student_id) 获取事务级 advisory lock。

        F6.4：区间重叠无法用唯一索引兜底，而 ``create_booking`` 运行在
        READ COMMITTED（非 SERIALIZABLE），因此显式串行化同一学员的预约创建，
        保证并发提交重叠排期时至多一个成功。锁随 COMMIT/ROLLBACK 自动释放。

        限制：双键形式为 (int4, int4)，ID 需在 int4 范围内（当前量级远低于 2^31）。
        """
        await db.execute(
            text(
                "SELECT pg_advisory_xact_lock("
                "CAST(:tenant_id AS integer), CAST(:student_id AS integer))"
            ),
            {"tenant_id": tenant_id, "student_id": student_id},
        )

    async def find_overlapping_active_booking(
        self,
        db: AsyncSession,
        *,
        student_id: int,
        start_at: datetime,
        end_at: datetime,
        exclude_booking_id: int | None = None,
    ) -> Booking | None:
        """查找该学员进行中预约中，所在排期时间段与 [start_at, end_at) 重叠的预约。

        F6.4（D10）：半开区间 ``start_at < :end_at AND end_at > :start_at``，
        边界相接不算冲突；仅 ``BOOKED`` / ``CHECKED_IN`` 参与判定，
        ``COMPLETED`` / ``NO_SHOW`` / ``CANCELLED`` 不参与。

        F6.5：``exclude_booking_id`` 用于改期排除自身，其余语义不变。
        """
        from app.core.tenant_context import get_tenant_id

        conditions = [
            Booking.student_id == student_id,
            Booking.status.in_(
                [BookingStatus.BOOKED.value, BookingStatus.CHECKED_IN.value]
            ),
            CourseSchedule.start_at < end_at,
            CourseSchedule.end_at > start_at,
        ]

        if exclude_booking_id is not None:
            conditions.append(Booking.id != exclude_booking_id)

        tenant_id = get_tenant_id()
        if tenant_id:
            # 与 find_active_booking 保持同构：JOIN 场景下显式叠加租户谓词，
            # 避免仅依赖 ORM 自动注入（见 security/tenant-isolation.md）。
            conditions.append(Booking.tenant_id == tenant_id)

        query = (
            select(Booking)
            .join(CourseSchedule, Booking.schedule_id == CourseSchedule.id)
            .where(and_(*conditions))
            .order_by(CourseSchedule.start_at.asc())
            .limit(1)
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def count_active_bookings(
        self,
        db: AsyncSession,
        schedule_id: int,
    ) -> int:
        """统计排期的有效预约人数"""
        query = (
            select(func.count())
            .select_from(Booking)
            .where(
                and_(
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
        )

        from app.core.tenant_context import get_tenant_id

        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Booking.tenant_id == tenant_id)

        result = await db.execute(query)
        return result.scalar() or 0

    async def delete_by_schedule_id(
        self,
        db: AsyncSession,
        schedule_id: int,
    ) -> int:
        """删除指定排期的所有预约记录"""
        from app.core.tenant_context import get_tenant_id

        query = Booking.__table__.delete().where(Booking.schedule_id == schedule_id)

        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Booking.tenant_id == tenant_id)

        result = await db.execute(query)
        return result.rowcount

    async def get_by_id_for_update(
        self,
        db: AsyncSession,
        booking_id: int,
    ) -> Booking | None:
        """按主键查询并对 booking 行加悲观锁（SELECT FOR UPDATE）

        用于取消预约等需要强并发安全的场景：
        - 锁住后防止并发取消同时 decrement_booked_count 多次
        - 调用方拿到锁后必须重新检查 status
        - 不使用 skip_locked：取消操作应排队序列化，而非快速失败
        - 锁按主键命中，稳定存在，不会 miss-lock

        F6.5：必须 ``populate_existing``。调用方常先用 ``get_by_id`` 预读，
        锁查询若不刷新会返回 identity map 中的旧快照（并发改期/取消后
        状态与卡字段过期），导致重复回补。
        """
        from app.core.tenant_context import get_tenant_id

        query = (
            select(Booking)
            .where(Booking.id == booking_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Booking.tenant_id == tenant_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def list_ids_by_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
        statuses: tuple[int, ...],
    ) -> list[int]:
        """按排期读取指定状态的 booking id（只读，id ASC）

        F6.3 finalize：先在无锁读阶段拿 id，再按 id ASC 统一加锁，
        避免多行锁顺序不一致导致死锁。
        """
        from app.core.tenant_context import get_tenant_id

        query = (
            select(Booking.id)
            .where(
                Booking.schedule_id == schedule_id,
                Booking.status.in_(statuses),
            )
            .order_by(Booking.id.asc())
        )

        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Booking.tenant_id == tenant_id)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_by_ids_for_update(
        self,
        db: AsyncSession,
        booking_ids: list[int],
    ) -> list[Booking]:
        """按 id 列表批量加悲观锁（ORDER BY id ASC FOR UPDATE）"""
        if not booking_ids:
            return []

        from app.core.tenant_context import get_tenant_id

        query = (
            select(Booking)
            .where(Booking.id.in_(booking_ids))
            .order_by(Booking.id.asc())
            .with_for_update()
        )

        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Booking.tenant_id == tenant_id)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def exists_card_booking_with_statuses(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        statuses: tuple[int, ...],
    ) -> bool:
        """该会员卡是否已有指定状态的预约（只读，LIMIT 1）

        F6.3 T6.3.6：90 天 PENDING 期卡作废前确认卡是否已被使用。
        """
        query = (
            select(Booking.id)
            .where(
                Booking.membership_card_id == card_id,
                Booking.tenant_id == tenant_id,
                Booking.status.in_(statuses),
            )
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_earliest_card_booking_start(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        statuses: tuple[int, ...] = (
            BookingStatus.BOOKED.value,
            BookingStatus.CHECKED_IN.value,
            BookingStatus.COMPLETED.value,
            BookingStatus.NO_SHOW.value,
        ),
    ) -> datetime | None:
        """返回该卡已存在的非取消预约中最早的排期开始时间（无则 None）

        F6.3 T6.3.2：期卡预期有效期窗口锚点 = 最早非取消预约的排期日。
        """
        query = (
            select(func.min(CourseSchedule.start_at))
            .select_from(Booking)
            .join(CourseSchedule, Booking.schedule_id == CourseSchedule.id)
            .where(
                Booking.membership_card_id == card_id,
                Booking.tenant_id == tenant_id,
                Booking.status.in_(statuses),
            )
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()


class BookingRescheduleRepository(TenantAwareRepository[BookingReschedule]):
    """改期 / 改派审计与幂等记录的数据访问层。

    所有查询都依赖 ORM 租户事件自动注入 ``tenant_id``（不手工叠加，
    避免与自动注入对抗）；本 Repository 不参与 JOIN 场景。
    """

    model_class = BookingReschedule

    async def get_by_request_key(
        self,
        db: AsyncSession,
        request_key: str,
    ) -> BookingReschedule | None:
        """按幂等键查询（租户内唯一）"""
        query = select(BookingReschedule).where(
            BookingReschedule.request_key == request_key
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_reschedule_by_old_booking(
        self,
        db: AsyncSession,
        old_booking_id: int,
    ) -> BookingReschedule | None:
        """查询旧预约的「改期」记录（固定 operation_type=reschedule）"""
        query = select(BookingReschedule).where(
            BookingReschedule.old_booking_id == old_booking_id,
            BookingReschedule.operation_type == "reschedule",
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_latest_by_old_booking(
        self,
        db: AsyncSession,
        old_booking_id: int,
    ) -> BookingReschedule | None:
        """查询旧预约的最新一条改期/改派记录（不限 operation_type）"""
        query = (
            select(BookingReschedule)
            .where(BookingReschedule.old_booking_id == old_booking_id)
            .order_by(
                BookingReschedule.created_at.desc(),
                BookingReschedule.id.desc(),
            )
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_new_booking(
        self,
        db: AsyncSession,
        new_booking_id: int,
    ) -> BookingReschedule | None:
        """查询新预约关联的最新一条审计记录"""
        query = (
            select(BookingReschedule)
            .where(BookingReschedule.new_booking_id == new_booking_id)
            .order_by(
                BookingReschedule.created_at.desc(),
                BookingReschedule.id.desc(),
            )
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_latest_card_swap(
        self,
        db: AsyncSession,
        old_booking_id: int,
    ) -> BookingReschedule | None:
        """查询旧预约的最新一条「同排期改派」记录"""
        query = (
            select(BookingReschedule)
            .where(
                BookingReschedule.old_booking_id == old_booking_id,
                BookingReschedule.operation_type == "card_swap",
            )
            .order_by(
                BookingReschedule.created_at.desc(),
                BookingReschedule.id.desc(),
            )
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
