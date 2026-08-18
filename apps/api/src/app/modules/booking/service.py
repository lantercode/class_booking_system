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
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.booking.repository import BookingRepository
from app.modules.schedule.repository import ScheduleRepository
from app.modules.user.repository import UserRepository
from app.modules.booking.models import Booking, BookingStatus, BookingSource
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.user.models import User
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

        # 校验：排期是否已开始
        if schedule.start_at and now > schedule.start_at:
            raise BusinessException("该课程已开始，无法预约", code=400)

        # 校验：是否超过预约窗口（最多未来两周）
        max_booking_date = now + timedelta(days=14)
        if schedule.start_at and schedule.start_at > max_booking_date:
            raise BusinessException("只能预约未来两周内的课程", code=400)

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

        return await self._do_cancel_booking(db, booking, reason)

    async def cancel_booking_by_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
        student_id: int,
        reason: Optional[str] = None,
    ) -> BookingResponse:
        """通过排期ID取消预约（学员端）"""
        logger.warning(f"[BookingService] 通过排期ID取消预约: schedule_id={schedule_id}, student_id={student_id}")

        booking = await self.repo.find_by_schedule_and_student(db, schedule_id, student_id)
        if not booking:
            raise NotFoundException("预约不存在")

        return await self._do_cancel_booking(db, booking, reason)

    async def _do_cancel_booking(
        self,
        db: AsyncSession,
        booking: Booking,
        reason: Optional[str] = None,
    ) -> BookingResponse:
        """执行取消预约操作"""
        if booking.status == BookingStatus.CANCELLED.value:
            raise BusinessException("预约已取消", code=400)

        if booking.status in [BookingStatus.CHECKED_IN.value, BookingStatus.COMPLETED.value]:
            raise BusinessException("已签到/已完成的预约无法取消", code=400)

        schedule = await self.schedule_repo.get_by_id(db, booking.schedule_id)
        if schedule:
            if schedule.cancel_deadline and datetime.now(timezone.utc) > schedule.cancel_deadline:
                raise BusinessException("已超过取消截止时间", code=400)
            
            time_diff = schedule.start_at - datetime.now(timezone.utc)
            if time_diff.total_seconds() < 90 * 60:
                raise BusinessException("开课前90分钟内不可取消预约", code=400)

        booking.status = BookingStatus.CANCELLED.value
        booking.cancelled_at = datetime.now(timezone.utc)
        if reason:
            booking.cancelled_reason = reason

        await self.schedule_repo.decrement_booked_count(db, booking.schedule_id)

        await db.commit()
        await db.refresh(booking)

        logger.warning(f"[BookingService] ✅ 预约已取消: id={booking.id}")
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
        booking.checked_in_at = datetime.now(timezone.utc)

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
        schedule_map = await self._get_schedule_info_map(db, [booking.schedule_id])
        return self._to_response(booking, schedule_info=schedule_map.get(booking.schedule_id))

    async def list_bookings(
        self,
        db: AsyncSession,
        *,
        schedule_id: Optional[int] = None,
        student_id: Optional[int] = None,
        status: Optional[int] = None,
        statuses: Optional[List[int]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> BookingListResponse:
        """获取预约列表（分页）"""
        items, total = await self.repo.search(
            db,
            schedule_id=schedule_id,
            student_id=student_id,
            status=status,
            statuses=statuses,
            page=page,
            page_size=page_size,
        )

        # 获取所有学员ID并批量查询学员信息
        student_ids = list({b.student_id for b in items})
        student_map = await self._get_student_info_map(db, student_ids)

        # 获取所有排期ID并批量查询排期关联信息（课程名、教室名、教师名、时间）
        schedule_ids = list({b.schedule_id for b in items})
        schedule_map = await self._get_schedule_info_map(db, schedule_ids)

        return BookingListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[self._to_response(b, student_map.get(b.student_id), schedule_map.get(b.schedule_id)) for b in items],
        )

    async def _get_student_info_map(self, db: AsyncSession, student_ids: List[int]) -> Dict[int, Tuple[str, str]]:
        """批量获取学员信息映射"""
        if not student_ids:
            return {}
        
        user_repo = UserRepository()
        query = select(User).where(User.id.in_(student_ids))
        result = await db.execute(query)
        users = result.scalars().all()
        
        return {
            user.id: (user.nickname, user.phone)
            for user in users
        }

    async def _get_schedule_info_map(self, db: AsyncSession, schedule_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """批量获取排期关联信息（课程名、教室名、教师名、时间）"""
        if not schedule_ids:
            return {}

        from app.modules.schedule.models import CourseSchedule
        from app.modules.course.models import Course, Classroom
        from app.modules.user.models import User

        query = (
            select(
                CourseSchedule.id,
                CourseSchedule.start_at,
                CourseSchedule.end_at,
                CourseSchedule.teacher_id,
                CourseSchedule.classroom_id,
                Course.name.label("course_name"),
                Classroom.name.label("classroom_name"),
            )
            .outerjoin(Course, CourseSchedule.course_id == Course.id)
            .outerjoin(Classroom, CourseSchedule.classroom_id == Classroom.id)
            .where(CourseSchedule.id.in_(schedule_ids))
        )
        result = await db.execute(query)
        rows = result.all()

        teacher_ids = [row.teacher_id for row in rows if row.teacher_id]
        teacher_map = {}
        if teacher_ids:
            teacher_query = select(User.id, User.nickname).where(User.id.in_(teacher_ids))
            teacher_result = await db.execute(teacher_query)
            teacher_map = {row.id: row.nickname for row in teacher_result.all()}

        return {
            row.id: {
                "start_at": row.start_at,
                "end_at": row.end_at,
                "course_name": row.course_name,
                "classroom_name": row.classroom_name,
                "teacher_name": teacher_map.get(row.teacher_id),
            }
            for row in rows
        }

    def _to_response(self, booking: Booking, student_info: Optional[Tuple[str, str]] = None, schedule_info: Optional[Dict[str, Any]] = None) -> BookingResponse:
        """将 ORM 模型转换为响应对象"""
        nickname, phone = student_info if student_info else (None, None)
        schedule_info = schedule_info or {}
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
            student_nickname=nickname,
            student_phone=phone,
            course_name=schedule_info.get("course_name"),
            start_at=schedule_info.get("start_at"),
            end_at=schedule_info.get("end_at"),
            classroom_name=schedule_info.get("classroom_name"),
            teacher_name=schedule_info.get("teacher_name"),
        )