"""排期延迟任务投递（阶段 3）。

排期不再依赖周期性全表扫描：创建/变更时投递带 ``run_at`` 的延迟任务，
由 JobWorker 到点执行。幂等键按「排期 + 任务类型」固定，重复投递只会
覆盖 ``run_at``，不会重复执行。
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.tenant_context import set_tenant_id
from app.modules.course.models import Course, CourseType
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.task.repository import JobQueueRepository
from app.modules.tenant.models import Tenant, TenantStatus

logger = logging.getLogger(__name__)

job_repo = JobQueueRepository()


def finish_job_key(schedule_id: int) -> str:
    return f"schedule:{schedule_id}:complete"


def underbooked_job_key(schedule_id: int) -> str:
    return f"schedule:{schedule_id}:cancel_underbooked"


def _job_specs(
    *,
    schedule_id: int,
    start_at: datetime,
    end_at: datetime,
    min_students: int | None,
    cancel_before_minutes: int | None,
    now: datetime,
) -> list[tuple[str, str, dict[str, Any], datetime]]:
    """按当前配置计算排期应投递的延迟任务（类型 / 幂等键 / payload / run_at）。"""
    settings = get_settings()
    specs: list[tuple[str, str, dict[str, Any], datetime]] = []

    if settings.AUTO_FINISH_ENABLED:
        grace = timedelta(minutes=settings.AUTO_FINISH_GRACE_MINUTES)
        specs.append(
            (
                "finish_schedule",
                finish_job_key(schedule_id),
                {"schedule_id": schedule_id},
                max(end_at + grace, now),
            )
        )

    if (
        getattr(settings, "AUTO_CANCEL_UNDERBOOKED_ENABLED", True)
        and min_students
        and cancel_before_minutes
    ):
        specs.append(
            (
                "cancel_schedule_if_underbooked",
                underbooked_job_key(schedule_id),
                {"schedule_id": schedule_id, "min_students": min_students},
                max(start_at - timedelta(minutes=cancel_before_minutes), now),
            )
        )

    return specs


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

    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(CourseType.min_students, CourseType.cancel_before_minutes)
            .join(Course, Course.course_type_code == CourseType.code)
            .where(Course.id == schedule.course_id)
        )
    ).first()

    for type_, key, payload, run_at in _job_specs(
        schedule_id=schedule.id,
        start_at=schedule.start_at,
        end_at=schedule.end_at,
        min_students=row.min_students if row else None,
        cancel_before_minutes=row.cancel_before_minutes if row else None,
        now=now,
    ):
        await job_repo.upsert(
            db,
            tenant_id=schedule.tenant_id,
            type=type_,
            idempotency_key=key,
            payload=payload,
            run_at=run_at,
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


async def _active_tenant_ids() -> list[int]:
    """对账/补投用的 ACTIVE 租户列表（独立会话，不依赖请求上下文）。"""
    async with SessionLocal() as db:
        return list(
            (
                await db.execute(
                    select(Tenant.id).where(Tenant.status == TenantStatus.ACTIVE.value)
                )
            )
            .scalars()
            .all()
        )


async def backfill_schedule_jobs() -> dict[str, int]:
    """为存量 NORMAL 排期补齐延迟任务（灰度上线 / 漏投补偿）。

    启用 Worker 后旧扫描任务下线，上线前已存在的排期没有对应的 ``job_queue``
    记录，会失去「自动完成 / 人数不足取消」。本任务逐租户扫描 NORMAL 排期，
    对**不存在**的任务做插入（``enqueue`` = ON CONFLICT DO NOTHING），因此：

    - 可重复执行，已投递（含已执行）的任务不会被重置或反复处理；
    - 已过期的 ``run_at`` 立即执行，完成一次性补偿。

    ``TASK_WORKER_ENABLED=false`` 时直接返回（旧扫描仍在工作）。
    """
    if not get_settings().TASK_WORKER_ENABLED:
        return {"tenants": 0, "schedules": 0, "enqueued": 0}

    stats = {"tenants": 0, "schedules": 0, "enqueued": 0}
    now = datetime.now(UTC)

    for tenant_id in await _active_tenant_ids():
        set_tenant_id(tenant_id)
        stats["tenants"] += 1
        try:
            async with SessionLocal() as db:
                rows = (
                    await db.execute(
                        select(
                            CourseSchedule.id,
                            CourseSchedule.start_at,
                            CourseSchedule.end_at,
                            CourseType.min_students,
                            CourseType.cancel_before_minutes,
                        )
                        .join(Course, CourseSchedule.course_id == Course.id)
                        .outerjoin(
                            CourseType, Course.course_type_code == CourseType.code
                        )
                        .where(
                            CourseSchedule.tenant_id == tenant_id,
                            CourseSchedule.status == ScheduleStatus.NORMAL.value,
                        )
                    )
                ).all()

                for row in rows:
                    stats["schedules"] += 1
                    for type_, key, payload, run_at in _job_specs(
                        schedule_id=row.id,
                        start_at=row.start_at,
                        end_at=row.end_at,
                        min_students=row.min_students,
                        cancel_before_minutes=row.cancel_before_minutes,
                        now=now,
                    ):
                        job = await job_repo.enqueue(
                            db,
                            tenant_id=tenant_id,
                            type=type_,
                            idempotency_key=key,
                            payload=payload,
                            run_at=run_at,
                        )
                        if job is not None:
                            stats["enqueued"] += 1
                await db.commit()
        except Exception:
            logger.exception("[schedule_jobs] 租户%s 存量排期补投失败，已跳过", tenant_id)
        finally:
            set_tenant_id(None)

    logger.info("[schedule_jobs] 存量排期补投完成: %s", stats)
    return stats
