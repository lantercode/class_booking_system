"""排期延迟任务投递（阶段 3）。

排期不再依赖周期性全表扫描：创建/变更时投递带 ``run_at`` 的延迟任务，
由 JobWorker 到点执行。幂等键按「排期 + 任务类型」固定，重复投递只会
覆盖 ``run_at``，不会重复执行。
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.course.models import Course, CourseType
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.task.repository import JobQueueRepository

logger = logging.getLogger(__name__)

job_repo = JobQueueRepository()


def finish_job_key(schedule_id: int) -> str:
    return f"schedule:{schedule_id}:complete"


def underbooked_job_key(schedule_id: int) -> str:
    return f"schedule:{schedule_id}:cancel_underbooked"


async def sync_schedule_jobs(db: AsyncSession, schedule: CourseSchedule) -> None:
    """按排期当前状态投递/覆盖两类延迟任务。

    - ``finish_schedule``：``end_at + grace`` 到点自动完成（含预约终态收口）；
    - ``cancel_schedule_if_underbooked``：``start_at - cancel_before`` 到点
      检查人数，不足则取消。

    非 NORMAL 排期不投递；``run_at`` 已过期时立即执行（补偿）。
    不 commit，由调用方控制事务边界。
    """
    if schedule.status != ScheduleStatus.NORMAL.value:
        return

    settings = get_settings()
    now = datetime.now(UTC)
    tenant_id = schedule.tenant_id

    if settings.AUTO_FINISH_ENABLED:
        grace = timedelta(minutes=settings.AUTO_FINISH_GRACE_MINUTES)
        await job_repo.upsert(
            db,
            tenant_id=tenant_id,
            type="finish_schedule",
            idempotency_key=finish_job_key(schedule.id),
            payload={"schedule_id": schedule.id},
            run_at=max(schedule.end_at + grace, now),
        )

    if getattr(settings, "AUTO_CANCEL_UNDERBOOKED_ENABLED", True):
        row = (
            await db.execute(
                select(CourseType.min_students, CourseType.cancel_before_minutes)
                .join(Course, Course.course_type_code == CourseType.code)
                .where(Course.id == schedule.course_id)
            )
        ).first()
        if row and row.min_students and row.cancel_before_minutes:
            await job_repo.upsert(
                db,
                tenant_id=tenant_id,
                type="cancel_schedule_if_underbooked",
                idempotency_key=underbooked_job_key(schedule.id),
                payload={
                    "schedule_id": schedule.id,
                    "min_students": row.min_students,
                },
                run_at=max(
                    schedule.start_at - timedelta(minutes=row.cancel_before_minutes), now
                ),
            )


async def safe_sync_schedule_jobs(db: AsyncSession, schedule: CourseSchedule) -> None:
    """业务提交后安全投递：失败仅记录日志，不影响主流程与返回对象。"""
    try:
        async with db.begin_nested():
            await sync_schedule_jobs(db, schedule)
        await db.commit()
    except Exception as e:
        logger.exception(
            "[schedule_jobs] 投递排期延迟任务失败 schedule=%s: %s", schedule.id, e
        )


async def cancel_schedule_jobs(db: AsyncSession, schedule: CourseSchedule) -> None:
    """排期取消时撤销其未执行的延迟任务（running 任务由 handler 状态守卫兜底）。"""
    try:
        await job_repo.cancel_pending(
            db,
            tenant_id=schedule.tenant_id,
            idempotency_keys=[
                finish_job_key(schedule.id),
                underbooked_job_key(schedule.id),
            ],
        )
        await db.commit()
    except Exception as e:
        logger.exception(
            "[schedule_jobs] 撤销排期延迟任务失败 schedule=%s: %s", schedule.id, e
        )
