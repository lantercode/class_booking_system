"""
Schedule Service - 排期业务逻辑层

处理排期管理的核心业务逻辑，包括时间冲突校验。
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.schedule.repository import ScheduleRepository
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.schedule.schemas import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduleListResponse,
)
from app.modules.classroom.repository import ClassroomRepository
from app.core.exceptions import ValidationException, NotFoundException, BusinessException

logger = logging.getLogger(__name__)


class ScheduleService:
    """排期管理服务"""

    def __init__(self):
        self.repo = ScheduleRepository()

    async def create_schedule(
        self,
        db: AsyncSession,
        data: ScheduleCreate,
        operator_id: Optional[int] = None,
    ) -> ScheduleResponse:
        """创建排期"""
        logger.info(
            f"[ScheduleService] 创建排期: course_id={data.course_id}, "
            f"teacher_id={data.teacher_id}, start={data.start_at}"
        )

        if data.end_at <= data.start_at:
            raise ValidationException("结束时间必须晚于开始时间")

        if data.classroom_id is not None:
            classroom_repo = ClassroomRepository()
            classroom = await classroom_repo.get_by_id(db, data.classroom_id)
            if not classroom:
                raise NotFoundException("教室不存在")
            if classroom.status != 1:
                raise ValidationException("该教室正在维护中，暂不可用")

        conflicts = await self.repo.find_conflicts(
            db,
            classroom_id=data.classroom_id,
            teacher_id=data.teacher_id,
            start_at=data.start_at,
            end_at=data.end_at,
        )
        if conflicts:
            conflict_info = ", ".join(
                f"排期#{c.id}({c.start_at}~{c.end_at})" for c in conflicts
            )
            raise BusinessException(f"存在时间冲突: {conflict_info}", code=400)

        schedule_data: Dict[str, Any] = {
            "course_id": data.course_id,
            "teacher_id": data.teacher_id,
            "start_at": data.start_at,
            "end_at": data.end_at,
            "capacity": data.capacity,
            "status": ScheduleStatus.NORMAL.value,
        }
        if data.classroom_id is not None:
            schedule_data["classroom_id"] = data.classroom_id
        if data.booking_opens_at is not None:
            schedule_data["booking_opens_at"] = data.booking_opens_at
        if data.booking_closes_at is not None:
            schedule_data["booking_closes_at"] = data.booking_closes_at
        if data.cancel_deadline is not None:
            schedule_data["cancel_deadline"] = data.cancel_deadline
        if data.notes is not None:
            schedule_data["notes"] = data.notes

        schedule = await self.repo.create(db, schedule_data)
        await db.commit()
        await db.refresh(schedule)

        logger.info(f"[ScheduleService] ✅ 排期创建成功: id={schedule.id}")
        return self._to_response(schedule)

    async def update_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
        data: ScheduleUpdate,
    ) -> ScheduleResponse:
        """更新排期"""
        logger.info(f"[ScheduleService] 更新排期: schedule_id={schedule_id}")

        schedule = await self.repo.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException("排期不存在")

        update_data: Dict[str, Any] = {}

        if data.course_id is not None:
            update_data["course_id"] = data.course_id
        if data.teacher_id is not None:
            update_data["teacher_id"] = data.teacher_id
        if data.classroom_id is not None:
            update_data["classroom_id"] = data.classroom_id
        if data.capacity is not None:
            if data.capacity < schedule.booked_count:
                raise ValidationException(f"容量不能小于已预约人数({schedule.booked_count})")
            update_data["capacity"] = data.capacity
        if data.status is not None:
            update_data["status"] = data.status
        if data.notes is not None:
            update_data["notes"] = data.notes

        start_at = data.start_at if data.start_at is not None else schedule.start_at
        end_at = data.end_at if data.end_at is not None else schedule.end_at

        if data.start_at is not None:
            update_data["start_at"] = data.start_at
        if data.end_at is not None:
            update_data["end_at"] = data.end_at

        if end_at <= start_at:
            raise ValidationException("结束时间必须晚于开始时间")

        classroom_id = data.classroom_id if data.classroom_id is not None else schedule.classroom_id
        teacher_id = data.teacher_id if data.teacher_id is not None else schedule.teacher_id

        if classroom_id is not None and data.classroom_id is not None:
            classroom_repo = ClassroomRepository()
            classroom = await classroom_repo.get_by_id(db, classroom_id)
            if not classroom:
                raise NotFoundException("教室不存在")
            if classroom.status != 1:
                raise ValidationException("该教室正在维护中，暂不可用")

        conflicts = await self.repo.find_conflicts(
            db,
            classroom_id=classroom_id,
            teacher_id=teacher_id,
            start_at=start_at,
            end_at=end_at,
            exclude_id=schedule_id,
        )
        if conflicts:
            conflict_info = ", ".join(
                f"排期#{c.id}({c.start_at}~{c.end_at})" for c in conflicts
            )
            raise BusinessException(f"存在时间冲突: {conflict_info}", code=400)

        if update_data:
            schedule = await self.repo.update(db, schedule_id, update_data)

        await db.commit()
        await db.refresh(schedule)

        logger.info(f"[ScheduleService] ✅ 排期更新成功: id={schedule_id}")
        return self._to_response(schedule)

    async def cancel_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
    ) -> ScheduleResponse:
        """取消排期"""
        logger.warning(f"[ScheduleService] 取消排期: schedule_id={schedule_id}")

        schedule = await self.repo.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException("排期不存在")

        if schedule.status == ScheduleStatus.CANCELLED.value:
            raise BusinessException("排期已取消")

        schedule = await self.repo.update(
            db, schedule_id, {"status": ScheduleStatus.CANCELLED.value}
        )
        await db.commit()
        await db.refresh(schedule)

        logger.warning(f"[ScheduleService] ✅ 排期已取消: id={schedule_id}")
        return self._to_response(schedule)

    async def get_schedule_by_id(
        self,
        db: AsyncSession,
        schedule_id: int,
    ) -> ScheduleResponse:
        """获取排期详情"""
        schedule = await self.repo.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException("排期不存在")
        return self._to_response(schedule)

    async def list_schedules(
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
    ) -> ScheduleListResponse:
        """获取排期列表（分页）"""
        items, total = await self.repo.search(
            db,
            course_id=course_id,
            teacher_id=teacher_id,
            classroom_id=classroom_id,
            status=status,
            start_from=start_from,
            start_to=start_to,
            page=page,
            page_size=page_size,
        )

        return ScheduleListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[self._to_response(s) for s in items],
        )

    def _to_response(self, schedule: CourseSchedule) -> ScheduleResponse:
        """将 ORM 模型转换为响应对象"""
        return ScheduleResponse(
            id=schedule.id,
            public_id=str(schedule.public_id),
            tenant_id=schedule.tenant_id,
            course_id=schedule.course_id,
            teacher_id=schedule.teacher_id,
            classroom_id=schedule.classroom_id,
            start_at=schedule.start_at,
            end_at=schedule.end_at,
            capacity=schedule.capacity,
            booked_count=schedule.booked_count,
            booking_opens_at=schedule.booking_opens_at,
            booking_closes_at=schedule.booking_closes_at,
            cancel_deadline=schedule.cancel_deadline,
            status=schedule.status,
            notes=schedule.notes,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )