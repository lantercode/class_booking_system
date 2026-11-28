"""异步任务对外 Service + Handler 注册表。

TaskService 封装入队 / 查询等公共 API；
Handler 注册表 ``HANDLERS`` 供 Worker 在启动时注入。

当前注册的 handler：
- ``notify_renewal_alert``           — 续费预警站内消息（复用 NotificationService.create_idempotent）
- ``notify_card_expiring``           — 会员卡即将到期提醒（同上，通知幂等键区分）
- ``activate_membership_card``       — 会员卡到点自动激活（复用 MembershipCardService.auto_activate_card）
- ``expire_membership_card``         — 会员卡到期自动过期（复用 MembershipCardService.expire_card）
- ``unfreeze_membership_card``       — 冻结到期自动解冻（复用 MembershipCardService.auto_unfreeze_card）
- ``cancel_pending_membership_card`` — 超期未激活期卡作废（复用 MembershipCardService.cancel_pending_card）
- ``cleanup_idempotency_keys``        — 幂等键表按保留期分批清理（Repository 原生 CTE 批量删除）
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notification.service import notification_service
from app.modules.task.repository import JobQueueRepository

logger = logging.getLogger(__name__)

# Handler 类型：(db, payload_dict, *, tenant_id) -> None
HandlerFunc = Callable[..., Any]

# ---------------------------------------------------------------------------
# 首次试点 handler：续费预警站内消息
# ---------------------------------------------------------------------------


async def _create_station_notification(
    db: AsyncSession,
    payload: dict,
    *,
    tenant_id: int,
    tag: str,
) -> None:
    """按 payload 发送一条幂等站内消息（续费预警 / 到期提醒共用）。"""
    user_id = int(payload["user_id"])
    note_type = str(payload["type"])
    title = str(payload["title"])
    content = str(payload["content"])
    idempotency_key = str(payload["idempotency_key"])

    created = await notification_service.create_idempotent(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        type=note_type,
        title=title,
        content=content,
        idempotency_key=idempotency_key,
    )
    # create_idempotent 返回 None 表示幂等键冲突（通知已存在），不算失败
    if created is None:
        logger.info(
            "[%s] 幂等命中 tenant=%s user=%s key=%s，跳过",
            tag, tenant_id, user_id, idempotency_key,
        )
    else:
        logger.info(
            "[%s] ✅ 已发送 tenant=%s user=%s note_id=%s",
            tag, tenant_id, user_id, created,
        )


async def notify_renewal_alert(
    db: AsyncSession,
    payload: dict,
    *,
    tenant_id: int,
) -> None:
    """给单个学员发一条续费预警的站内消息。

    payload 约定（由入队方如 APScheduler 的 send_renewal_alerts 写入）：
    ```json
    {
      "user_id": 123,
      "type": "renewal_alert",
      "title": "会员卡即将到期",
      "content": "你的会员卡 XXXX 将于 2026-11-30 到期，...",
      "idempotency_key": "renewal:card456:20261124"
    }
    ```
    幂等：同一租户同一 idempotency_key 只发一次（由 NotificationService 保证）。
    """
    await _create_station_notification(
        db, payload, tenant_id=tenant_id, tag="notify_renewal_alert"
    )


async def notify_card_expiring(
    db: AsyncSession,
    payload: dict,
    *,
    tenant_id: int,
) -> None:
    """会员卡即将到期站内提醒（payload 结构与续费预警一致，幂等由通知键保证）。"""
    await _create_station_notification(
        db, payload, tenant_id=tenant_id, tag="notify_card_expiring"
    )


# ---------------------------------------------------------------------------
# Handler：会员卡到点自动激活
# ---------------------------------------------------------------------------


async def activate_membership_card(
    db: AsyncSession,
    payload: dict,
    *,
    tenant_id: int,
) -> None:
    """系统自动激活会员卡（PENDING → ACTIVE）。

    payload 约定：``{"card_id": 123}``。

    幂等由 Service 保证：行锁 + 状态重检，已激活 / 未到生效时间 / 同课程
    类型窗口冲突都会返回 ``None``（视为「无需激活」，任务正常结束）。
    卡已不存在的确定性业务错误不重试。
    """
    from app.modules.membership.service import membership_card_service

    card_id = int(payload["card_id"])
    try:
        card = await membership_card_service.auto_activate_card(db, card_id, tenant_id)
    except HTTPException as exc:
        logger.warning(
            "[activate_membership_card] 跳过 card=%s tenant=%s: %s",
            card_id, tenant_id, exc.detail,
        )
        return

    if card is None:
        logger.info(
            "[activate_membership_card] 无需激活 card=%s tenant=%s", card_id, tenant_id
        )
    else:
        logger.info(
            "[activate_membership_card] ✅ 已激活 card=%s tenant=%s", card_id, tenant_id
        )


# ---------------------------------------------------------------------------
# Handler：会员卡到期自动过期
# ---------------------------------------------------------------------------


async def expire_membership_card(
    db: AsyncSession,
    payload: dict,
    *,
    tenant_id: int,
) -> None:
    """系统自动过期会员卡（ACTIVE/PENDING → EXPIRED）。

    payload 约定：``{"card_id": 123}``。

    ``expire_card`` 逐卡行锁 + 状态重检，未到期或已被其他流程处理时返回卡片
    本身（状态非 EXPIRED），视为正常结束；卡不存在属确定性业务错误，不重试。
    """
    from app.modules.membership.models import CardStatus
    from app.modules.membership.service import membership_card_service

    card_id = int(payload["card_id"])
    try:
        card = await membership_card_service.expire_card(db, card_id, tenant_id)
    except HTTPException as exc:
        logger.warning(
            "[expire_membership_card] 跳过 card=%s tenant=%s: %s",
            card_id, tenant_id, exc.detail,
        )
        return

    if card.status == CardStatus.EXPIRED.value:
        logger.info(
            "[expire_membership_card] ✅ 已过期 card=%s tenant=%s", card_id, tenant_id
        )
    else:
        logger.info(
            "[expire_membership_card] 无需处理 card=%s status=%s tenant=%s",
            card_id, card.status, tenant_id,
        )


# ---------------------------------------------------------------------------
# Handler：冻结到期自动解冻
# ---------------------------------------------------------------------------


async def unfreeze_membership_card(
    db: AsyncSession,
    payload: dict,
    *,
    tenant_id: int,
) -> None:
    """冻结到期自动解冻；仍有同课程类型窗口冲突时保持冻结并更新原因。

    payload 约定：``{"card_id": 123}``。幂等：状态/时间重检在 Service 内完成。
    """
    from app.modules.membership.models import CardStatus
    from app.modules.membership.service import membership_card_service

    card_id = int(payload["card_id"])
    try:
        card = await membership_card_service.auto_unfreeze_card(db, card_id, tenant_id)
    except HTTPException as exc:
        logger.warning(
            "[unfreeze_membership_card] 跳过 card=%s tenant=%s: %s",
            card_id, tenant_id, exc.detail,
        )
        return

    if card.status == CardStatus.ACTIVE.value:
        logger.info(
            "[unfreeze_membership_card] ✅ 已解冻 card=%s tenant=%s", card_id, tenant_id
        )
    else:
        logger.info(
            "[unfreeze_membership_card] 保持冻结 card=%s tenant=%s reason=%s",
            card_id, tenant_id, card.frozen_reason,
        )


# ---------------------------------------------------------------------------
# Handler：PENDING 期卡超期作废
# ---------------------------------------------------------------------------


async def cancel_pending_membership_card(
    db: AsyncSession,
    payload: dict,
    *,
    tenant_id: int,
) -> None:
    """超期未激活的 PENDING 期卡自动作废。

    payload 约定：``{"card_id": 123, "days": 30}``。

    入队时调度侧已做过一次「是否已使用」预检；Worker 执行时按当前数据重检，
    避免入队与执行之间产生 COMPLETED / NO_SHOW 预约后被误作废。
    """
    from app.modules.booking.service import BookingService
    from app.modules.membership.models import CardStatus
    from app.modules.membership.service import membership_card_service

    card_id = int(payload["card_id"])
    days = int(payload["days"])
    try:
        used = await BookingService().has_completed_or_no_show_booking_for_card(
            db, card_id, tenant_id
        )
        if used:
            logger.info(
                "[cancel_pending_membership_card] 已使用，跳过 card=%s tenant=%s",
                card_id, tenant_id,
            )
            return
        card = await membership_card_service.cancel_pending_card(
            db, card_id, tenant_id, days=days
        )
    except HTTPException as exc:
        logger.warning(
            "[cancel_pending_membership_card] 跳过 card=%s tenant=%s: %s",
            card_id, tenant_id, exc.detail,
        )
        return

    if card.status == CardStatus.CANCELLED.value:
        logger.info(
            "[cancel_pending_membership_card] ✅ 已作废 card=%s tenant=%s",
            card_id, tenant_id,
        )
    else:
        logger.info(
            "[cancel_pending_membership_card] 无需处理 card=%s status=%s tenant=%s",
            card_id, card.status, tenant_id,
        )


# ---------------------------------------------------------------------------
# Handler：排期到点自动完成
# ---------------------------------------------------------------------------


async def finish_schedule(
    db: AsyncSession,
    payload: dict,
    *,
    tenant_id: int,
) -> None:
    """排期结束后（含 grace）自动收口预约终态。

    payload 约定：``{"schedule_id": 123}``。非 NORMAL / 未到点（重投递或时钟
    偏差）时跳过；重复执行幂等（预约已完成则不再变更）。
    """
    from app.core.config import get_settings
    from app.modules.booking.service import BookingService
    from app.modules.schedule.models import CourseSchedule, ScheduleStatus

    schedule_id = int(payload["schedule_id"])
    schedule = (
        await db.execute(
            select(CourseSchedule).where(
                CourseSchedule.id == schedule_id,
                CourseSchedule.tenant_id == tenant_id,
            )
        )
    ).scalars().first()

    if schedule is None:
        logger.warning(
            "[finish_schedule] 排期不存在 schedule=%s tenant=%s", schedule_id, tenant_id
        )
        return
    if schedule.status != ScheduleStatus.NORMAL.value:
        logger.info(
            "[finish_schedule] 非 NORMAL 跳过 schedule=%s status=%s",
            schedule_id, schedule.status,
        )
        return

    grace = timedelta(minutes=get_settings().AUTO_FINISH_GRACE_MINUTES)
    if schedule.end_at + grace > datetime.now(UTC):
        logger.info("[finish_schedule] 未到点跳过 schedule=%s", schedule_id)
        return

    await BookingService().finalize_schedule_bookings(db, schedule_id)
    logger.info(
        "[finish_schedule] ✅ 已收口 schedule=%s tenant=%s", schedule_id, tenant_id
    )


# ---------------------------------------------------------------------------
# Handler：人数不足自动取消排期
# ---------------------------------------------------------------------------


async def cancel_schedule_if_underbooked(
    db: AsyncSession,
    payload: dict,
    *,
    tenant_id: int,
) -> None:
    """到点检查预约人数，不足 ``min_students`` 则自动取消排期。

    payload 约定：``{"schedule_id": 123, "min_students": 3}``。

    执行时重查状态/时间/人数：未到截止时间则重新投递；已达人数则跳过。
    """
    from app.modules.course.models import Course, CourseType
    from app.modules.schedule.jobs import job_repo, underbooked_job_key
    from app.modules.schedule.models import CourseSchedule, ScheduleStatus
    from app.modules.schedule.service import ScheduleService

    schedule_id = int(payload["schedule_id"])
    now = datetime.now(UTC)

    row = (
        await db.execute(
            select(
                CourseSchedule.status,
                CourseSchedule.booked_count,
                CourseSchedule.start_at,
                CourseType.min_students,
                CourseType.cancel_before_minutes,
            )
            .join(Course, CourseSchedule.course_id == Course.id)
            .join(CourseType, Course.course_type_code == CourseType.code)
            .where(
                CourseSchedule.id == schedule_id,
                CourseSchedule.tenant_id == tenant_id,
            )
        )
    ).first()

    if row is None or row.status != ScheduleStatus.NORMAL.value:
        logger.info(
            "[cancel_schedule_if_underbooked] 排期不存在或非 NORMAL 跳过 schedule=%s",
            schedule_id,
        )
        return
    if not row.min_students or row.cancel_before_minutes is None:
        return
    if row.booked_count >= row.min_students:
        logger.info(
            "[cancel_schedule_if_underbooked] 人数达标跳过 schedule=%s (%s/%s)",
            schedule_id, row.booked_count, row.min_students,
        )
        return

    deadline = row.start_at - timedelta(minutes=row.cancel_before_minutes)
    if now < deadline:
        # 提前触发（如预约变更）：重新投递到真正的截止时间
        await job_repo.upsert(
            db,
            tenant_id=tenant_id,
            type="cancel_schedule_if_underbooked",
            idempotency_key=underbooked_job_key(schedule_id),
            payload={"schedule_id": schedule_id, "min_students": row.min_students},
            run_at=deadline,
        )
        return

    await ScheduleService().cancel_schedule(
        db,
        schedule_id=schedule_id,
        cancel_reason=(
            f"预约人数不足（{row.booked_count}/{row.min_students}），系统自动取消"
        ),
        operator_id=0,
    )
    logger.info(
        "[cancel_schedule_if_underbooked] ✅ 已自动取消 schedule=%s (%s/%s)",
        schedule_id, row.booked_count, row.min_students,
    )


# ---------------------------------------------------------------------------
# Handler：幂等键表按保留期清理
# ---------------------------------------------------------------------------


async def cleanup_idempotency_keys(
    db: AsyncSession,
    payload: dict,
    *,
    tenant_id: int,
) -> None:
    """删除 ``created_at`` 早于保留期的幂等键记录（按租户分批）。

    payload 约定：``{"retention_days": 7}``（缺省取 ``IDEMPOTENCY_KEY_RETENTION_DAYS``）。

    分批删除直到单批返回行数小于 ``IDEMPOTENCY_CLEANUP_BATCH_SIZE``，避免一次性
    大事务长时间持锁；删除语句由 ``IdempotencyKeyRepository.delete_expired_batch``
    提供（原生 CTE + LIMIT），显式限定 tenant_id。
    """
    from app.core.config import get_settings
    from app.modules.booking.repository import IdempotencyKeyRepository

    settings = get_settings()
    retention_days = int(
        payload.get("retention_days", settings.IDEMPOTENCY_KEY_RETENTION_DAYS)
    )
    batch_size = max(1, int(settings.IDEMPOTENCY_CLEANUP_BATCH_SIZE))
    before = datetime.now(UTC) - timedelta(days=retention_days)

    repo = IdempotencyKeyRepository()
    total = 0
    while True:
        deleted = await repo.delete_expired_batch(
            db,
            tenant_id=tenant_id,
            before=before,
            limit=batch_size,
        )
        total += deleted
        if deleted < batch_size:
            break

    print(f"[cleanup] 清理幂等记录: tenant={tenant_id} deleted={total}")
    logger.info(
        "[cleanup_idempotency_keys] tenant=%s retention_days=%s deleted=%s",
        tenant_id, retention_days, total,
    )


# ---------------------------------------------------------------------------
# Handler 注册表（Worker 启动时整体注入）
# ---------------------------------------------------------------------------

HANDLERS: dict[str, HandlerFunc] = {
    "notify_renewal_alert": notify_renewal_alert,
    "notify_card_expiring": notify_card_expiring,
    "activate_membership_card": activate_membership_card,
    "expire_membership_card": expire_membership_card,
    "unfreeze_membership_card": unfreeze_membership_card,
    "cancel_pending_membership_card": cancel_pending_membership_card,
    "finish_schedule": finish_schedule,
    "cancel_schedule_if_underbooked": cancel_schedule_if_underbooked,
    "cleanup_idempotency_keys": cleanup_idempotency_keys,
}


# ---------------------------------------------------------------------------
# TaskService — 对外公共 API
# ---------------------------------------------------------------------------


class TaskService:
    """任务队列对外 API：入队、查询等。"""

    def __init__(self) -> None:
        self.repo = JobQueueRepository()

    # ---- 入队 -----------------------------------------------------------

    async def enqueue(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        type: str,
        idempotency_key: str,
        payload: dict,
        run_at: datetime | None = None,
    ) -> Any:
        """入队一条任务；返回 JobQueue ORM 对象或 None（幂等冲突）。"""
        return await self.repo.enqueue(
            db,
            tenant_id=tenant_id,
            type=type,
            idempotency_key=idempotency_key,
            payload=payload,
            run_at=run_at,
        )

    # ---- 查询 -----------------------------------------------------------

    async def counts_by_status(
        self,
        db: AsyncSession,
        *,
        tenant_id: int | None = None,
    ) -> dict[str, int]:
        return await self.repo.count_by_status(db, tenant_id=tenant_id)


# 模块级单例
task_service = TaskService()
