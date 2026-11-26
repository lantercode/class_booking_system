"""
会员卡定时任务

包含：
- 自动激活待激活的会员卡
- 自动将已过期的会员卡标记为 EXPIRED

租户隔离：
- 定时任务运行在 APScheduler 线程，ContextVar 为空，若不设置租户会触发全表扫描跨租户操作。
- 每个任务开头查询所有 ACTIVE 租户，循环内 set_tenant_id(tenant.id) 后执行业务，
  单租户异常被隔离不影响其他租户，全部处理完后清理上下文。
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.tenant_context import get_tenant_id, set_tenant_id
from app.modules.membership.models import (
    CardStatus,
    CardType,
    MembershipCard,
)
from app.modules.tenant.models import Tenant, TenantStatus

logger = logging.getLogger(__name__)

settings = get_settings()


async def _get_active_tenants():
    """
    查询所有状态为 ACTIVE 的租户列表。

    注意：Tenant 模型不含 tenant_id 字段，tenant_query 自动注入不会过滤此查询，
    因此无需担心被当前 ContextVar 的租户过滤误伤。
    """
    async with SessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE.value)
        )
        return result.scalars().all()


async def _expire_cards_in_transaction(db, now: datetime):
    """
    内部辅助函数：在事务中处理过期卡

    用于在激活任务执行前先标记过期卡，确保状态正确。
    这是生产级的防御性编程，避免依赖外部定时任务的执行顺序。

    F6.3 T6.3.6：
    - 扫描状态扩展为 ACTIVE / PENDING（兼容历史带 expire_at 的 PENDING 卡）。
    - 逐卡交给 MembershipCardService.expire_card 加锁并重检状态；
      单卡失败用 savepoint 隔离，不拖垮同租户其他卡。
    """
    from app.modules.membership.service import membership_card_service

    result = await db.execute(
        select(MembershipCard.id).where(
            MembershipCard.expire_at < now,
            MembershipCard.expire_at.isnot(None),
            MembershipCard.status.in_(
                [CardStatus.ACTIVE.value, CardStatus.PENDING.value]
            ),
        )
    )
    card_ids = list(result.scalars().all())

    if not card_ids:
        return

    tenant_id = get_tenant_id()
    if not tenant_id:
        logger.warning("[激活任务] 未设置租户上下文，跳过过期处理")
        return

    expired_count = 0
    for card_id in card_ids:
        try:
            async with db.begin_nested():
                card = await membership_card_service.expire_card(
                    db, card_id, tenant_id
                )
                if card.status == CardStatus.EXPIRED.value:
                    expired_count += 1
        except Exception as e:
            logger.exception(
                f"[激活任务] 过期处理失败，跳过卡 {card_id}: {e}"
            )

    # 【关键】刷新到数据库，确保后续查询能看到最新状态
    await db.flush()
    logger.info(f"[激活任务] 预处理: 标记 {expired_count} 个会员卡为已过期")


async def auto_activate_membership_cards():
    """自动激活已到生效时间但未激活的会员卡。

    调度侧只负责「发现候选」；实际状态流转统一收口到
    ``MembershipCardService.auto_activate_card``（不再裸写 card.status）：

    - ``TASK_WORKER_ENABLED=true``：逐卡入队 ``activate_membership_card``，
      由 JobWorker 异步消费；
    - ``TASK_WORKER_ENABLED=false``：本线程直接调 Service，保持同步生效。

    单租户/单卡失败仅记录日志，不中断其他租户。
    """
    from app.modules.membership.service import membership_card_service
    from app.modules.task.service import task_service

    via_queue = get_settings().TASK_WORKER_ENABLED
    job_date = datetime.now(UTC).strftime("%Y%m%d")

    tenants = await _get_active_tenants()
    if not tenants:
        return

    for tenant in tenants:
        tenant_id = tenant.id
        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                now = datetime.now(UTC)

                # 【生产级优化】先执行过期处理，确保状态正确
                # 这样可以避免已过期但状态仍为ACTIVE的卡被误判为冲突
                await _expire_cards_in_transaction(db, now)

                card_ids = list(
                    (
                        await db.execute(
                            select(MembershipCard.id).where(
                                MembershipCard.valid_from <= now,
                                MembershipCard.status == CardStatus.PENDING.value,
                            )
                        )
                    ).scalars().all()
                )

                if not card_ids:
                    continue

                logger.info(
                    f"[定时任务][租户{tenant_id}] 发现 {len(card_ids)} 个待激活会员卡, ids={card_ids}"
                )

                activated_count = 0
                skipped_count = 0
                fail_count = 0

                for card_id in card_ids:
                    try:
                        if via_queue:
                            job = await task_service.enqueue(
                                db,
                                tenant_id=tenant_id,
                                type="activate_membership_card",
                                # 按天去重：DEAD 后次日仍可重新入队；激活成功后
                                # 卡状态不再是 PENDING，次日扫描不会再选中。
                                idempotency_key=f"card-activate:{card_id}:{job_date}",
                                payload={"card_id": card_id},
                            )
                            if job is not None:
                                activated_count += 1
                        else:
                            async with db.begin_nested():
                                card = await membership_card_service.auto_activate_card(
                                    db, card_id, tenant_id
                                )
                            if card is not None:
                                activated_count += 1
                            else:
                                skipped_count += 1
                    except Exception as e:
                        logger.exception(f"[定时任务][租户{tenant_id}] 卡 {card_id} 失败: {e}")
                        fail_count += 1
                        continue

                await db.commit()

                logger.info(
                    f"[定时任务][租户{tenant_id}] 自动激活"
                    f"{'入队' if via_queue else '完成'}: "
                    f"{'入队' if via_queue else '成功'} {activated_count} 个, "
                    f"跳过 {skipped_count} 个, 失败 {fail_count} 个"
                )
        except Exception as e:
            logger.exception(
                f"[定时任务][租户{tenant_id}] 自动激活会员卡失败，已跳过该租户: {e}"
            )
            continue
        finally:
            set_tenant_id(None)


async def auto_expire_membership_cards():
    """
    自动将已过期的会员卡标记为 EXPIRED

    执行逻辑:
    1. 遍历所有 ACTIVE 租户，逐租户设置 ContextVar
    2. 找到 expire_at < now 且 status=ACTIVE 的会员卡
    3. 对于次卡，如果还有剩余次数，自动清零并记录流水
    4. 将会员卡状态改为 EXPIRED
    5. 记录过期流水

    单租户处理失败仅记录日志，不中断其他租户。

    状态流转收口在 ``MembershipCardService.expire_card``（逐卡行锁 + 状态重检，
    幂等）：``TASK_WORKER_ENABLED=true`` 时逐卡入队 ``expire_membership_card``，
    否则本线程直接调 Service。
    """
    from app.modules.membership.service import membership_card_service
    from app.modules.task.service import task_service

    via_queue = get_settings().TASK_WORKER_ENABLED
    job_date = datetime.now(UTC).strftime("%Y%m%d")

    tenants = await _get_active_tenants()
    if not tenants:
        return

    for tenant in tenants:
        tenant_id = tenant.id
        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                now = datetime.now(UTC)

                # F6.3 T6.3.6：扫描范围扩展为 ACTIVE / PENDING（兼容历史带
                # expire_at 的 PENDING 卡）；逐卡加锁重检由 Service 负责。
                result = await db.execute(
                    select(MembershipCard.id).where(
                        MembershipCard.expire_at < now,
                        MembershipCard.expire_at.isnot(None),
                        MembershipCard.status.in_(
                            [CardStatus.ACTIVE.value, CardStatus.PENDING.value]
                        ),
                    )
                )
                card_ids = list(result.scalars().all())

                if not card_ids:
                    continue

                logger.info(
                    f"[定时任务][租户{tenant_id}] 发现 {len(card_ids)} 个已过期会员卡, ids={card_ids}"
                )

                expired_count = 0
                skipped_count = 0
                fail_count = 0

                for card_id in card_ids:
                    try:
                        if via_queue:
                            job = await task_service.enqueue(
                                db,
                                tenant_id=tenant_id,
                                type="expire_membership_card",
                                # 按天去重：DEAD 后次日仍可重新入队；已过期卡不再是
                                # ACTIVE/PENDING，次日扫描不会再选中。
                                idempotency_key=f"card-expire:{card_id}:{job_date}",
                                payload={"card_id": card_id},
                            )
                            if job is not None:
                                expired_count += 1
                        else:
                            async with db.begin_nested():
                                card = await membership_card_service.expire_card(
                                    db, card_id, tenant_id
                                )
                            if card.status == CardStatus.EXPIRED.value:
                                expired_count += 1
                            else:
                                skipped_count += 1
                    except Exception as e:
                        logger.exception(
                            f"[定时任务][租户{tenant_id}] 卡 {card_id} 失败: {e}"
                        )
                        fail_count += 1
                        continue

                await db.commit()

                logger.info(
                    f"[定时任务][租户{tenant_id}] 自动过期"
                    f"{'入队' if via_queue else '标记'}完成: "
                    f"{'入队' if via_queue else '成功'} {expired_count} 个, "
                    f"跳过 {skipped_count} 个, 失败 {fail_count} 个"
                )
        except Exception as e:
            logger.exception(
                f"[定时任务][租户{tenant_id}] 自动过期会员卡失败，已跳过该租户: {e}"
            )
            continue
        finally:
            set_tenant_id(None)


async def notify_expiring_membership_cards():
    """
    会员卡到期提醒

    执行逻辑:
    1. 遍历所有 ACTIVE 租户，逐租户设置 ContextVar
    2. 找到 expire_at 在 3 天内且 status=ACTIVE 的会员卡
    3. 按卡生成幂等站内提醒（同一卡同一到期日只提醒一次）

    ``TASK_WORKER_ENABLED=true`` 时逐卡入队 ``notify_card_expiring``，
    否则本线程直接调 NotificationService。此任务应每天运行一次。

    单租户处理失败仅记录日志，不中断其他租户。
    """
    from app.modules.notification.service import notification_service
    from app.modules.task.service import task_service

    via_queue = get_settings().TASK_WORKER_ENABLED
    job_date = datetime.now(UTC).strftime("%Y%m%d")

    tenants = await _get_active_tenants()
    if not tenants:
        return

    for tenant in tenants:
        tenant_id = tenant.id
        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                now = datetime.now(UTC)
                three_days_later = now + timedelta(days=3)

                result = await db.execute(
                    select(MembershipCard).where(
                        MembershipCard.expire_at <= three_days_later,
                        MembershipCard.expire_at > now,
                        MembershipCard.status == CardStatus.ACTIVE.value,
                        MembershipCard.expire_at.isnot(None),
                    )
                )
                cards = result.scalars().all()

                if not cards:
                    continue

                card_ids = [c.id for c in cards]
                logger.info(
                    f"[定时任务][租户{tenant_id}] 发现 {len(card_ids)} 个即将到期的会员卡, ids={card_ids}"
                )

                created_count = 0
                fail_count = 0

                for card in cards:
                    try:
                        remaining = (card.total_credits or 0) - card.used_credits
                        days_left = (card.expire_at - now).days
                        expire_date = card.expire_at.strftime("%Y-%m-%d")
                        # 同一卡同一到期日只提醒一次
                        idempotency_key = (
                            f"card_expiring:{card.id}:{card.expire_at.strftime('%Y%m%d')}"
                        )
                        title = "会员卡即将到期"
                        content = (
                            f"您的会员卡将于 {days_left} 天后（{expire_date}）到期，"
                            f"剩余 {remaining} 次，请及时续费。"
                        )

                        if via_queue:
                            job = await task_service.enqueue(
                                db,
                                tenant_id=tenant_id,
                                type="notify_card_expiring",
                                # 按天去重：任务 DEAD 后次日可重新入队重试，
                                # 通知侧幂等键保证同一到期日只发一条。
                                idempotency_key=(
                                    f"card-expiry-notify:{card.id}:"
                                    f"{card.expire_at.strftime('%Y%m%d')}:{job_date}"
                                ),
                                payload={
                                    "user_id": card.student_id,
                                    "type": "card_expiry_reminder",
                                    "title": title,
                                    "content": content,
                                    "idempotency_key": idempotency_key,
                                },
                            )
                            if job is not None:
                                created_count += 1
                        else:
                            new_id = await notification_service.create_idempotent(
                                db,
                                tenant_id=tenant_id,
                                user_id=card.student_id,
                                type="card_expiry_reminder",
                                title=title,
                                content=content,
                                idempotency_key=idempotency_key,
                            )
                            if new_id is not None:
                                created_count += 1
                    except Exception as e:
                        logger.exception(f"[定时任务][租户{tenant_id}] 卡 {card.id} 失败: {e}")
                        fail_count += 1
                        continue

                await db.commit()

                logger.info(
                    f"[定时任务][租户{tenant_id}] 到期提醒"
                    f"{'入队' if via_queue else '完成'}: "
                    f"{'入队' if via_queue else '新增'} {created_count} 条, 失败 {fail_count} 条"
                )
        except Exception as e:
            logger.exception(
                f"[定时任务][租户{tenant_id}] 到期提醒失败，已跳过该租户: {e}"
            )
            continue
        finally:
            set_tenant_id(None)


async def auto_unfreeze_membership_cards():
    """
    自动解冻到期冻结的会员卡

    执行逻辑:
    1. 遍历所有 ACTIVE 租户，逐租户设置 ContextVar
    2. 找到 frozen_until <= now 且 status=FROZEN 的会员卡
    3. 检查是否存在同课程类型且时间重叠的有效卡
    4. 如果冲突已解决（无冲突），自动解冻
    5. 如果仍有冲突，更新冻结原因提示
    6. 清除冻结信息
    7. 更新冻结记录的unfrozen_at

    单租户处理失败仅记录日志，不中断其他租户。

    状态流转收口在 ``MembershipCardService.auto_unfreeze_card``：
    ``TASK_WORKER_ENABLED=true`` 时逐卡入队 ``unfreeze_membership_card``，
    否则本线程直接调 Service。
    """
    from app.modules.membership.service import membership_card_service
    from app.modules.task.service import task_service

    via_queue = get_settings().TASK_WORKER_ENABLED
    job_date = datetime.now(UTC).strftime("%Y%m%d")

    tenants = await _get_active_tenants()
    if not tenants:
        return

    for tenant in tenants:
        tenant_id = tenant.id
        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                now = datetime.now(UTC)

                result = await db.execute(
                    select(MembershipCard.id).where(
                        MembershipCard.frozen_until <= now,
                        MembershipCard.status == CardStatus.FROZEN.value,
                        MembershipCard.frozen_until.isnot(None),
                    )
                )
                card_ids = list(result.scalars().all())

                if not card_ids:
                    continue

                logger.info(
                    f"[定时任务][租户{tenant_id}] 发现 {len(card_ids)} 个冻结到期的会员卡, ids={card_ids}"
                )

                unfrozen_count = 0
                conflict_count = 0
                fail_count = 0

                for card_id in card_ids:
                    try:
                        if via_queue:
                            job = await task_service.enqueue(
                                db,
                                tenant_id=tenant_id,
                                type="unfreeze_membership_card",
                                # 按天去重：DEAD 后次日可重新入队；已解冻卡不再是
                                # FROZEN，次日扫描不会再选中。
                                idempotency_key=f"card-unfreeze:{card_id}:{job_date}",
                                payload={"card_id": card_id},
                            )
                            if job is not None:
                                unfrozen_count += 1
                        else:
                            async with db.begin_nested():
                                card = await membership_card_service.auto_unfreeze_card(
                                    db, card_id, tenant_id
                                )
                            if card.status == CardStatus.ACTIVE.value:
                                unfrozen_count += 1
                            else:
                                conflict_count += 1
                    except Exception as e:
                        logger.exception(f"[定时任务][租户{tenant_id}] 卡 {card_id} 失败: {e}")
                        fail_count += 1
                        continue

                await db.commit()

                logger.info(
                    f"[定时任务][租户{tenant_id}] 自动解冻"
                    f"{'入队' if via_queue else '完成'}："
                    f"{'入队' if via_queue else '成功'} {unfrozen_count} 张，"
                    f"冲突跳过 {conflict_count} 张，失败 {fail_count} 张"
                )
        except Exception as e:
            logger.exception(
                f"[定时任务][租户{tenant_id}] 自动解冻会员卡失败，已跳过该租户: {e}"
            )
            continue
        finally:
            set_tenant_id(None)


async def auto_cancel_pending_membership_cards():
    """作废超期未激活的 PENDING 期卡（F6.3 T6.3.6）

    执行逻辑：
    1. ``PENDING_CARD_CANCEL_ENABLED=false`` 时直接返回。
    2. 逐 ACTIVE 租户设置 ContextVar，每租户一个会话。
    3. 扫描 ``card_type=period``、``status=PENDING``、``created_at < now - N 天`` 的卡。
    4. 经 BookingService 判断该卡是否已有 COMPLETED / NO_SHOW 预约；
       已有则跳过（视为已使用，不自动作废）。
    5. 逐卡 FOR UPDATE 重检后置 CANCELLED + 写 EXPIRE 流水。
    6. 单卡失败隔离；租户异常回滚该租户；``finally set_tenant_id(None)``。
    """
    if not settings.PENDING_CARD_CANCEL_ENABLED:
        return

    from app.modules.booking.service import BookingService
    from app.modules.membership.service import membership_card_service
    from app.modules.task.service import task_service

    booking_service = BookingService()
    via_queue = get_settings().TASK_WORKER_ENABLED
    job_date = datetime.now(UTC).strftime("%Y%m%d")
    tenants = await _get_active_tenants()
    if not tenants:
        return

    days = settings.PENDING_CARD_CANCEL_DAYS

    for tenant in tenants:
        tenant_id = tenant.id
        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                now = datetime.now(UTC)
                cutoff = now - timedelta(days=days)

                result = await db.execute(
                    select(MembershipCard.id).where(
                        MembershipCard.card_type == CardType.PERIOD.value,
                        MembershipCard.status == CardStatus.PENDING.value,
                        MembershipCard.created_at < cutoff,
                    )
                )
                card_ids = list(result.scalars().all())

                if not card_ids:
                    continue

                logger.info(
                    f"[定时任务][租户{tenant_id}] 发现 {len(card_ids)} 个超期未激活期卡, "
                    f"days={days}, ids={card_ids}"
                )

                cancelled_count = 0
                skipped_count = 0
                fail_count = 0

                for card_id in card_ids:
                    try:
                        used = await booking_service.has_completed_or_no_show_booking_for_card(
                            db, card_id, tenant_id
                        )
                        if used:
                            skipped_count += 1
                            continue

                        if via_queue:
                            job = await task_service.enqueue(
                                db,
                                tenant_id=tenant_id,
                                type="cancel_pending_membership_card",
                                # 按天去重：DEAD 后次日可重新入队；已作废卡不再是
                                # PENDING，次日扫描不会再选中。
                                idempotency_key=f"card-cancel-pending:{card_id}:{job_date}",
                                payload={"card_id": card_id, "days": days},
                            )
                            if job is not None:
                                cancelled_count += 1
                        else:
                            async with db.begin_nested():
                                card = await membership_card_service.cancel_pending_card(
                                    db, card_id, tenant_id, days=days
                                )
                            if card.status == CardStatus.CANCELLED.value:
                                cancelled_count += 1
                    except Exception as e:
                        logger.exception(
                            f"[定时任务][租户{tenant_id}] 期卡 {card_id} 作废失败: {e}"
                        )
                        fail_count += 1

                await db.commit()

                logger.info(
                    f"[定时任务][租户{tenant_id}] PENDING 期卡作废"
                    f"{'入队' if via_queue else '完成'}: "
                    f"{'入队' if via_queue else '成功'} {cancelled_count} 个, "
                    f"已使用跳过 {skipped_count} 个, 失败 {fail_count} 个"
                )
        except Exception as e:
            logger.exception(
                f"[定时任务][租户{tenant_id}] PENDING 期卡作废失败，已跳过该租户: {e}"
            )
            continue
        finally:
            set_tenant_id(None)


async def send_renewal_alerts():
    """会员续费预警：生成站内消息（默认关闭，按租户灰度）。

    业务判定（N 天内到期 / 剩余课时不足）由 Service 完成；
    同一学员同一卡同一到期周期只提醒一次（幂等键）。

    灰度开关：``TASK_WORKER_ENABLED`` 为真时只入队 ``notify_renewal_alert``
    任务、由 JobWorker 异步发送；为假（默认）时保持旧的同步直发，避免
    Worker 未启动导致告警丢失。
    """
    from app.ai.agent.renewal import RENEWAL_TITLE, compose_renewal_content
    from app.modules.membership.service import membership_card_service
    from app.modules.notification.service import notification_service
    from app.modules.task.service import task_service

    settings = get_settings()
    via_queue = settings.TASK_WORKER_ENABLED
    job_date = datetime.now(UTC).strftime("%Y%m%d")
    if not settings.AI_RENEWAL_ALERT_ENABLED:
        return

    whitelist = {
        item.strip() for item in settings.AI_RENEWAL_ALERT_TENANTS.split(",") if item.strip()
    }
    tenants = await _get_active_tenants()
    if not tenants:
        return

    for tenant in tenants:
        tenant_id = tenant.id
        if whitelist and str(tenant_id) not in whitelist:
            continue

        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                sent_today = await notification_service.count_today(
                    db, tenant_id=tenant_id, type="renewal_alert"
                )
                budget = settings.AI_RENEWAL_ALERT_MAX_PER_DAY - sent_today
                if budget <= 0:
                    logger.info(f"[续费预警][租户{tenant_id}] 今日已达上限，跳过")
                    continue

                items = await membership_card_service.list_renewal_alerts(
                    db,
                    tenant_id,
                    days=settings.AI_RENEWAL_ALERT_DAYS,
                    credits_threshold=settings.AI_RENEWAL_ALERT_CREDITS_THRESHOLD,
                    limit=budget,
                )
                if not items:
                    continue

                created = 0
                for item in items:
                    if created >= budget:
                        break
                    expire_at = item.get("expire_at")
                    period = expire_at.strftime("%Y%m%d") if expire_at else "low_credits"
                    idempotency_key = f"renewal:{item['card_id']}:{period}"
                    content = await compose_renewal_content(item)
                    if via_queue:
                        job = await task_service.enqueue(
                            db,
                            tenant_id=tenant_id,
                            type="notify_renewal_alert",
                            # 入队键按天去重：任务进 DEAD 后次日仍可重新入队重试；
                            # 通知侧幂等键（idempotency_key）保证同一周期只发一条。
                            idempotency_key=(
                                f"renewal-alert:{item['card_id']}:{period}:{job_date}"
                            ),
                            payload={
                                "user_id": item["student_id"],
                                "type": "renewal_alert",
                                "title": RENEWAL_TITLE,
                                "content": content,
                                "idempotency_key": idempotency_key,
                            },
                        )
                        if job is not None:
                            created += 1
                    else:
                        new_id = await notification_service.create_idempotent(
                            db,
                            tenant_id=tenant_id,
                            user_id=item["student_id"],
                            type="renewal_alert",
                            title=RENEWAL_TITLE,
                            content=content,
                            idempotency_key=idempotency_key,
                        )
                        if new_id is not None:
                            created += 1

                await db.commit()
                logger.info(
                    f"[续费预警][租户{tenant_id}] 候选 {len(items)} 张卡，"
                    f"{'入队' if via_queue else '新增'} {created} 条"
                )
        except Exception as e:
            logger.exception(f"[续费预警][租户{tenant_id}] 执行失败，已跳过该租户: {e}")
            continue
        finally:
            set_tenant_id(None)
