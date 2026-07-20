"""
Booking Service - 预约业务逻辑层

处理预约管理的核心业务逻辑，包括：
- 容量校验
- 重复预约检测
- 预约人数原子更新
- 取消预约
- 签到/完成
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.booking.repository import BookingRepository
from app.modules.schedule.repository import ScheduleRepository
from app.modules.booking.models import Booking, BookingStatus, BookingSource
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.booking.schemas import (
    BookingCreate,
    BookingUpdate,
    BookingResponse,
    BookingListResponse,
)
from app.core.exceptions import ValidationException, NotFoundException, BusinessException, PermissionException

logger = logging.getLogger(__name__)


class BookingService:
    """预约管理服务"""

    def __init__(self):
        self.repo = BookingRepository()
        self.schedule_repo = ScheduleRepository()

    async def create_booking(
        self,
        db: AsyncSession,
        data: BookingCreate,
        student_id: int,
        operator_id: Optional[int] = None,
    ) -> BookingResponse:
        """创建预约"""
        logger.info(
            f"[BookingService] 创建预约: schedule_id={data.schedule_id}, "
            f"student_id={student_id}"
        )

        schedule = await self.schedule_repo.get_by_id(db, data.schedule_id)
        if not schedule:
            raise NotFoundException("排期不存在")

        if schedule.status != ScheduleStatus.NORMAL.value:
            raise BusinessException("该排期已取消或已完成，无法预约", code=400)

        if schedule.booked_count >= schedule.capacity:
            raise BusinessException("该排期已约满", code=400)

        now = datetime.utcnow()
        if schedule.booking_opens_at and now < schedule.booking_opens_at:
            raise BusinessException("预约尚未开放", code=400)
        if schedule.booking_closes_at and now > schedule.booking_closes_at:
            raise BusinessException("预约已截止", code=400)

        existing = await self.repo.find_active_booking(
            db, data.schedule_id, student_id
        )
        if existing:
            raise BusinessException("您已预约该排期，请勿重复预约", code=400)

        success = await self.schedule_repo.increment_booked_count(
            db, data.schedule_id
        )
        if not success:
            raise BusinessException("预约失败，排期可能已满或已取消", code=400)

        source = data.source or BookingSource.SELF.value
        if source not in [s.value for s in BookingSource]:
            raise ValidationException(f"无效的预约来源: {source}")

        booking_data: Dict[str, Any] = {
            "schedule_id": data.schedule_id,
            "student_id": student_id,
            "status": BookingStatus.BOOKED.value,
            "source": source,
        }
        if data.membership_card_id is not None:
            booking_data["membership_card_id"] = data.membership_card_id

        booking = await self.repo.create(db, booking_data)
        await db.commit()
        await db.refresh(booking)

        logger.info(f"[BookingService] ✅ 预约创建成功: id={booking.id}")
        return self._to_response(booking)

    async def cancel_booking(
        self,
        db: AsyncSession,
        booking_id: int,
        student_id: int,
        reason: Optional[str] = None,
    ) -> BookingResponse:
        """取消预约"""
        logger.warning(f"[BookingService] 取消预约: booking_id={booking_id}")

        booking = await self.repo.get_by_id(db, booking_id)
        if not booking:
            raise NotFoundException("预约不存在")

        if booking.student_id != student_id:
            raise PermissionException("只能取消自己的预约")

        if booking.status == BookingStatus.CANCELLED.value:
            raise BusinessException("预约已取消", code=400)

        if booking.status in [BookingStatus.CHECKED_IN.value, BookingStatus.COMPLETED.value]:
            raise BusinessException("已签到/已完成的预约无法取消", code=400)

        schedule = await self.schedule_repo.get_by_id(db, booking.schedule_id)
        if schedule and schedule.cancel_deadline:
            if datetime.utcnow() > schedule.cancel_deadline:
                raise BusinessException("已超过取消截止时间", code=400)

        booking.status = BookingStatus.CANCELLED.value
        booking.cancelled_at = datetime.utcnow()
        if reason:
            booking.cancelled_reason = reason

        await self.schedule_repo.decrement_booked_count(db, booking.schedule_id)

        await db.commit()
        await db.refresh(booking)

        logger.warning(f"[BookingService] ✅ 预约已取消: id={booking_id}")
        return self._to_response(booking)

    async def check_in_booking(
        self,
        db: AsyncSession,
        booking_id: int,
    ) -> BookingResponse:
        """签到"""
        logger.info(f"[BookingService] 签到: booking_id={booking_id}")

        booking = await self.repo.get_by_id(db, booking_id)
        if not booking:
            raise NotFoundException("预约不存在")

        if booking.status != BookingStatus.BOOKED.value:
            raise BusinessException("当前预约状态无法签到", code=400)

        booking.status = BookingStatus.CHECKED_IN.value
        booking.checked_in_at = datetime.utcnow()

        await db.commit()
        await db.refresh(booking)

        logger.info(f"[BookingService] ✅ 签到成功: id={booking_id}")
        return self._to_response(booking)

    async def complete_booking(
        self,
        db: AsyncSession,
        booking_id: int,
    ) -> BookingResponse:
        """完成课程"""
        logger.info(f"[BookingService] 完成课程: booking_id={booking_id}")

        booking = await self.repo.get_by_id(db, booking_id)
        if not booking:
            raise NotFoundException("预约不存在")

        if booking.status not in [BookingStatus.BOOKED.value, BookingStatus.CHECKED_IN.value]:
            raise BusinessException("当前预约状态无法完成", code=400)

        booking.status = BookingStatus.COMPLETED.value

        await db.commit()
        await db.refresh(booking)

        logger.info(f"[BookingService] ✅ 课程完成: id={booking_id}")
        return self._to_response(booking)

    async def get_booking_by_id(
        self,
        db: AsyncSession,
        booking_id: int,
    ) -> BookingResponse:
        """获取预约详情"""
        booking = await self.repo.get_by_id(db, booking_id)
        if not booking:
            raise NotFoundException("预约不存在")
        return self._to_response(booking)

    async def list_bookings(
        self,
        db: AsyncSession,
        *,
        schedule_id: Optional[int] = None,
        student_id: Optional[int] = None,
        status: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> BookingListResponse:
        """获取预约列表（分页）"""
        items, total = await self.repo.search(
            db,
            schedule_id=schedule_id,
            student_id=student_id,
            status=status,
            page=page,
            page_size=page_size,
        )

        return BookingListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[self._to_response(b) for b in items],
        )

    def _to_response(self, booking: Booking) -> BookingResponse:
        """将 ORM 模型转换为响应对象"""
        return BookingResponse(
            id=booking.id,
            public_id=str(booking.public_id),
            tenant_id=booking.tenant_id,
            schedule_id=booking.schedule_id,
            student_id=booking.student_id,
            status=booking.status,
            source=booking.source,
            membership_card_id=booking.membership_card_id,
            booked_at=booking.booked_at,
            cancelled_at=booking.cancelled_at,
            cancelled_reason=booking.cancelled_reason,
            checked_in_at=booking.checked_in_at,
            created_at=booking.created_at,
            updated_at=booking.updated_at,
        )