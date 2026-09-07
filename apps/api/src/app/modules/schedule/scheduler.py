"""
排期定时任务 - 自动标记过期排期为已完成
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.booking.models import Booking, BookingStatus
from app.modules.schedule.models import CourseSchedule, ScheduleStatus

logger = logging.getLogger(__name__)

settings = get_settings()


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
            update(Booking).where(
                Booking.schedule_id.in_(schedule_ids),
                Booking.status == BookingStatus.CHECKED_IN.value,
            ).values(status=BookingStatus.COMPLETED.value)
        )

        await db.execute(
            update(Booking).where(
                Booking.schedule_id.in_(schedule_ids),
                Booking.status == BookingStatus.BOOKED.value,
            ).values(status=BookingStatus.NO_SHOW.value)
        )

        await db.commit()

        logger.info(
            f"[定时任务] 自动标记 {len(schedule_ids)} 个排期为已完成"
        )
