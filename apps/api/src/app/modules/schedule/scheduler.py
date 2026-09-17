"""
排期定时任务 - 自动标记过期排期为已完成、自动取消人数不足课程
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.booking.models import Booking, BookingStatus
from app.modules.course.models import Course, CourseType
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.schedule.service import ScheduleService

logger = logging.getLogger(__name__)

settings = get_settings()
schedule_service = ScheduleService()


async def auto_finish_expired_schedules():
    """
    自动将已结束的排期标记为 FINISHED

    执行逻辑:
    1. 找到 end_at + grace_period < now 且 status=NORMAL 的排期
    2. 将排期状态改为 FINISHED
    3. 关联预约状态流转:
       - CHECKED_IN(3) -> COMPLETED(4)   已签到的视为完成
       - BOOKED(1)     -> NO_SHOW(5)     约了没来的视为缺席
    """
    if not settings.AUTO_FINISH_ENABLED:
        return

    async with SessionLocal() as db:
        now = datetime.now(UTC)
        grace = timedelta(minutes=settings.AUTO_FINISH_GRACE_MINUTES)

        result = await db.execute(
            select(CourseSchedule).where(
                CourseSchedule.end_at < now - grace,
                CourseSchedule.status == ScheduleStatus.NORMAL.value,
            )
        )
        schedules = result.scalars().all()

        if not schedules:
            return

        schedule_ids = [s.id for s in schedules]
        logger.info(
            f"[定时任务] 发现 {len(schedule_ids)} 个已结束排期, "
            f"grace={settings.AUTO_FINISH_GRACE_MINUTES}min, ids={schedule_ids}"
        )

        for schedule in schedules:
            schedule.status = ScheduleStatus.FINISHED.value

        await db.execute(
            update(Booking)
            .where(
                Booking.schedule_id.in_(schedule_ids),
                Booking.status == BookingStatus.CHECKED_IN.value,
            )
            .values(status=BookingStatus.COMPLETED.value)
        )

        await db.execute(
            update(Booking)
            .where(
                Booking.schedule_id.in_(schedule_ids),
                Booking.status == BookingStatus.BOOKED.value,
            )
            .values(status=BookingStatus.NO_SHOW.value)
        )

        await db.commit()

        logger.info(f"[定时任务] 自动标记 {len(schedule_ids)} 个排期为已完成")


async def auto_cancel_underbooked_schedules():
    """
    自动取消人数不足的常规课

    执行逻辑:
    1. 找到 start_at - cancel_before_minutes < now 且 status=NORMAL 的排期
    2. 关联 course_types 表，筛选 min_students 不为 NULL 的类型
    3. 检查 booked_count < min_students
    4. 取消排期（自动处理学员预约和课时退还）
    5. 记录取消原因："预约人数不足（X/Y），系统自动取消"
    """
    if not getattr(settings, "AUTO_CANCEL_UNDERBOOKED_ENABLED", True):
        return

    async with SessionLocal() as db:
        now = datetime.now(UTC)

        # 查询需要检查的排期：
        # - 状态为 NORMAL
        # - 关联的课程类型设置了 min_students 和 cancel_before_minutes
        # - 当前时间已经到达或超过取消截止时间（start_at - cancel_before_minutes）
        # - 实际预约人数 < 最低人数
        query = (
            select(
                CourseSchedule.id,
                CourseSchedule.booked_count,
                CourseSchedule.start_at,
                CourseType.min_students,
                CourseType.cancel_before_minutes,
                CourseType.name.label("type_name"),
                Course.name.label("course_name"),
            )
            .join(Course, CourseSchedule.course_id == Course.id)
            .join(CourseType, Course.course_type_code == CourseType.code)
            .where(
                CourseSchedule.status == ScheduleStatus.NORMAL.value,
                CourseType.min_students.isnot(None),
                CourseType.cancel_before_minutes.isnot(None),
                CourseSchedule.start_at - timedelta(minutes=CourseType.cancel_before_minutes) <= now,
                CourseSchedule.booked_count < CourseType.min_students,
            )
        )

        result = await db.execute(query)
        rows = result.all()

        if not rows:
            return

        logger.info(
            f"[定时任务] 发现 {len(rows)} 个预约人数不足的排期，准备自动取消"
        )

        cancelled_count = 0
        failed_count = 0

        for row in rows:
            schedule_id = row.id
            booked = row.booked_count
            min_req = row.min_students
            cancel_minutes = row.cancel_before_minutes
            type_name = row.type_name
            course_name = row.course_name
            start_at = row.start_at

            try:
                cancel_reason = (
                    f"预约人数不足（{booked}/{min_req}），系统自动取消"
                )
                # 复用现有的 cancel_schedule 逻辑处理学员预约和课时退还
                await schedule_service.cancel_schedule(
                    db,
                    schedule_id=schedule_id,
                    cancel_reason=cancel_reason,
                    operator_id=0,  # 0 表示系统自动取消
                )
                cancelled_count += 1
                logger.info(
                    f"[定时任务] 自动取消排期 #{schedule_id}: "
                    f"{course_name}({type_name}), 已约{booked}人/最低{min_req}人, "
                    f"开课前{cancel_minutes}分钟不能取消"
                )
            except Exception as e:
                failed_count += 1
                logger.error(
                    f"[定时任务] 自动取消排期 #{schedule_id} 失败: {e}"
                )

        await db.commit()

        logger.info(
            f"[定时任务] 自动取消人数不足课程完成: "
            f"成功 {cancelled_count}, 失败 {failed_count}"
        )