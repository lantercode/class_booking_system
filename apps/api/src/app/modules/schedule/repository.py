"""
Schedule Repository - 排期数据访问层

提供排期相关的数据库操作，继承 TenantAwareRepository 实现自动多租户隔离。
"""

from typing import Optional, List, Tuple
from datetime import datetime

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.schedule.models import CourseSchedule, ScheduleStatus


class ScheduleRepository(TenantAwareRepository[CourseSchedule]):
    """排期数据访问层"""

    model_class = CourseSchedule

    async def search(
        self,
        db: AsyncSession,
        *,
        course_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
        classroom_id: Optional[int] = None,
        status: Optional[int] = None,
        start_from: Optional[datetime] = None,
        start_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[CourseSchedule], int]:
        """搜索排期（支持多条件筛选）"""
        base_query = select(CourseSchedule)
        count_query = select(func.count()).select_from(CourseSchedule)

        if course_id:
            base_query = base_query.where(CourseSchedule.course_id == course_id)
            count_query = count_query.where(CourseSchedule.course_id == course_id)

        if teacher_id:
            base_query = base_query.where(CourseSchedule.teacher_id == teacher_id)
            count_query = count_query.where(CourseSchedule.teacher_id == teacher_id)

        if classroom_id:
            base_query = base_query.where(CourseSchedule.classroom_id == classroom_id)
            count_query = count_query.where(CourseSchedule.classroom_id == classroom_id)

        if status is not None:
            base_query = base_query.where(CourseSchedule.status == status)
            count_query = count_query.where(CourseSchedule.status == status)

        if start_from:
            base_query = base_query.where(CourseSchedule.start_at >= start_from)
            count_query = count_query.where(CourseSchedule.start_at >= start_from)

        if start_to:
            base_query = base_query.where(CourseSchedule.start_at <= start_to)
            count_query = count_query.where(CourseSchedule.start_at <= start_to)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            base_query = base_query.where(CourseSchedule.tenant_id == tenant_id)
            count_query = count_query.where(CourseSchedule.tenant_id == tenant_id)

        base_query = base_query.order_by(CourseSchedule.start_at.asc())

        offset_val = (page - 1) * page_size
        base_query = base_query.offset(offset_val).limit(page_size)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        result = await db.execute(base_query)
        items = list(result.scalars().all())

        return items, total

    async def find_conflicts(
        self,
        db: AsyncSession,
        *,
        classroom_id: Optional[int] = None,
        teacher_id: Optional[int] = None,
        start_at: datetime,
        end_at: datetime,
        exclude_id: Optional[int] = None,
    ) -> List[CourseSchedule]:
        """检查时间冲突（同一教室或同一教师在同一时间段内是否有排期）"""
        from app.core.tenant_context import get_tenant_id

        conditions = [
            CourseSchedule.status == ScheduleStatus.NORMAL.value,
            CourseSchedule.start_at < end_at,
            CourseSchedule.end_at > start_at,
        ]

        tenant_id = get_tenant_id()
        if tenant_id:
            conditions.append(CourseSchedule.tenant_id == tenant_id)

        if exclude_id:
            conditions.append(CourseSchedule.id != exclude_id)

        classroom_conflicts = []
        teacher_conflicts = []

        if classroom_id:
            classroom_query = select(CourseSchedule).where(
                and_(*conditions, CourseSchedule.classroom_id == classroom_id)
            )
            result = await db.execute(classroom_query)
            classroom_conflicts = list(result.scalars().all())

        if teacher_id:
            teacher_query = select(CourseSchedule).where(
                and_(*conditions, CourseSchedule.teacher_id == teacher_id)
            )
            result = await db.execute(teacher_query)
            teacher_conflicts = list(result.scalars().all())

        all_conflicts = classroom_conflicts + teacher_conflicts
        seen_ids = set()
        unique_conflicts = []
        for c in all_conflicts:
            if c.id not in seen_ids:
                seen_ids.add(c.id)
                unique_conflicts.append(c)

        return unique_conflicts

    async def increment_booked_count(
        self,
        db: AsyncSession,
        schedule_id: int,
    ) -> bool:
        """预约人数 +1（原子操作）"""
        stmt = (
            select(CourseSchedule)
            .where(
                CourseSchedule.id == schedule_id,
                CourseSchedule.status == ScheduleStatus.NORMAL.value,
                CourseSchedule.booked_count < CourseSchedule.capacity,
            )
            .with_for_update()
        )
        result = await db.execute(stmt)
        schedule = result.scalar_one_or_none()

        if not schedule:
            return False

        schedule.booked_count += 1
        return True

    async def decrement_booked_count(
        self,
        db: AsyncSession,
        schedule_id: int,
    ) -> bool:
        """预约人数 -1（取消预约时调用）"""
        stmt = (
            select(CourseSchedule)
            .where(CourseSchedule.id == schedule_id)
            .with_for_update()
        )
        result = await db.execute(stmt)
        schedule = result.scalar_one_or_none()

        if not schedule:
            return False

        if schedule.booked_count > 0:
            schedule.booked_count -= 1
        return True