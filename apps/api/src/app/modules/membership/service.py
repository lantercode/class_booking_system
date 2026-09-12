"""
Membership Card Service - 会员卡业务逻辑层

包含：
- 产品管理（CRUD）
- 会员卡发放与管理
- 课时扣减与恢复
- 消费流水记录
- 冻结/解冻操作
"""

from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.membership.models import (
    CardStatus,
    MembershipCard,
    MembershipCardFreeze,
    MembershipCardProduct,
    MembershipCardTransaction,
    ProductStatus,
    TransactionType,
)
from app.modules.membership.repository import (
    MembershipCardFreezeRepository,
    MembershipCardProductRepository,
    MembershipCardRepository,
    MembershipCardTransactionRepository,
)
from app.modules.membership.schemas import (
    MembershipCardCreate,
    MembershipCardProductCreate,
    MembershipCardProductResponse,
    MembershipCardProductUpdate,
    MembershipCardResponse,
    MembershipCardTransactionResponse,
)


class MembershipCardService:
    """会员卡业务逻辑"""

    def __init__(self):
        self.product_repo = MembershipCardProductRepository()
        self.card_repo = MembershipCardRepository()
        self.txn_repo = MembershipCardTransactionRepository()
        self.freeze_repo = MembershipCardFreezeRepository()

    async def create_product(
        self,
        db: AsyncSession,
        data: MembershipCardProductCreate,
        tenant_id: int,
    ) -> MembershipCardProduct:
        """创建会员卡产品"""
        product = MembershipCardProduct(
            tenant_id=tenant_id,
            name=data.name,
            card_type=data.card_type,
            price=data.price,
            total_credits=data.total_credits,
            validity_days=data.validity_days,
            applicable_course_ids=data.applicable_course_ids,
            max_weekly_usage=data.max_weekly_usage,
            description=data.description,
            sort_order=data.sort_order,
        )
        db.add(product)
        await db.flush()
        return product

    async def get_product(self, db: AsyncSession, product_id: int, tenant_id: int) -> MembershipCardProduct:
        """获取产品详情"""
        product = await self.product_repo.get_by_id(db, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="产品不存在")
        return product

    async def list_products(
        self,
        db: AsyncSession,
        tenant_id: int,
        *,
        status: int | None = None,
        card_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取产品列表"""
        items, total = await self.product_repo.list_products(
            db, status=status, card_type=card_type, page=page, page_size=page_size,
        )
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    async def update_product(
        self,
        db: AsyncSession,
        product_id: int,
        tenant_id: int,
        data: MembershipCardProductUpdate,
    ) -> MembershipCardProduct:
        """更新产品"""
        product = await self.get_product(db, product_id, tenant_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(product, field, value)
        await db.flush()
        return product

    async def delete_product(self, db: AsyncSession, product_id: int, tenant_id: int) -> None:
        """删除产品（软删除：设置 deleted_at）"""
        product = await self.get_product(db, product_id, tenant_id)
        
        # 检查是否已下架
        if product.status != ProductStatus.OFFLINE.value:
            raise HTTPException(
                status_code=400,
                detail="请先下架该产品后再删除"
            )
        
        # 检查是否有关联的会员卡
        result = await db.execute(
            select(func.count()).where(MembershipCard.product_id == product_id)
        )
        card_count = result.scalar() or 0
        if card_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"该卡类型已被 {card_count} 张会员卡使用，无法删除。请先处理关联的会员卡。"
            )
        
        # 检查是否有关联的消费流水
        result = await db.execute(
            select(func.count()).where(MembershipCardTransaction.card_id.in_(
                select(MembershipCard.id).where(MembershipCard.product_id == product_id)
            ))
        )
        txn_count = result.scalar() or 0
        if txn_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"该卡类型已有 {txn_count} 条消费流水，无法删除。历史数据需要保留。"
            )
        
        product.deleted_at = datetime.now(timezone.utc)
        await db.flush()

    async def restore_product(self, db: AsyncSession, product_id: int, tenant_id: int) -> MembershipCardProduct:
        """恢复已删除的产品（从回收站恢复）"""
        product = await self.product_repo.restore_product(db, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="产品不存在或未被删除")
        return product

    async def list_deleted_products(
        self,
        db: AsyncSession,
        tenant_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取回收站中的产品列表"""
        items, total = await self.product_repo.list_deleted_products(
            db, page=page, page_size=page_size,
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def issue_card(
        self,
        db: AsyncSession,
        data: MembershipCardCreate,
        tenant_id: int,
        operator_id: int | None = None,
        idempotency_key: str | None = None,
        allow_duplicate: bool = False,
    ) -> MembershipCard:
        """发放会员卡
        
        Args:
            allow_duplicate: 是否允许重复发卡（默认False）
                - False: 如果学员已有同产品的有效卡，拒绝发卡
                - True: 允许重复发卡（适用于续卡场景）
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"📥 Service层收到参数: data.allow_duplicate={data.allow_duplicate}, 函数参数allow_duplicate={allow_duplicate}")
        
        # 幂等检查
        if idempotency_key:
            existing = await self.txn_repo.get_by_idempotency_key(db, idempotency_key)
            if existing:
                return await self.card_repo.get_by_id(db, existing.card_id)

        product = None
        if data.product_id:
            product = await self.product_repo.get_by_id(db, data.product_id)
            if not product:
                raise HTTPException(status_code=404, detail="产品不存在")

        # 检查学员是否已有同产品的有效卡
        existing_cards = []
        if data.product_id:
            existing_cards = await self.card_repo.get_active_cards_by_product(
                db, data.student_id, data.product_id, tenant_id
            )
        
        # 如果不是续卡模式，且已有有效卡，则拒绝
        if not allow_duplicate and existing_cards:
            card_count = len(existing_cards)
            
            # 计算最早生效时间（旧卡中最晚的到期时间的次日）
            earliest_valid_from = None
            latest_expire_at = None
            for card in existing_cards:
                if card.expire_at and (latest_expire_at is None or card.expire_at > latest_expire_at):
                    latest_expire_at = card.expire_at
            
            if latest_expire_at:
                from datetime import timedelta
                earliest_valid_from = datetime(
                    year=latest_expire_at.year,
                    month=latest_expire_at.month,
                    day=latest_expire_at.day,
                    hour=0,
                    minute=0,
                    second=0,
                    tzinfo=latest_expire_at.tzinfo or timezone.utc
                ) + timedelta(days=1)
            
            error_msg = f"该学员已有 {card_count} 张同类型有效卡。如需续卡，请修改生效时间后重新提交"
            if earliest_valid_from:
                error_msg += f"，最早生效时间：{earliest_valid_from.strftime('%Y-%m-%d')}"
            
            raise HTTPException(
                status_code=409,  # Conflict
                detail=error_msg
            )
        
        # 如果是续卡模式，计算新卡的最早生效时间
        earliest_valid_from = None
        if allow_duplicate and existing_cards:
            # 找到最晚的到期时间
            latest_expire_at = None
            for card in existing_cards:
                if card.expire_at and (latest_expire_at is None or card.expire_at > latest_expire_at):
                    latest_expire_at = card.expire_at
            
            if latest_expire_at:
                # 新卡的生效时间必须晚于旧卡的到期时间
                # 到期时间是 23:59:59，所以新卡生效时间应该是到期时间的第二天 00:00:00
                from datetime import timedelta
                earliest_valid_from = datetime(
                    year=latest_expire_at.year,
                    month=latest_expire_at.month,
                    day=latest_expire_at.day,
                    hour=0,
                    minute=0,
                    second=0,
                    tzinfo=latest_expire_at.tzinfo or timezone.utc
                ) + timedelta(days=1)

        now = datetime.now(timezone.utc)
        validity_days = data.validity_days or (product.validity_days if product else None)

        # 次卡和期卡必须有有效天数
        card_type = product.card_type if product else "count"
        if card_type in ["count", "period"] and not validity_days:
            raise HTTPException(
                status_code=400, 
                detail=f"{card_type == 'count' and '次卡' or '期卡'}必须设置有效天数（validity_days）"
            )

        # 激活逻辑：
        # - valid_from 为空 → 立即激活（ACTIVE）
        # - valid_from 为过去/现在 → 立即激活（ACTIVE）
        # - valid_from 为未来 → 待激活（PENDING）
        valid_from = data.valid_from
        if valid_from is not None and valid_from.tzinfo is None:
            valid_from = valid_from.replace(tzinfo=timezone.utc)
        valid_from = valid_from or now
        
        # 续卡场景：如果用户传入的生效时间早于最早允许时间，则拒绝
        if earliest_valid_from and valid_from < earliest_valid_from:
            raise HTTPException(
                status_code=400,
                detail=f"续卡生效时间不能早于 {earliest_valid_from.strftime('%Y-%m-%d')}（旧卡到期时间的次日）。"
                       f"如需立即生效，请先将旧卡作废或冻结。"
            )
        
        # 生效时间的时分秒统一为 00:00:00
        valid_from = datetime(
            year=valid_from.year,
            month=valid_from.month,
            day=valid_from.day,
            hour=0,
            minute=0,
            second=0,
            tzinfo=valid_from.tzinfo or timezone.utc
        )
        
        if valid_from <= now:
            status = CardStatus.ACTIVE.value
        else:
            status = CardStatus.PENDING.value

        # 到期时间计算（无论是否立即激活，都基于 valid_from 计算）
        expire_at = None
        if validity_days:
            expire_at = self._calc_expire_at(valid_from, validity_days)

        card = MembershipCard(
            tenant_id=tenant_id,
            student_id=data.student_id,
            product_id=data.product_id,
            card_type=card_type,
            total_credits=data.total_credits or (product.total_credits if product else None),
            used_credits=0,
            valid_from=valid_from,
            expire_at=expire_at,
            applicable_course_ids=data.applicable_course_ids or (product.applicable_course_ids if product else None),
            applicable_course_type_codes=data.applicable_course_type_codes or (product.applicable_course_type_codes if product else None),
            max_weekly_usage=data.max_weekly_usage or (product.max_weekly_usage if product else None),
            status=status,
        )
        db.add(card)
        await db.flush()

        total_credits = card.total_credits or 0
        txn = MembershipCardTransaction(
            tenant_id=tenant_id,
            card_id=card.id,
            operation_type=TransactionType.ISSUE.value,
            change_amount=total_credits,
            balance_after=total_credits,
            operator_id=operator_id,
            idempotency_key=idempotency_key,
            remark=f"发放会员卡{f'（产品：{product.name}）' if product else ''}",
        )
        db.add(txn)
        await db.flush()

        return card

    async def get_card(self, db: AsyncSession, card_id: int, tenant_id: int) -> MembershipCard:
        """获取会员卡详情"""
        card = await self.card_repo.get_by_id(db, card_id)
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        # 多租户隔离验证
        if card.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="无权访问此会员卡")
        return card

    async def get_card_with_lock(
        self, db: AsyncSession, card_id: int, tenant_id: int
    ) -> MembershipCard:
        """获取会员卡并加悲观锁（SELECT FOR UPDATE）
        
        用于并发扣次、恢复次数等需要保证数据一致性的场景
        """
        from sqlalchemy import select
        
        query = select(MembershipCard).where(
            MembershipCard.id == card_id,
            MembershipCard.tenant_id == tenant_id,
        ).with_for_update()
        
        result = await db.execute(query)
        card = result.scalar_one_or_none()
        
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        
        return card

    async def list_cards(
        self,
        db: AsyncSession,
        tenant_id: int,
        *,
        student_id: int | None = None,
        product_id: int | None = None,
        card_type: str | None = None,
        status: int | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取会员卡列表"""
        items, total = await self.card_repo.list_cards(
            db, student_id=student_id, product_id=product_id,
            card_type=card_type, status=status, keyword=keyword, page=page, page_size=page_size,
        )
        # items 已经是 dict 格式（包含关联字段），直接返回
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    async def get_student_active_cards(
        self, db: AsyncSession, student_id: int, tenant_id: int,
    ) -> list[dict]:
        """获取学员的有效会员卡"""
        return await self.card_repo.get_active_cards_by_student(db, student_id, tenant_id)

    async def list_transactions(
        self,
        db: AsyncSession,
        tenant_id: int,
        *,
        card_id: int | None = None,
        operation_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取消费流水列表"""
        items, total = await self.txn_repo.list_transactions(
            db, card_id=card_id, operation_type=operation_type, page=page, page_size=page_size,
        )
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    async def freeze_card(
        self, 
        db: AsyncSession, 
        card_id: int, 
        tenant_id: int, 
        reason: str, 
        operator_id: int,
        freeze_days: int,
        auto_unfreeze: bool = True,
    ) -> MembershipCard:
        """冻结会员卡
        
        Args:
            freeze_days: 冻结天数（1-365天）
            auto_unfreeze: 是否到期自动解冻
        """
        card = await self.get_card(db, card_id, tenant_id)
        if card.status == CardStatus.FROZEN.value:
            raise HTTPException(status_code=400, detail="会员卡已处于冻结状态")
        if card.status == CardStatus.EXPIRED.value:
            raise HTTPException(status_code=400, detail="会员卡已过期，无法冻结")
        if card.status == CardStatus.CANCELLED.value:
            raise HTTPException(status_code=400, detail="会员卡已作废，无法冻结")

        now = datetime.now(timezone.utc)
        
        # 如果卡已过期（expire_at < now），不允许冻结
        if card.expire_at and card.expire_at < now:
            raise HTTPException(
                status_code=400, 
                detail=f"会员卡已于 {card.expire_at.strftime('%Y-%m-%d %H:%M')} 过期，无法冻结"
            )

        card.status = CardStatus.FROZEN.value
        card.frozen_reason = reason
        card.frozen_at = now
        
        # 设置冻结到期时间，并顺延卡的有效期
        frozen_until = now + timedelta(days=freeze_days)
        card.frozen_until = frozen_until
        card.expire_at = card.expire_at + timedelta(days=freeze_days) if card.expire_at else None

        freeze = MembershipCardFreeze(
            tenant_id=tenant_id, 
            card_id=card.id, 
            reason=reason, 
            operator_id=operator_id,
            frozen_at=now,
            unfrozen_at=frozen_until if auto_unfreeze else None
        )
        db.add(freeze)
        await db.flush()
        return card

    async def unfreeze_card(
        self, db: AsyncSession, card_id: int, tenant_id: int, operator_id: int,
    ) -> MembershipCard:
        """解冻会员卡（提前解冻）"""
        card = await self.get_card(db, card_id, tenant_id)
        if card.status != CardStatus.FROZEN.value:
            raise HTTPException(status_code=400, detail="会员卡未处于冻结状态")

        now = datetime.now(timezone.utc)
        card.status = CardStatus.ACTIVE.value
        card.frozen_reason = None
        card.frozen_at = None
        card.frozen_until = None

        freezes, _ = await self.freeze_repo.list_freezes(db, card_id=card_id, page=1, page_size=1)
        if freezes and freezes[0].unfrozen_at is None:
            freezes[0].unfrozen_at = now

        await db.flush()
        return card

    async def activate_card(
        self, db: AsyncSession, card_id: int, tenant_id: int, student_id: int,
    ) -> MembershipCard:
        """学员主动激活会员卡（仅学员本人可操作）
        
        支持场景：
        - 激活待激活的卡（PENDING → ACTIVE）
        - 提前激活冻结的卡（FROZEN → ACTIVE）- 需要验证冻结到期时间
        """
        card = await self.get_card(db, card_id, tenant_id)
        if card.student_id != student_id:
            raise HTTPException(status_code=403, detail="无权操作此会员卡")
        if card.status not in [CardStatus.PENDING.value, CardStatus.FROZEN.value]:
            raise HTTPException(status_code=400, detail="会员卡状态不允许激活")

        # 如果是冻结状态，验证是否允许提前激活
        if card.status == CardStatus.FROZEN.value:
            # 检查是否有冻结到期时间
            if card.frozen_until is None:
                raise HTTPException(status_code=400, detail="无限期冻结，请联系管理员处理")
            
            now = datetime.now(timezone.utc)
            # 如果冻结还未到期，不允许学员提前激活（需要管理员操作）
            if card.frozen_until > now:
                raise HTTPException(
                    status_code=400, 
                    detail=f"会员卡冻结中，到期时间：{card.frozen_until.strftime('%Y-%m-%d %H:%M')}，请联系管理员提前解冻"
                )
            
            # 冻结已到期，清除冻结信息
            card.frozen_reason = None
            card.frozen_at = None
            card.frozen_until = None
        
        # 先计算生效时间和到期时间（用于冲突检查）
        now = datetime.now(timezone.utc)
        valid_from = datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=0,
            minute=0,
            second=0,
            tzinfo=timezone.utc
        )
        
        # 重新计算到期时间
        product = None
        if card.product_id:
            product = await self.product_repo.get_by_id(db, card.product_id)
        
        validity_days = product.validity_days if product else None
        expire_at = self._calc_expire_at(valid_from, validity_days) if validity_days else None
        
        # 临时设置用于冲突检查
        card.valid_from = valid_from
        card.expire_at = expire_at

        # 检查学员是否已有同产品且课程类型重叠的有效卡（防止同一时段多张卡重叠）
        if card.product_id:
            existing_cards = await self.card_repo.get_active_cards_by_product(
                db, card.student_id, card.product_id, tenant_id, exclude_pending=True
            )
            
            # 过滤出课程类型有重叠的卡
            conflicting_cards = []
            new_card_course_types = set(card.applicable_course_type_codes or [])
            
            for existing_card in existing_cards:
                existing_course_types = set(existing_card.applicable_course_type_codes or [])
                # 如果课程类型有交集，说明存在冲突
                if new_card_course_types & existing_course_types:
                    # 进一步检查时间是否重叠
                    if self._check_time_overlap(card, existing_card):
                        conflicting_cards.append(existing_card)
            
            if conflicting_cards:
                card_count = len(conflicting_cards)
                # 获取冲突卡的课程类型名称
                conflict_types = set()
                for c in conflicting_cards:
                    conflict_types.update(c.applicable_course_type_codes or [])
                
                raise HTTPException(
                    status_code=409,
                    detail=f"该学员已有 {card_count} 张同课程类型的有效卡（{', '.join(conflict_types)}）。请先将旧卡作废或冻结后再激活新卡。"
                )

        card.status = CardStatus.ACTIVE.value
        # valid_from 和 expire_at 已在上面设置，无需重复设置

        txn = MembershipCardTransaction(
            tenant_id=tenant_id,
            card_id=card.id,
            operation_type=TransactionType.ISSUE.value,
            change_amount=0,
            balance_after=card.total_credits or 0,
            operator_id=student_id,
            remark="学员主动激活",
        )
        db.add(txn)
        await db.flush()
        return card

    async def admin_activate_card(
        self, db: AsyncSession, card_id: int, tenant_id: int, operator_id: int,
    ) -> MembershipCard:
        """管理员手动激活会员卡"""
        card = await self.get_card(db, card_id, tenant_id)
        if card.status != CardStatus.PENDING.value:
            raise HTTPException(status_code=400, detail="会员卡已激活或已过期，无法重复激活")

        # 检查学员是否已有同产品且课程类型重叠的有效卡（防止同一时段多张卡重叠）
        if card.product_id:
            existing_cards = await self.card_repo.get_active_cards_by_product(
                db, card.student_id, card.product_id, tenant_id, exclude_pending=True
            )
            
            # 过滤出课程类型有重叠的卡
            conflicting_cards = []
            new_card_course_types = set(card.applicable_course_type_codes or [])
            
            for existing_card in existing_cards:
                existing_course_types = set(existing_card.applicable_course_type_codes or [])
                # 如果课程类型有交集，说明存在冲突
                if new_card_course_types & existing_course_types:
                    # 进一步检查时间是否重叠
                    if self._check_time_overlap(card, existing_card):
                        conflicting_cards.append(existing_card)
            
            if conflicting_cards:
                card_count = len(conflicting_cards)
                # 获取冲突卡的课程类型名称
                conflict_types = set()
                for c in conflicting_cards:
                    conflict_types.update(c.applicable_course_type_codes or [])
                
                raise HTTPException(
                    status_code=409,
                    detail=f"该学员已有 {card_count} 张同课程类型的有效卡（{', '.join(conflict_types)}）。请先将旧卡作废或冻结后再激活新卡。"
                )

        now = datetime.now(timezone.utc)
        
        # 先计算生效时间和到期时间（用于冲突检查）
        valid_from = datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=0,
            minute=0,
            second=0,
            tzinfo=timezone.utc
        )
        
        # 重新计算到期时间
        product = None
        if card.product_id:
            product = await self.product_repo.get_by_id(db, card.product_id)
        
        validity_days = product.validity_days if product else None
        expire_at = self._calc_expire_at(valid_from, validity_days) if validity_days else None
        
        # 临时设置用于冲突检查
        card.valid_from = valid_from
        card.expire_at = expire_at

        # 检查学员是否已有同产品且课程类型重叠的有效卡（防止同一时段多张卡重叠）
        if card.product_id:
            existing_cards = await self.card_repo.get_active_cards_by_product(
                db, card.student_id, card.product_id, tenant_id, exclude_pending=True
            )
            
            # 过滤出课程类型有重叠的卡
            conflicting_cards = []
            new_card_course_types = set(card.applicable_course_type_codes or [])
            
            for existing_card in existing_cards:
                existing_course_types = set(existing_card.applicable_course_type_codes or [])
                # 如果课程类型有交集，说明存在冲突
                if new_card_course_types & existing_course_types:
                    # 进一步检查时间是否重叠
                    if self._check_time_overlap(card, existing_card):
                        conflicting_cards.append(existing_card)
            
            if conflicting_cards:
                card_count = len(conflicting_cards)
                # 获取冲突卡的课程类型名称
                conflict_types = set()
                for c in conflicting_cards:
                    conflict_types.update(c.applicable_course_type_codes or [])
                
                raise HTTPException(
                    status_code=409,
                    detail=f"该学员已有 {card_count} 张同课程类型的有效卡（{', '.join(conflict_types)}）。请先将旧卡作废或冻结后再激活新卡。"
                )

        card.status = CardStatus.ACTIVE.value
        # valid_from 和 expire_at 已在上面设置，无需重复设置

        txn = MembershipCardTransaction(
            tenant_id=tenant_id,
            card_id=card.id,
            operation_type=TransactionType.ISSUE.value,
            change_amount=0,
            balance_after=card.total_credits or 0,
            operator_id=operator_id,
            remark="管理员手动激活",
        )
        db.add(txn)
        await db.flush()
        return card

    async def deduct_credit(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        booking_id: int | None = None,
        operator_id: int | None = None,
        idempotency_key: str | None = None,
    ) -> MembershipCard:
        """扣减次数（约课时调用）
        
        使用悲观锁防止并发扣次导致次数为负
        """
        # 幂等检查
        if idempotency_key:
            existing = await self.txn_repo.get_by_idempotency_key(db, idempotency_key)
            if existing:
                return await self.card_repo.get_by_id(db, existing.card_id)

        # 使用悲观锁获取会员卡（SELECT FOR UPDATE）
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if card.status != CardStatus.ACTIVE.value:
            raise HTTPException(status_code=400, detail="会员卡状态异常，无法扣次")
        
        # 期卡/无限卡：total_credits 为 None，不限制次数
        if card.total_credits is None:
            balance_after = 0
        else:
            # 次卡：检查余额是否充足
            if card.used_credits >= card.total_credits:
                raise HTTPException(status_code=400, detail="会员卡次数已用完")
            
            # 数据一致性检查：防止历史数据异常导致负余额
            if card.used_credits < 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"会员卡数据异常（已使用次数为负：{card.used_credits}），请联系管理员"
                )
            
            card.used_credits += 1
            balance_after = card.total_credits - card.used_credits
            
            # 最终安全检查：确保余额不为负
            if balance_after < 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"会员卡扣次异常（余额计算为负：{balance_after}），请联系管理员检查数据"
                )

        txn = MembershipCardTransaction(
            tenant_id=tenant_id,
            card_id=card.id,
            booking_id=booking_id,
            operation_type=TransactionType.CONSUME.value,
            change_amount=-1,
            balance_after=balance_after,
            operator_id=operator_id,
            idempotency_key=idempotency_key,
            remark="约课扣次",
        )
        db.add(txn)
        await db.flush()
        return card

    async def restore_credit(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        booking_id: int | None = None,
        operator_id: int | None = None,
        idempotency_key: str | None = None,
        remark: str = "取消约课恢复次数",
    ) -> MembershipCard:
        """恢复次数（取消约课时调用）
        
        使用悲观锁防止并发恢复导致数据不一致
        """
        # 幂等检查
        if idempotency_key:
            existing = await self.txn_repo.get_by_idempotency_key(db, idempotency_key)
            if existing:
                return await self.card_repo.get_by_id(db, existing.card_id)

        # 使用悲观锁获取会员卡
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if card.used_credits <= 0:
            raise HTTPException(status_code=400, detail="会员卡已使用次数为0，无法恢复")

        card.used_credits -= 1
        # 期卡/无限卡：total_credits 为 None，余额记为 0
        balance_after = (card.total_credits - card.used_credits) if card.total_credits is not None else 0

        txn = MembershipCardTransaction(
            tenant_id=tenant_id,
            card_id=card.id,
            booking_id=booking_id,
            operation_type=TransactionType.RESTORE.value,
            change_amount=1,
            balance_after=balance_after,
            operator_id=operator_id,
            idempotency_key=idempotency_key,
            remark=remark,
        )
        db.add(txn)
        await db.flush()
        return card

    @staticmethod
    def _check_time_overlap(card1: MembershipCard, card2: MembershipCard) -> bool:
        """检查两张卡的时间是否重叠
        
        重叠条件：
        - card1 的 valid_from <= card2 的 expire_at
        - card2 的 valid_from <= card1 的 expire_at
        """
        # 如果任一卡没有有效期，认为不重叠（无限卡）
        if card1.expire_at is None or card2.expire_at is None:
            return False
        if card1.valid_from is None or card2.valid_from is None:
            return False
        
        # 检查时间重叠
        return card1.valid_from <= card2.expire_at and card2.valid_from <= card1.expire_at

    @staticmethod
    def _calc_expire_at(start_at: datetime, days: int) -> datetime:
        """计算到期时间，时分秒统一设置为23:59:59"""
        expire_date = start_at.date() + timedelta(days=days)
        return datetime(
            year=expire_date.year,
            month=expire_date.month,
            day=expire_date.day,
            hour=23,
            minute=59,
            second=59,
            tzinfo=start_at.tzinfo or timezone.utc
        )

    async def extend_card(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        extend_days: int,
        operator_id: int,
        remark: str = "付费延期",
    ) -> MembershipCard:
        """延长会员卡有效期
        
        Args:
            extend_days: 延长天数
            remark: 延期原因
        """
        card = await self.get_card(db, card_id, tenant_id)
        if card.status not in [CardStatus.ACTIVE.value, CardStatus.FROZEN.value]:
            raise HTTPException(status_code=400, detail="会员卡状态异常，无法延期")
        if not card.expire_at:
            raise HTTPException(status_code=400, detail="无限卡无需延期")

        old_expire_at = card.expire_at
        card.expire_at = card.expire_at + timedelta(days=extend_days)

        txn = MembershipCardTransaction(
            tenant_id=tenant_id,
            card_id=card.id,
            operation_type=TransactionType.ADJUST.value,
            change_amount=0,
            balance_after=(card.total_credits or 0) - card.used_credits,
            operator_id=operator_id,
            remark=f"{remark}：有效期延长{extend_days}天（{old_expire_at.strftime('%Y-%m-%d')} → {card.expire_at.strftime('%Y-%m-%d')}）",
        )
        db.add(txn)
        await db.flush()
        return card

    async def cancel_card(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        reason: str,
        operator_id: int,
    ) -> MembershipCard:
        """作废会员卡（管理员操作）
        
        适用场景：
        - 发放错误的卡
        - 学员退卡
        - 其他需要作废的情况
        """
        card = await self.get_card(db, card_id, tenant_id)
        if card.status == CardStatus.CANCELLED.value:
            raise HTTPException(status_code=400, detail="会员卡已处于作废状态")
        if card.status == CardStatus.REFUNDED.value:
            raise HTTPException(status_code=400, detail="会员卡已退款，无需重复作废")

        now = datetime.now(timezone.utc)
        remaining = (card.total_credits or 0) - card.used_credits
        
        # 如果有剩余次数，记录作废流水
        if remaining > 0:
            txn = MembershipCardTransaction(
                tenant_id=tenant_id,
                card_id=card.id,
                operation_type=TransactionType.EXPIRE.value,
                change_amount=-remaining,
                balance_after=0,
                operator_id=operator_id,
                remark=f"会员卡作废（原因：{reason}），剩余{remaining}次清零",
            )
            db.add(txn)
            card.used_credits = card.total_credits

        # 更新卡状态
        card.status = CardStatus.CANCELLED.value
        card.cancelled_at = now
        card.cancelled_reason = reason
        card.frozen_reason = None
        card.frozen_at = None
        card.frozen_until = None

        await db.flush()
        return card


membership_card_service = MembershipCardService()