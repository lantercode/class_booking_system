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
    MembershipCardFreeze,
    MembershipCardTransaction,
    TransactionType,
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
    """
    自动激活已到生效时间但未激活的会员卡

    执行逻辑:
    1. 遍历所有 ACTIVE 租户，逐租户设置 ContextVar
    2. 【关键】先执行过期处理，确保卡状态正确（防止误判冲突）
    3. 找到 valid_from <= now 且 status=PENDING 的会员卡
    4. 检查是否有同课程类型且时间重叠的有效卡
    5. 将状态改为 ACTIVE
    6. 计算 expire_at（如果有有效天数）
    7. 记录激活流水

    单租户处理失败仅记录日志，不中断其他租户。
    """
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

                result = await db.execute(
                    select(MembershipCard).where(
                        MembershipCard.valid_from <= now,
                        MembershipCard.status == CardStatus.PENDING.value,
                    )
                )
                cards = result.scalars().all()

                if not cards:
                    continue

                card_ids = [c.id for c in cards]
                logger.info(
                    f"[定时任务][租户{tenant_id}] 发现 {len(card_ids)} 个待激活会员卡, ids={card_ids}"
                )

                success_count = 0
                fail_count = 0

                for card in cards:
                    try:
                        # 检查学员是否已有同课程类型且时间重叠的有效卡（防止同一时段多张卡重叠）
                        # 注意：这里检查所有有效卡，不只是同产品的卡
                        from app.modules.membership.repository import MembershipCardRepository

                        card_repo = MembershipCardRepository()
                        all_existing_cards = await card_repo.get_active_cards_by_student(
                            db, card.student_id, card.tenant_id
                        )

                        # 过滤出课程类型相同且时间重叠的卡
                        has_conflict = False
                        new_card_course_type = card.applicable_course_type_code

                        if new_card_course_type:
                            for existing_card in all_existing_cards:
                                # 【关键】跳过当前正在处理的卡本身,避免"自己与自己冲突"
                                if existing_card.id == card.id:
                                    continue

                                existing_course_type = existing_card.applicable_course_type_code
                                # 如果课程类型相同
                                if existing_course_type == new_card_course_type:
                                    # 检查时间是否重叠
                                    existing_valid_from = existing_card.valid_from
                                    existing_expire_at = existing_card.expire_at

                                    if (
                                        card.valid_from
                                        and existing_expire_at
                                        and card.expire_at
                                        and existing_valid_from
                                    ):
                                        if (
                                            card.valid_from <= existing_expire_at
                                            and existing_valid_from <= card.expire_at
                                        ):
                                            has_conflict = True
                                            break

                        if has_conflict:
                            logger.warning(
                                f"[定时任务][租户{tenant_id}] 跳过激活会员卡 {card.id}："
                                f"学员 {card.student_id} 已有同课程类型的有效卡"
                            )
                            continue

                        card.status = CardStatus.ACTIVE.value

                        # 如果有有效天数，计算到期时间
                        # F6.3 T6.3.6：优先使用发卡时快照 card.validity_days，
                        # 回退产品配置，避免产品后续变更导致卡条款漂移。
                        validity_days = card.validity_days
                        if not validity_days and card.product_id:
                            from app.modules.membership.models import MembershipCardProduct

                            product_result = await db.execute(
                                select(MembershipCardProduct).where(
                                    MembershipCardProduct.id == card.product_id,
                                    MembershipCardProduct.tenant_id == card.tenant_id,
                                )
                            )
                            product = product_result.scalars().first()
                            validity_days = product.validity_days if product else None

                        if validity_days:
                            # 使用与 service.py 相同的计算逻辑：起始日期算作第1天
                            expire_date = card.valid_from.date() + timedelta(days=validity_days - 1)
                            card.expire_at = datetime(
                                year=expire_date.year,
                                month=expire_date.month,
                                day=expire_date.day,
                                hour=23,
                                minute=59,
                                second=59,
                                tzinfo=card.valid_from.tzinfo or UTC,
                            )

                        txn = MembershipCardTransaction(
                            tenant_id=card.tenant_id,
                            card_id=card.id,
                            operation_type=TransactionType.ISSUE.value,
                            change_amount=0,
                            balance_after=(card.total_credits or 0) - card.used_credits,
                            remark="会员卡自动激活",
                        )
                        db.add(txn)
                        success_count += 1

                    except Exception as e:
                        logger.exception(f"[定时任务][租户{tenant_id}] 卡 {card.id} 失败: {e}")
                        fail_count += 1
                        continue

                await db.commit()

                logger.info(
                    f"[定时任务][租户{tenant_id}] 自动激活完成: 成功 {success_count} 个, 失败 {fail_count} 个"
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
    """
    tenants = await _get_active_tenants()
    if not tenants:
        return

    for tenant in tenants:
        tenant_id = tenant.id
        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                from app.modules.membership.service import membership_card_service

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

                success_count = 0
                fail_count = 0

                for card_id in card_ids:
                    try:
                        async with db.begin_nested():
                            card = await membership_card_service.expire_card(
                                db, card_id, tenant_id
                            )
                        if card.status == CardStatus.EXPIRED.value:
                            success_count += 1
                        else:
                            logger.info(
                                f"[定时任务][租户{tenant_id}] 卡 {card_id} 已被其他流程处理，跳过"
                            )
                    except Exception as e:
                        logger.exception(
                            f"[定时任务][租户{tenant_id}] 卡 {card_id} 失败: {e}"
                        )
                        fail_count += 1

                await db.commit()

                logger.info(
                    f"[定时任务][租户{tenant_id}] 自动标记完成: 成功 {success_count} 个, 失败 {fail_count} 个"
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
    3. 记录提醒日志（实际项目中可接入短信/推送/微信模板消息）

    注意：此任务应每天运行一次
    单租户处理失败仅记录日志，不中断其他租户。
    """
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

                success_count = 0
                fail_count = 0

                for card in cards:
                    try:
                        remaining = (card.total_credits or 0) - card.used_credits
                        days_left = (card.expire_at - now).days

                        # TODO: 实际项目中应接入通知服务
                        # 例如：发送短信、微信模板消息、App推送等
                        logger.info(
                            f"[到期提醒][租户{tenant_id}] 会员卡 {card.id} (学员ID: {card.student_id}) "
                            f"将在 {days_left} 天后到期，剩余次数: {remaining}"
                        )
                        success_count += 1

                    except Exception as e:
                        logger.exception(f"[定时任务][租户{tenant_id}] 卡 {card.id} 失败: {e}")
                        fail_count += 1
                        continue

                logger.info(
                    f"[定时任务][租户{tenant_id}] 到期提醒完成: 成功 {success_count} 个, 失败 {fail_count} 个"
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
    """
    from app.modules.membership.repository import MembershipCardRepository

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
                    select(MembershipCard).where(
                        MembershipCard.frozen_until <= now,
                        MembershipCard.status == CardStatus.FROZEN.value,
                        MembershipCard.frozen_until.isnot(None),
                    )
                )
                cards = result.scalars().all()

                if not cards:
                    continue

                card_ids = [c.id for c in cards]
                logger.info(
                    f"[定时任务][租户{tenant_id}] 发现 {len(card_ids)} 个冻结到期的会员卡, ids={card_ids}"
                )

                card_repo = MembershipCardRepository()
                unfrozen_count = 0
                conflict_count = 0
                resolved_count = 0
                fail_count = 0

                for card in cards:
                    try:
                        # 检查是否存在同课程类型且时间重叠的有效卡
                        all_existing_cards = await card_repo.get_active_cards_by_student(
                            db, card.student_id, card.tenant_id
                        )

                        has_conflict = False
                        card_course_type = card.applicable_course_type_code

                        if card_course_type:
                            for existing_card in all_existing_cards:
                                # 跳过当前卡本身
                                if existing_card.id == card.id:
                                    continue

                                existing_course_type = existing_card.applicable_course_type_code
                                if existing_course_type == card_course_type:
                                    existing_valid_from = existing_card.valid_from
                                    existing_expire_at = existing_card.expire_at

                                    if (
                                        card.valid_from
                                        and existing_valid_from
                                        and card.expire_at
                                        and existing_expire_at
                                    ):
                                        # 检查时间重叠
                                        if card.valid_from <= existing_expire_at and existing_valid_from <= card.expire_at:
                                            has_conflict = True
                                            break

                        if has_conflict:
                            # 仍有冲突，更新冻结原因
                            conflict_msg = (
                                f"冻结到期但因课程冲突无法自动解冻（{card_course_type}），请联系管理员处理"
                            )
                            if card.frozen_reason != conflict_msg:
                                card.frozen_reason = conflict_msg
                                logger.warning(
                                    f"[定时任务][租户{tenant_id}] 卡 {card.id}（学员 {card.student_id}）"
                                    f"冻结到期但存在冲突，已更新冻结原因"
                                )
                            conflict_count += 1
                            continue

                        # 冲突已解决或无冲突，自动解冻
                        card.status = CardStatus.ACTIVE.value

                        # 根据冻结时保存的剩余天数重新计算有效期
                        if card.frozen_remaining_days is not None and card.frozen_remaining_days > 0:
                            card.expire_at = now + timedelta(days=card.frozen_remaining_days)

                        # 在清除 frozen_reason 之前先保存，用于后续判断是否曾经有冲突
                        had_conflict_before_unfreeze = "课程冲突" in (card.frozen_reason or "")

                        # 更新最新的冻结记录（必须在清除 frozen_reason 之前完成）
                        result = await db.execute(
                            select(MembershipCardFreeze)
                            .where(
                                MembershipCardFreeze.card_id == card.id,
                                MembershipCardFreeze.unfrozen_at.is_(None),
                            )
                            .order_by(MembershipCardFreeze.created_at.desc())
                            .limit(1)
                        )
                        freeze_record = result.scalars().first()
                        if freeze_record:
                            freeze_record.unfrozen_at = now

                        # 清除冻结信息
                        card.frozen_reason = None
                        card.frozen_at = None
                        card.frozen_until = None
                        card.frozen_remaining_days = None

                        # 检查之前是否有冲突标记，如果有则记录日志
                        if had_conflict_before_unfreeze:
                            resolved_count += 1
                            logger.info(
                                f"[定时任务][租户{tenant_id}] 卡 {card.id}（学员 {card.student_id}）"
                                f"冲突已解决，自动解冻"
                            )

                        unfrozen_count += 1

                    except Exception as e:
                        logger.exception(f"[定时任务][租户{tenant_id}] 卡 {card.id} 失败: {e}")
                        fail_count += 1
                        continue

                await db.commit()

                logger.info(
                    f"[定时任务][租户{tenant_id}] 自动解冻完成：成功 {unfrozen_count} 张，"
                    f"冲突跳过 {conflict_count} 张，"
                    f"冲突解决 {resolved_count} 张，"
                    f"失败 {fail_count} 张"
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

    booking_service = BookingService()
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
                    f"[定时任务][租户{tenant_id}] PENDING 期卡作废完成: "
                    f"成功 {cancelled_count} 个, 已使用跳过 {skipped_count} 个, 失败 {fail_count} 个"
                )
        except Exception as e:
            logger.exception(
                f"[定时任务][租户{tenant_id}] PENDING 期卡作废失败，已跳过该租户: {e}"
            )
            continue
        finally:
            set_tenant_id(None)
