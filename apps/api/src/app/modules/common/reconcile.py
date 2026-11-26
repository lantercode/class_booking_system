"""派生状态对账（阶段 6.2）。

只读比对「按时间派生出的状态」与「数据库落库状态」，输出差异数量，
用于灰度期判断是否可下线旧扫描任务。**不修改任何数据**。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import Booking, BookingStatus
from app.modules.course.models import Course, CourseType
from app.modules.membership.models import CardStatus, CardType, MembershipCard
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.tenant.models import Tenant, TenantStatus

logger = logging.getLogger(__name__)


async def _count_diffs(
    db: AsyncSession, tenant_id: int, *, now: datetime, grace: timedelta
) -> dict[str, int]:
    """统计单个租户的派生状态差异（只读）。"""
    settings = get_settings()

    # 1) 排期：已过 end_at + grace 但仍为 NORMAL
    stale_schedules = (
        await db.execute(
            select(CourseSchedule.id).where(
                CourseSchedule.tenant_id == tenant_id,
                CourseSchedule.status == ScheduleStatus.NORMAL.value,
                CourseSchedule.end_at + grace < now,
            )
        )
    ).scalars().all()

    # 2) 会员卡：已过 expire_at 但仍为 ACTIVE/PENDING
    expired_cards = (
        await db.execute(
            select(MembershipCard.id).where(
                MembershipCard.tenant_id == tenant_id,
                MembershipCard.expire_at.isnot(None),
                MembershipCard.expire_at < now,
                MembershipCard.status.in_(
                    [CardStatus.ACTIVE.value, CardStatus.PENDING.value]
                ),
            )
        )
    ).scalars().all()

    # 3) 会员卡：已到 valid_from 但仍为 PENDING
    activatable_cards = (
        await db.execute(
            select(MembershipCard.id).where(
                MembershipCard.tenant_id == tenant_id,
                MembershipCard.status == CardStatus.PENDING.value,
                MembershipCard.valid_from.isnot(None),
                MembershipCard.valid_from <= now,
            )
        )
    ).scalars().all()

    # 4) 会员卡：冻结已到期但仍为 FROZEN
    unfreezable_cards = (
        await db.execute(
            select(MembershipCard.id).where(
                MembershipCard.tenant_id == tenant_id,
                MembershipCard.status == CardStatus.FROZEN.value,
                MembershipCard.frozen_until.isnot(None),
                MembershipCard.frozen_until <= now,
            )
        )
    ).scalars().all()

    # 5) 期卡：超期未激活且从未使用，但仍为 PENDING（应被作废）
    #    作废开关关闭时不比对，避免把「预期保留 PENDING」误报成差异。
    if settings.PENDING_CARD_CANCEL_ENABLED:
        cutoff = now - timedelta(days=settings.PENDING_CARD_CANCEL_DAYS)
        used_booking = (
            select(Booking.id)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.membership_card_id == MembershipCard.id,
                Booking.status.in_(
                    [
                        BookingStatus.COMPLETED.value,
                        BookingStatus.NO_SHOW.value,
                    ]
                ),
            )
            .exists()
        )
        cancelable_pending_cards = (
            await db.execute(
                select(MembershipCard.id).where(
                    MembershipCard.tenant_id == tenant_id,
                    MembershipCard.card_type == CardType.PERIOD.value,
                    MembershipCard.status == CardStatus.PENDING.value,
                    MembershipCard.created_at < cutoff,
                    ~used_booking,
                )
            )
        ).scalars().all()
    else:
        cancelable_pending_cards = []

    # 6) 排期：已过「开课前 N 分钟」截止点且人数不足，但仍为 NORMAL（应被取消）
    if getattr(settings, "AUTO_CANCEL_UNDERBOOKED_ENABLED", True):
        underbooked_schedules = (
            await db.execute(
                select(CourseSchedule.id)
                .join(Course, CourseSchedule.course_id == Course.id)
                .join(CourseType, Course.course_type_code == CourseType.code)
                .where(
                    CourseSchedule.tenant_id == tenant_id,
                    CourseSchedule.status == ScheduleStatus.NORMAL.value,
                    CourseType.min_students.isnot(None),
                    CourseType.cancel_before_minutes.isnot(None),
                    CourseSchedule.booked_count < CourseType.min_students,
                    CourseSchedule.start_at
                    - func.make_interval(
                        0, 0, 0, 0, 0, CourseType.cancel_before_minutes
                    )
                    <= now,
                )
            )
        ).scalars().all()
    else:
        underbooked_schedules = []

    return {
        "schedule_finish_diff": len(stale_schedules),
        "card_expired_diff": len(expired_cards),
        "card_activate_diff": len(activatable_cards),
        "card_unfreeze_diff": len(unfreezable_cards),
        "card_cancel_pending_diff": len(cancelable_pending_cards),
        "schedule_underbooked_diff": len(underbooked_schedules),
    }


async def reconcile_derived_status() -> dict[str, int]:
    """逐租户比对排期/会员卡状态，返回差异统计（含 total 键）。"""
    settings = get_settings()
    grace = timedelta(minutes=settings.AUTO_FINISH_GRACE_MINUTES)
    totals = {
        "schedule_finish_diff": 0,
        "card_expired_diff": 0,
        "card_activate_diff": 0,
        "card_unfreeze_diff": 0,
        "card_cancel_pending_diff": 0,
        "schedule_underbooked_diff": 0,
    }

    async with SessionLocal() as db:
        tenants = (
            await db.execute(
                select(Tenant).where(Tenant.status == TenantStatus.ACTIVE.value)
            )
        ).scalars().all()

    for tenant in tenants:
        set_tenant_id(tenant.id)
        try:
            async with SessionLocal() as db:
                diffs = await _count_diffs(
                    db, tenant.id, now=datetime.now(UTC), grace=grace
                )
                if any(diffs.values()):
                    logger.warning("[reconcile][租户%s] 差异: %s", tenant.id, diffs)
                for key, value in diffs.items():
                    totals[key] += value
        except Exception:
            logger.exception("[reconcile][租户%s] 对账失败，已跳过", tenant.id)
        finally:
            set_tenant_id(None)

    total = sum(totals.values())
    logger.info("[reconcile] 对账完成: total=%s detail=%s", total, totals)
    return {**totals, "total": total}
