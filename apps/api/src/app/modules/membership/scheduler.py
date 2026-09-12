"""
会员卡定时任务

包含：
- 自动激活待激活的会员卡
- 自动将已过期的会员卡标记为 EXPIRED
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.membership.models import (
    CardStatus,
    MembershipCard,
    MembershipCardTransaction,
    TransactionType,
)

logger = logging.getLogger(__name__)

settings = get_settings()


async def auto_activate_membership_cards():
    """
    自动激活已到生效时间但未激活的会员卡

    执行逻辑:
    1. 找到 valid_from <= now 且 status=PENDING 的会员卡
    2. 将状态改为 ACTIVE
    3. 计算 expire_at（如果有有效天数）
    4. 记录激活流水
    """
    from datetime import timedelta

    async with SessionLocal() as db:
        now = datetime.now(UTC)

        result = await db.execute(
            select(MembershipCard).where(
                MembershipCard.valid_from <= now,
                MembershipCard.status == CardStatus.PENDING.value,
            )
        )
        cards = result.scalars().all()

        if not cards:
            return

        card_ids = [c.id for c in cards]
        logger.info(
            f"[定时任务] 发现 {len(card_ids)} 个待激活会员卡, ids={card_ids}"
        )

        for card in cards:
            # 检查学员是否已有同产品且课程类型重叠的有效卡（防止同一时段多张卡重叠）
            if card.product_id:
                from app.modules.membership.repository import MembershipCardRepository
                card_repo = MembershipCardRepository()
                existing_cards = await card_repo.get_active_cards_by_product(
                    db, card.student_id, card.product_id, card.tenant_id, exclude_pending=True
                )
                
                # 过滤出课程类型有重叠且时间重叠的卡
                has_conflict = False
                new_card_course_types = set(card.applicable_course_type_codes or [])
                
                for existing_card in existing_cards:
                    existing_course_types = set(existing_card.applicable_course_type_codes or [])
                    # 如果课程类型有交集
                    if new_card_course_types & existing_course_types:
                        # 检查时间是否重叠
                        if card.valid_from and existing_card.expire_at and card.expire_at and existing_card.valid_from:
                            if card.valid_from <= existing_card.expire_at and existing_card.valid_from <= card.expire_at:
                                has_conflict = True
                                break
                
                if has_conflict:
                    logger.warning(
                        f"[定时任务] 跳过激活会员卡 {card.id}：学员 {card.student_id} 已有同课程类型的有效卡"
                    )
                    continue

            card.status = CardStatus.ACTIVE.value

            # 如果有有效天数，计算到期时间
            if card.product_id:
                from app.modules.membership.repository import MembershipCardProductRepository
                product_repo = MembershipCardProductRepository()
                product = await product_repo.get_by_id(db, card.product_id)
                if product and product.validity_days:
                    card.expire_at = card.valid_from + timedelta(days=product.validity_days)

            txn = MembershipCardTransaction(
                tenant_id=card.tenant_id,
                card_id=card.id,
                operation_type=TransactionType.ISSUE.value,
                change_amount=0,
                balance_after=(card.total_credits or 0) - card.used_credits,
                remark="会员卡自动激活",
            )
            db.add(txn)

        await db.commit()

        logger.info(
            f"[定时任务] 自动激活 {len(card_ids)} 个会员卡"
        )


async def auto_expire_membership_cards():
    """
    自动将已过期的会员卡标记为 EXPIRED

    执行逻辑:
    1. 找到 expire_at < now 且 status=ACTIVE 的会员卡
    2. 对于次卡，如果还有剩余次数，自动清零并记录流水
    3. 将会员卡状态改为 EXPIRED
    4. 记录过期流水
    """
    from app.modules.membership.models import CardType
    
    async with SessionLocal() as db:
        now = datetime.now(UTC)

        result = await db.execute(
            select(MembershipCard).where(
                MembershipCard.expire_at < now,
                MembershipCard.status == CardStatus.ACTIVE.value,
                MembershipCard.expire_at.isnot(None),
                # 排除已冻结的卡（冻结期间不计入过期）
                MembershipCard.status != CardStatus.FROZEN.value,
            )
        )
        cards = result.scalars().all()

        if not cards:
            return

        card_ids = [c.id for c in cards]
        logger.info(
            f"[定时任务] 发现 {len(card_ids)} 个已过期会员卡, ids={card_ids}"
        )

        for card in cards:
            remaining = (card.total_credits or 0) - card.used_credits
            
            # 对于次卡，如果有剩余次数，先清零
            if card.card_type == CardType.COUNT.value and remaining > 0:
                logger.info(
                    f"[定时任务] 次卡 {card.id} 到期，剩余 {remaining} 次自动清零"
                )
                # 记录清零流水
                clear_txn = MembershipCardTransaction(
                    tenant_id=card.tenant_id,
                    card_id=card.id,
                    operation_type=TransactionType.EXPIRE.value,
                    change_amount=-remaining,
                    balance_after=0,
                    remark=f"会员卡到期，剩余{remaining}次自动清零",
                )
                db.add(clear_txn)
                # 更新已使用次数为总次数（表示全部用完）
                card.used_credits = card.total_credits

            # 更新状态为已过期
            card.status = CardStatus.EXPIRED.value

            # 记录过期流水（如果没有剩余次数，只记录过期流水）
            if remaining == 0:
                txn = MembershipCardTransaction(
                    tenant_id=card.tenant_id,
                    card_id=card.id,
                    operation_type=TransactionType.EXPIRE.value,
                    change_amount=0,
                    balance_after=0,
                    remark="会员卡自动过期",
                )
                db.add(txn)

        await db.commit()

        logger.info(
            f"[定时任务] 自动标记 {len(card_ids)} 个会员卡为已过期"
        )


async def notify_expiring_membership_cards():
    """
    会员卡到期提醒
    
    执行逻辑:
    1. 找到 expire_at 在 3 天内且 status=ACTIVE 的会员卡
    2. 记录提醒日志（实际项目中可接入短信/推送/微信模板消息）
    
    注意：此任务应每天运行一次
    """
    from datetime import timedelta
    
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
            return

        card_ids = [c.id for c in cards]
        logger.info(
            f"[定时任务] 发现 {len(card_ids)} 个即将到期的会员卡, ids={card_ids}"
        )

        for card in cards:
            remaining = (card.total_credits or 0) - card.used_credits
            days_left = (card.expire_at - now).days
            
            # TODO: 实际项目中应接入通知服务
            # 例如：发送短信、微信模板消息、App推送等
            logger.info(
                f"[到期提醒] 会员卡 {card.id} (学员ID: {card.student_id}) "
                f"将在 {days_left} 天后到期，剩余次数: {remaining}"
            )


async def auto_unfreeze_membership_cards():
    """
    自动解冻到期冻结的会员卡
    
    执行逻辑:
    1. 找到 frozen_until <= now 且 status=FROZEN 的会员卡
    2. 将状态改为 ACTIVE
    3. 清除冻结信息
    4. 更新冻结记录的unfrozen_at
    """
    from app.modules.membership.models import MembershipCardFreeze
    
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
            return

        card_ids = [c.id for c in cards]
        logger.info(
            f"[定时任务] 发现 {len(card_ids)} 个冻结到期的会员卡, ids={card_ids}"
        )

        for card in cards:
            card.status = CardStatus.ACTIVE.value
            card.frozen_reason = None
            card.frozen_at = None
            frozen_until = card.frozen_until
            card.frozen_until = None

            # 更新最新的冻结记录
            result = await db.execute(
                select(MembershipCardFreeze).where(
                    MembershipCardFreeze.card_id == card.id,
                    MembershipCardFreeze.unfrozen_at.is_(None),
                ).order_by(MembershipCardFreeze.created_at.desc()).limit(1)
            )
            freeze_record = result.scalars().first()
            if freeze_record:
                freeze_record.unfrozen_at = now

        await db.commit()

        logger.info(
            f"[定时任务] 自动解冻 {len(card_ids)} 个会员卡"
        )