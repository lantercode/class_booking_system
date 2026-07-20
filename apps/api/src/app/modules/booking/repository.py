"""
Booking Repository - 预约数据访问层

提供预约相关的数据库操作，继承 TenantAwareRepository 实现自动多租户隔离。
"""

from typing import Optional, List, Tuple
from datetime import datetime

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.booking.models import Booking, BookingStatus


class BookingRepository(TenantAwareRepository[Booking]):
    """预约数据访问层"""

    model_class = Booking

    async def search(
        self,
        db: AsyncSession,
        *,
        schedule_id: Optional[int] = None,
        student_id: Optional[int] = None,
        status: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Booking], int]:
        """搜索预约（支持多条件筛选）"""
        base_query = select(Booking)
        count_query = select(func.count()).select_from(Booking)

        if schedule_id:
            base_query = base_query.where(Booking.schedule_id == schedule_id)
            count_query = count_query.where(Booking.schedule_id == schedule_id)

        if student_id:
            base_query = base_query.where(Booking.student_id == student_id)
            count_query = count_query.where(Booking.student_id == student_id)

        if status is not None:
            base_query = base_query.where(Booking.status == status)
            count_query = count_query.where(Booking.status == status)

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

    async def find_active_booking(
        self,
        db: AsyncSession,
        schedule_id: int,
        student_id: int,
    ) -> Optional[Booking]:
        """查找学员在指定排期的有效预约（已预约/已签到/已完成）"""
        from app.core.tenant_context import get_tenant_id

        query = select(Booking).where(
            and_(
                Booking.schedule_id == schedule_id,
                Booking.student_id == student_id,
                Booking.status.in_([
                    BookingStatus.BOOKED.value,
                    BookingStatus.CHECKED_IN.value,
                    BookingStatus.COMPLETED.value,
                ]),
            )
        )

        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Booking.tenant_id == tenant_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def count_active_bookings(
        self,
        db: AsyncSession,
        schedule_id: int,
    ) -> int:
        """统计排期的有效预约人数"""
        query = select(func.count()).select_from(Booking).where(
            and_(
                Booking.schedule_id == schedule_id,
                Booking.status.in_([
                    BookingStatus.BOOKED.value,
                    BookingStatus.CHECKED_IN.value,
                    BookingStatus.COMPLETED.value,
                ]),
            )
        )

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Booking.tenant_id == tenant_id)

        result = await db.execute(query)
        return result.scalar() or 0