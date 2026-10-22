"""
Membership Card Service - 会员卡业务逻辑层

包含：
- 产品管理（CRUD）
- 会员卡发放与管理
- 课时扣减与恢复
- 消费流水记录
- 冻结/解冻操作
"""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.membership.models import (
    CardStatus,
    CardType,
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
    MembershipCardProductUpdate,
    MembershipCardResponse,
)

logger = logging.getLogger(__name__)


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
            applicable_course_type_code=data.applicable_course_type_code,
            max_weekly_usage=data.max_weekly_usage,
            description=data.description,
            sort_order=data.sort_order,
        )
        db.add(product)
        await db.flush()
        return product

    async def get_product(
        self, db: AsyncSession, product_id: int, tenant_id: int
    ) -> MembershipCardProduct:
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
            db,
            status=status,
            card_type=card_type,
            page=page,
            page_size=page_size,
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
            raise HTTPException(status_code=400, detail="请先下架该产品后再删除")

        # 检查是否有关联的有效会员卡（排除已作废的卡）
        # 有效状态：PENDING(0), ACTIVE(1), EXPIRED(2), FROZEN(3)
        # 无效状态：CANCELLED(6)
        valid_statuses = [
            CardStatus.PENDING.value,
            CardStatus.ACTIVE.value,
            CardStatus.EXPIRED.value,
            CardStatus.FROZEN.value,
        ]
        result = await db.execute(
            select(func.count()).where(
                MembershipCard.product_id == product_id,
                MembershipCard.status.in_(valid_statuses),
            )
        )
        card_count = result.scalar() or 0
        if card_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"该卡类型已被 {card_count} 张有效会员卡使用，无法删除。请先作废或退款关联的会员卡。",
            )

        # 检查是否有关联的消费流水
        result = await db.execute(
            select(func.count()).where(
                MembershipCardTransaction.card_id.in_(
                    select(MembershipCard.id).where(MembershipCard.product_id == product_id)
                )
            )
        )
        txn_count = result.scalar() or 0
        if txn_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"该卡类型已有 {txn_count} 条消费流水，无法删除。历史数据需要保留。",
            )

        product.deleted_at = datetime.now(UTC)
        await db.flush()

    async def batch_delete_products(
        self,
        db: AsyncSession,
        product_ids: list[int],
        tenant_id: int,
    ) -> dict:
        """批量删除卡类型产品（软删除）

        Returns:
            dict: {
                "success_count": 成功删除的数量,
                "failed_count": 失败的数量,
                "failed_products": 失败的产品ID和原因列表
            }
        """
        success_count = 0
        failed_count = 0
        failed_products = []

        for product_id in product_ids:
            try:
                await self.delete_product(db, product_id, tenant_id)
                success_count += 1
            except HTTPException as e:
                failed_count += 1
                failed_products.append({"product_id": product_id, "error": e.detail})
            except Exception as e:
                failed_count += 1
                failed_products.append({"product_id": product_id, "error": str(e)})

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "failed_products": failed_products,
            "total": len(product_ids),
        }

    async def restore_product(
        self, db: AsyncSession, product_id: int, tenant_id: int
    ) -> MembershipCardProduct:
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
            db,
            page=page,
            page_size=page_size,
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

        # 检查学员是否已有同课程类型的有效卡（防止不同产品但课程类型重叠）
        now = datetime.now(UTC)
        validity_days = data.validity_days or (product.validity_days if product else None)
        card_type = product.card_type if product else "count"

        # 获取新卡的课程类型（单选字段）
        new_card_course_type = data.applicable_course_type_code or (
            product.applicable_course_type_code if product else None
        )

        # F6.3 T6.3.1：期卡发卡强制 PENDING、有效期留空，由首次完成课程时激活；
        # 发卡期不做“同课程类型时间重叠”与续卡最早生效计算。
        if card_type != CardType.PERIOD.value and new_card_course_type:
            # 使用悲观锁获取学员所有有效卡（防止并发发卡导致冲突检查失效）
            locked_result = await db.execute(
                select(MembershipCard)
                .where(
                    MembershipCard.student_id == data.student_id,
                    MembershipCard.tenant_id == tenant_id,
                    MembershipCard.status.in_([
                        CardStatus.PENDING.value, CardStatus.ACTIVE.value, CardStatus.FROZEN.value,
                    ]),
                )
                .with_for_update()
            )
            locked_existing_cards = locked_result.scalars().all()
            all_existing_cards = [
                {"id": c.id, "applicable_course_type_code": c.applicable_course_type_code,
                 "valid_from": c.valid_from, "expire_at": c.expire_at}
                for c in locked_existing_cards
            ]

            # 计算新卡的生效时间和到期时间（用于时间重叠检查）
            temp_valid_from = data.valid_from or now
            if temp_valid_from.tzinfo is None:
                temp_valid_from = temp_valid_from.replace(tzinfo=UTC)
            temp_valid_from = datetime(
                year=temp_valid_from.year,
                month=temp_valid_from.month,
                day=temp_valid_from.day,
                hour=0,
                minute=0,
                second=0,
                tzinfo=temp_valid_from.tzinfo or UTC,
            )

            temp_expire_at = None
            if validity_days:
                temp_expire_at = self._calc_expire_at(temp_valid_from, validity_days)

            # 过滤出课程类型相同且时间重叠的卡
            conflicting_cards = []
            for existing_card_dict in all_existing_cards:
                # 获取现有卡的课程类型（单选字段）
                existing_course_type = existing_card_dict.get("applicable_course_type_code")
                # 如果课程类型相同
                if existing_course_type == new_card_course_type:
                    # 检查时间是否重叠
                    existing_valid_from = existing_card_dict.get("valid_from")
                    existing_expire_at = existing_card_dict.get("expire_at")

                    if existing_valid_from and existing_expire_at and temp_expire_at:
                        # 检查时间重叠：新卡的valid_from <= 旧卡的expire_at AND 旧卡的valid_from <= 新卡的expire_at
                        if (
                            temp_valid_from <= existing_expire_at
                            and existing_valid_from <= temp_expire_at
                        ):
                            conflicting_cards.append(existing_card_dict)

            # 如果不是续卡模式，且有冲突卡，则拒绝
            if conflicting_cards and not allow_duplicate:
                card_count = len(conflicting_cards)
                conflict_type = new_card_course_type

                # 计算最早可选生效时间（旧卡到期时间的次日）
                earliest_date = None
                for card in conflicting_cards:
                    expire_at = card.expire_at
                    if expire_at:
                        candidate = datetime(
                            year=expire_at.year,
                            month=expire_at.month,
                            day=expire_at.day,
                            hour=0,
                            minute=0,
                            second=0,
                            tzinfo=expire_at.tzinfo or UTC,
                        ) + timedelta(days=1)
                        if earliest_date is None or candidate > earliest_date:
                            earliest_date = candidate

                detail_msg = f"该学员已有 {card_count} 张同课程类型的有效卡（{conflict_type}）。请先将旧卡作废或冻结后再发放新卡。"
                if earliest_date:
                    detail_msg += (
                        f" 如需续卡，最早生效时间为 {earliest_date.strftime('%Y-%m-%d')}。"
                    )

                raise HTTPException(
                    status_code=409,
                    detail=detail_msg,
                )

        # 如果是续卡模式，计算新卡的最早生效时间
        earliest_valid_from = None
        if card_type != CardType.PERIOD.value and allow_duplicate and product:
            # 获取学员所有同产品的有效卡
            existing_cards = await self.card_repo.get_active_cards_by_product(
                db, data.student_id, data.product_id, tenant_id
            )

            if existing_cards:
                # 找到最晚的到期时间
                latest_expire_at = None
                for card in existing_cards:
                    if card.expire_at and (
                        latest_expire_at is None or card.expire_at > latest_expire_at
                    ):
                        latest_expire_at = card.expire_at

                if latest_expire_at:
                    # 新卡的生效时间必须晚于旧卡的到期时间
                    # 到期时间是 23:59:59，所以新卡生效时间应该是到期时间的第二天 00:00:00
                    earliest_valid_from = datetime(
                        year=latest_expire_at.year,
                        month=latest_expire_at.month,
                        day=latest_expire_at.day,
                        hour=0,
                        minute=0,
                        second=0,
                        tzinfo=latest_expire_at.tzinfo or UTC,
                    ) + timedelta(days=1)

        # 次卡和期卡必须有有效天数
        if card_type in [CardType.COUNT.value, CardType.PERIOD.value] and not validity_days:
            raise HTTPException(
                status_code=400,
                detail=f"{'次卡' if card_type == CardType.COUNT.value else '期卡'}必须设置有效天数（validity_days）",
            )

        if card_type == CardType.PERIOD.value:
            # F6.3 T6.3.1：期卡发卡强制 PENDING，生效/到期时间留空，
            # 由首次完成课程（含 NO_SHOW）时按排期日 + validity_days 激活。
            # 忽略入参 valid_from（D9：发卡不开始计时）。
            if data.valid_from is not None:
                logger.warning(
                    "[MembershipCardService] 期卡发卡忽略 valid_from 入参: student_id=%s",
                    data.student_id,
                )
            valid_from = None
            expire_at = None
            status = CardStatus.PENDING.value
        else:
            # 非期卡：保持既有逻辑不变
            # - valid_from 为空 → 立即激活（ACTIVE）
            # - valid_from 为过去/现在 → 立即激活（ACTIVE）
            # - valid_from 为未来 → 待激活（PENDING）
            valid_from = data.valid_from
            if valid_from is not None and valid_from.tzinfo is None:
                valid_from = valid_from.replace(tzinfo=UTC)
            valid_from = valid_from or now

            # 续卡场景：如果用户传入的生效时间早于最早允许时间，则拒绝
            if earliest_valid_from and valid_from < earliest_valid_from:
                raise HTTPException(
                    status_code=409,
                    detail=f"续卡生效时间不能早于 {earliest_valid_from.strftime('%Y-%m-%d')}（旧卡到期时间的次日）。"
                    f"如需立即生效，请先将旧卡作废或冻结。",
                )

            # 生效时间的时分秒统一为 00:00:00
            valid_from = datetime(
                year=valid_from.year,
                month=valid_from.month,
                day=valid_from.day,
                hour=0,
                minute=0,
                second=0,
                tzinfo=valid_from.tzinfo or UTC,
            )

            if valid_from <= now:
                status = CardStatus.ACTIVE.value
            else:
                status = CardStatus.PENDING.value

            # 到期时间计算（无论是否立即激活，都基于 valid_from 计算）
            expire_at = None
            if validity_days:
                expire_at = self._calc_expire_at(valid_from, validity_days)

        # 确定适用课程类型（单选）
        applicable_course_type_code = data.applicable_course_type_code or (
            product.applicable_course_type_code if product else None
        )

        card = MembershipCard(
            tenant_id=tenant_id,
            student_id=data.student_id,
            product_id=data.product_id,
            card_type=card_type,
            card_no=MembershipCard.generate_card_no(),
            total_credits=data.total_credits or (product.total_credits if product else None),
            used_credits=0,
            valid_from=valid_from,
            expire_at=expire_at,
            validity_days=validity_days if card_type == CardType.PERIOD.value else None,
            applicable_course_ids=data.applicable_course_ids
            or (product.applicable_course_ids if product else None),
            applicable_course_type_code=applicable_course_type_code,
            max_weekly_usage=data.max_weekly_usage
            or (product.max_weekly_usage if product else None),
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

        query = (
            select(MembershipCard)
            .where(
                MembershipCard.id == card_id,
                MembershipCard.tenant_id == tenant_id,
            )
            # FOR NO KEY UPDATE（key_share=True）：与 booking 插入时 FK 持有的
            # FOR KEY SHARE 兼容，避免并发预约“先拿 KEY SHARE 再升级 FOR UPDATE”
            # 的死锁；同时与其它 NO KEY UPDATE 互斥，保证扣次串行化。
            .with_for_update(key_share=True)
            # 锁等待期间该行可能已被并发事务扣次/改状态；必须用最新行覆盖
            # identity map，否则锁后读到陈旧 used_credits 会导致超扣。
            .execution_options(populate_existing=True)
        )

        result = await db.execute(query)
        card = result.scalar_one_or_none()

        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")

        return card

    # ============================================================
    # F6.3 期卡预约校验 / 首次完成激活
    # ============================================================

    @staticmethod
    def is_period_pending_bookable(card: MembershipCard) -> bool:
        """D9：期卡 PENDING 且尚未确定生效日（valid_from IS NULL）时可预约。

        带有效生效日的 PENDING（历史/续卡数据）仍不可预约，由 D4 拒绝。
        """
        return (
            card.card_type == CardType.PERIOD.value
            and card.status == CardStatus.PENDING.value
            and card.valid_from is None
        )

    @staticmethod
    def _card_field(card, name: str):
        """统一读取 ORM 实体或 dict 上的会员卡字段。

        推荐链路的数据源是 ``get_all_cards_by_student`` 返回的 dict，
        下单校验链路传入 ORM 实体，两种形态共用同一判定函数。
        """
        if isinstance(card, dict):
            return card.get(name)
        return getattr(card, name, None)

    @staticmethod
    def _card_status_unavailable_reason(status) -> str:
        """按卡状态生成不可用原因（仅非可用状态调用）。"""
        if status == CardStatus.CANCELLED.value:
            return "已作废"
        if status == CardStatus.EXPIRED.value:
            return "已过期"
        if status == CardStatus.FROZEN.value:
            return "已冻结"
        if status == CardStatus.PENDING.value:
            return "未激活"
        return "已停用"

    def card_unavailable_reason(
        self,
        card,
        *,
        schedule_start_at: datetime,
        course_id: int,
        course_type_code: str | None,
    ) -> str | None:
        """基础不可用原因（状态 + 排期日有效期 + 课程适用性）。

        可用返回 ``None``。仅覆盖共享判定；次卡余额与期卡区间冲突不在此处。
        有效期按“排期日”比较（含 expire_at 当天），不得使用 now。
        """
        card_type = self._card_field(card, "card_type")
        status = self._card_field(card, "status")
        valid_from = self._card_field(card, "valid_from")
        expire_at = self._card_field(card, "expire_at")
        applicable_course_type_code = self._card_field(
            card, "applicable_course_type_code"
        )
        applicable_course_ids = self._card_field(card, "applicable_course_ids")

        if card_type not in (
            CardType.COUNT.value,
            CardType.UNLIMITED.value,
            CardType.PERIOD.value,
        ):
            return "不支持的卡类型"

        if card_type in (CardType.COUNT.value, CardType.UNLIMITED.value):
            if status != CardStatus.ACTIVE.value:
                return self._card_status_unavailable_reason(status)
        else:  # PERIOD：ACTIVE 或 PENDING 且 valid_from IS NULL（D9）可预约
            if status != CardStatus.ACTIVE.value and not (
                status == CardStatus.PENDING.value and valid_from is None
            ):
                return self._card_status_unavailable_reason(status)

        schedule_date = schedule_start_at.date()
        if valid_from is not None and schedule_date < valid_from.date():
            return f"尚未生效（{valid_from.strftime('%Y-%m-%d')} 生效）"
        if expire_at is not None and schedule_date > expire_at.date():
            return f"已过期（{expire_at.strftime('%Y-%m-%d')} 到期）"

        if applicable_course_type_code:
            if (
                not course_type_code
                or applicable_course_type_code != course_type_code
            ):
                return "不适用于此课程类型"
        if applicable_course_ids and course_id not in applicable_course_ids:
            return "不适用于此课程"

        return None

    def is_bookable_card(
        self,
        card: MembershipCard,
        *,
        schedule_start_at: datetime,
        course_id: int,
        course_type_code: str | None,
    ) -> bool:
        """基础可预约判定（状态 + 排期日有效期 + 课程适用性）。

        有效期按“排期日”比较（含 expire_at 当天），不得使用 now。
        """
        return (
            self.card_unavailable_reason(
                card,
                schedule_start_at=schedule_start_at,
                course_id=course_id,
                course_type_code=course_type_code,
            )
            is None
        )

    def card_recommend_unavailable_reason(
        self,
        card,
        *,
        schedule_start_at: datetime,
        course_id: int,
        course_type_code: str | None,
    ) -> str | None:
        """推荐链路不可用原因：在共享判定之上追加次卡余额校验。

        期卡区间冲突不在推荐阶段预校验（K4），仍由下单校验负责。
        """
        reason = self.card_unavailable_reason(
            card,
            schedule_start_at=schedule_start_at,
            course_id=course_id,
            course_type_code=course_type_code,
        )
        if reason is None and self._card_field(card, "card_type") == CardType.COUNT.value:
            if (self._card_field(card, "remaining_credits") or 0) <= 0:
                return "次卡已用完"
        return reason

    async def validate_card_for_booking(
        self,
        db: AsyncSession,
        *,
        card_id: int,
        tenant_id: int,
        student_id: int,
        schedule_id: int,
        schedule_start_at: datetime,
        course_id: int,
        course_type_code: str | None,
    ) -> dict:
        """预约前的会员卡基础校验（无锁快路径）。

        Returns:
            {"card_type", "deduct", "validity_days", "status", "valid_from"}
        """
        card = await self.card_repo.get_by_id(db, card_id)
        if not card or card.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.student_id != student_id:
            raise HTTPException(status_code=403, detail="无权使用此会员卡")

        if card.card_type == CardType.COUNT.value:
            if card.status != CardStatus.ACTIVE.value:
                raise HTTPException(status_code=400, detail="会员卡状态异常，无法预约")
        elif card.card_type == CardType.UNLIMITED.value:
            if card.status != CardStatus.ACTIVE.value:
                raise HTTPException(status_code=400, detail="会员卡状态异常，无法预约")
        elif card.card_type == CardType.PERIOD.value:
            # ACTIVE：已激活；PENDING 且 valid_from IS NULL：D9 可预约
            if card.status != CardStatus.ACTIVE.value and not self.is_period_pending_bookable(card):
                raise HTTPException(status_code=400, detail="会员卡状态异常，无法预约")
        else:
            raise HTTPException(status_code=400, detail="会员卡类型异常，无法预约")

        # D4：按排期日判断有效期（含 expire_at 当天）
        schedule_date = schedule_start_at.date()
        if card.valid_from is not None and schedule_date < card.valid_from.date():
            raise HTTPException(
                status_code=400,
                detail=f"会员卡尚未生效，生效时间：{card.valid_from.strftime('%Y-%m-%d')}",
            )
        if card.expire_at is not None and schedule_date > card.expire_at.date():
            raise HTTPException(
                status_code=400,
                detail=f"会员卡已过期，到期时间：{card.expire_at.strftime('%Y-%m-%d')}",
            )

        if card.applicable_course_type_code and (
            not course_type_code
            or card.applicable_course_type_code != course_type_code
        ):
            raise HTTPException(status_code=400, detail="该会员卡不适用于此课程类型")
        if card.applicable_course_ids and course_id not in card.applicable_course_ids:
            raise HTTPException(status_code=400, detail="该会员卡不适用于此课程")

        return {
            "card_type": card.card_type,
            "deduct": card.card_type == CardType.COUNT.value,
            "validity_days": card.validity_days,
            "status": card.status,
            "valid_from": card.valid_from,
        }

    async def lock_student_cards_for_booking_change(
        self,
        db: AsyncSession,
        *,
        student_id: int,
        tenant_id: int,
    ) -> list[MembershipCard]:
        """锁定学员卡集（id ASC），供改期/改派回补与扣次复用。

        F6.5：旧卡可能已过期/冻结/作废，因此覆盖全部状态，避免
        ``restore_credit`` 取不到旧卡或漏锁导致并发不一致。
        """
        return await self.card_repo.get_cards_for_update_by_student(
            db,
            student_id,
            tenant_id,
            statuses=(
                CardStatus.PENDING.value,
                CardStatus.ACTIVE.value,
                CardStatus.EXPIRED.value,
                CardStatus.FROZEN.value,
                CardStatus.CANCELLED.value,
            ),
        )

    async def validate_period_card_booking(
        self,
        db: AsyncSession,
        *,
        card_id: int,
        tenant_id: int,
        student_id: int,
        schedule_start_at: datetime,
        anchor_start_at: datetime | None = None,
    ) -> MembershipCard:
        """期卡预约的预期有效期窗口 + 冲突预校验（加锁，不写任何数据）。

        锚点 = 该卡最早非取消预约的排期日；无历史预约时取当前排期日。
        预期窗口 = [锚点 00:00:00, 锚点 + validity_days - 1 的 23:59:59]。
        """
        cards = await self.card_repo.get_cards_for_update_by_student(
            db, student_id, tenant_id
        )
        card = next((c for c in cards if c.id == card_id), None)
        if card is None:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="无权使用此会员卡")

        if not self.is_period_pending_bookable(card):
            raise HTTPException(status_code=400, detail="会员卡状态异常，无法预约")

        validity_days = card.validity_days
        if not validity_days and card.product_id:
            product = await self.product_repo.get_by_id(db, card.product_id)
            validity_days = product.validity_days if product else None
        if not validity_days:
            raise HTTPException(
                status_code=400, detail="期卡缺少有效天数，无法预约，请联系管理员"
            )

        anchor = anchor_start_at or schedule_start_at
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=UTC)
        expected_valid_from = datetime(
            year=anchor.year,
            month=anchor.month,
            day=anchor.day,
            hour=0,
            minute=0,
            second=0,
            tzinfo=anchor.tzinfo or UTC,
        )
        expected_expire_at = self._calc_expire_at(expected_valid_from, validity_days)

        schedule_date = schedule_start_at.date()
        if not (
            expected_valid_from.date()
            <= schedule_date
            <= expected_expire_at.date()
        ):
            raise HTTPException(
                status_code=400, detail="该排期超出此期卡的有效期窗口"
            )

        # 冲突集合：同学员、同租户、同课程类型、排除自身、有效期均非空
        if card.applicable_course_type_code:
            for existing_card in cards:
                if existing_card.id == card.id:
                    continue
                if existing_card.applicable_course_type_code != card.applicable_course_type_code:
                    continue
                if existing_card.valid_from is None or existing_card.expire_at is None:
                    continue
                if (
                    expected_valid_from <= existing_card.expire_at
                    and existing_card.valid_from <= expected_expire_at
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="期卡生效区间与已有会员卡重叠，无法预约",
                    )

        return card

    async def activate_period_card_on_completion(
        self,
        db: AsyncSession,
        *,
        card_id: int,
        booking_id: int,
        tenant_id: int,
        schedule_start_at: datetime,
        operator_id: int | None = None,
    ) -> MembershipCard:
        """期卡首次完成课程（COMPLETED / NO_SHOW）时激活。

        - 幂等：``booking_{booking_id}_period_activate`` 流水存在则直接返回。
        - 行锁：锁定学员卡集（id ASC）后重检状态。
        - fail-closed：缺 validity_days / 区间冲突时抛异常，由调用方回滚事务，
          卡保持 PENDING，下一轮 finalize 重试。
        - 不 commit（由调用方统一提交）。
        """
        idempotency_key = f"booking_{booking_id}_period_activate"
        existing_txn = await self.txn_repo.get_by_idempotency_key(db, idempotency_key)
        if existing_txn:
            existing_card = await self.card_repo.get_by_id(db, existing_txn.card_id)
            if existing_card:
                return existing_card

        card = await self.card_repo.get_by_id(db, card_id)
        if not card or card.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.card_type != CardType.PERIOD.value:
            return card

        cards = await self.card_repo.get_cards_for_update_by_student(
            db, card.student_id, tenant_id
        )
        locked_card = next((c for c in cards if c.id == card_id), None)
        if locked_card is None:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        card = locked_card

        # 锁后状态重检
        if card.status == CardStatus.ACTIVE.value:
            return card
        if card.status in (CardStatus.EXPIRED.value, CardStatus.CANCELLED.value):
            logger.warning(
                "[MembershipCardService] 期卡已完成终态，跳过激活: card_id=%s status=%s",
                card.id,
                card.status,
            )
            return card
        if card.status == CardStatus.FROZEN.value:
            # PENDING 已在 freeze_card 禁止冻结；此处仅兼容历史数据
            logger.warning(
                "[MembershipCardService] 冻结期卡跳过激活: card_id=%s", card.id
            )
            return card
        if card.status != CardStatus.PENDING.value:
            raise HTTPException(status_code=400, detail="会员卡状态异常，无法激活")

        validity_days = card.validity_days
        if not validity_days and card.product_id:
            product = await self.product_repo.get_by_id(db, card.product_id)
            validity_days = product.validity_days if product else None
        if not validity_days:
            logger.error(
                "[MembershipCardService] 期卡缺少 validity_days，激活失败: card_id=%s booking_id=%s",
                card.id,
                booking_id,
            )
            raise HTTPException(status_code=400, detail="期卡缺少有效天数，无法激活")

        start_at = schedule_start_at
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=UTC)
        valid_from = datetime(
            year=start_at.year,
            month=start_at.month,
            day=start_at.day,
            hour=0,
            minute=0,
            second=0,
            tzinfo=start_at.tzinfo or UTC,
        )
        expire_at = self._calc_expire_at(valid_from, validity_days)

        if card.applicable_course_type_code:
            for existing_card in cards:
                if existing_card.id == card.id:
                    continue
                if existing_card.applicable_course_type_code != card.applicable_course_type_code:
                    continue
                if existing_card.valid_from is None or existing_card.expire_at is None:
                    continue
                if (
                    valid_from <= existing_card.expire_at
                    and existing_card.valid_from <= expire_at
                ):
                    logger.error(
                        "[MembershipCardService] 期卡激活冲突: card_id=%s conflict_card_id=%s",
                        card.id,
                        existing_card.id,
                    )
                    raise HTTPException(
                        status_code=409,
                        detail="期卡生效区间与已有会员卡重叠，无法激活",
                    )

        card.status = CardStatus.ACTIVE.value
        card.valid_from = valid_from
        card.expire_at = expire_at
        card.frozen_reason = None
        card.frozen_at = None
        card.frozen_until = None

        txn = MembershipCardTransaction(
            tenant_id=tenant_id,
            card_id=card.id,
            booking_id=booking_id,
            operation_type=TransactionType.ISSUE.value,
            change_amount=0,
            balance_after=0,
            operator_id=operator_id,
            idempotency_key=idempotency_key,
            remark="首次完成课程自动激活期卡",
        )
        db.add(txn)
        await db.flush()
        return card

    async def list_cards(
        self,
        db: AsyncSession,
        tenant_id: int,
        *,
        student_id: int | None = None,
        product_id: int | None = None,
        card_type: str | None = None,
        status: list[int] | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取会员卡列表"""
        items, total = await self.card_repo.list_cards(
            db,
            student_id=student_id,
            product_id=product_id,
            card_type=card_type,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        # items 已经是 dict 格式（包含关联字段），直接返回
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    async def get_student_all_cards(
        self,
        db: AsyncSession,
        student_id: int,
        tenant_id: int,
    ) -> list[dict]:
        """获取学员的所有会员卡（包含已过期、已作废）"""
        cards = await self.card_repo.get_all_cards_by_student(db, student_id, tenant_id)

        # 为冻结卡附加冲突检查信息
        for card in cards:
            if card.get("status") == CardStatus.FROZEN.value and card.get("frozen_until"):
                conflict_check = await self.check_card_conflict(db, card["id"], tenant_id)
                card["has_conflict"] = conflict_check["has_conflict"]
                card["conflict_count"] = conflict_check["conflict_count"]

        return cards

    @staticmethod
    def _as_aware(value: datetime | None) -> datetime | None:
        """统一时区，避免排序键比较 naive/aware 混用。"""
        if value is None:
            return None
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    @classmethod
    def _recommend_sort_key(cls, card) -> tuple:
        """D6 排序：expire_at ASC（NULL 最后）→ remaining ASC（None 最后）
        → created_at ASC → id ASC。"""
        expire_at = cls._as_aware(cls._card_field(card, "expire_at"))
        remaining = cls._card_field(card, "remaining_credits")
        created_at = cls._as_aware(cls._card_field(card, "created_at"))
        max_dt = datetime.max.replace(tzinfo=UTC)
        return (
            expire_at is None,
            expire_at or max_dt,
            remaining is None,
            remaining if remaining is not None else 0,
            created_at or max_dt,
            cls._card_field(card, "id") or 0,
        )

    @staticmethod
    def _recommend_message(
        total_cards: int,
        available_count: int,
        reasons: list[str],
    ) -> str | None:
        """无可用卡时的聚合文案；有可用卡返回 None。"""
        if total_cards == 0:
            return "您还没有会员卡"
        if available_count == 0:
            return "暂无可用会员卡：" + "；".join(dict.fromkeys(reasons))
        return None

    async def recommend_card_for_schedule(
        self,
        db: AsyncSession,
        student_id: int,
        tenant_id: int,
        schedule_id: int,
    ) -> dict:
        """按排期推荐学员可用会员卡（只读，无锁、无写库）。

        跨模块只读取排期（ScheduleService），卡数据复用租户感知 Repository。
        """
        from app.modules.schedule.service import ScheduleService

        schedule = await ScheduleService().get_schedule_by_id(db, schedule_id)
        if schedule.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="排期不存在")

        cards = await self.card_repo.get_all_cards_by_student(db, student_id, tenant_id)
        available: list[dict] = []
        reasons: list[str] = []
        for card in cards:
            reason = self.card_recommend_unavailable_reason(
                card,
                schedule_start_at=schedule.start_at,
                course_id=schedule.course_id,
                course_type_code=schedule.course_type_code,
            )
            if reason is None:
                available.append(card)
            else:
                reasons.append(reason)

        available.sort(key=self._recommend_sort_key)

        return {
            "schedule_id": schedule_id,
            "recommended_card_id": available[0]["id"] if available else None,
            "available_cards": [
                MembershipCardResponse.model_validate(card) for card in available
            ],
            "message": self._recommend_message(len(cards), len(available), reasons),
        }

    async def get_student_active_cards(
        self,
        db: AsyncSession,
        student_id: int,
        tenant_id: int,
    ) -> list[dict]:
        """获取学员的有效会员卡"""
        return await self.card_repo.get_active_cards_by_student(db, student_id, tenant_id)

    async def get_user_balance(
        self,
        db: AsyncSession,
        student_id: int,
        tenant_id: int,
    ) -> dict:
        """
        获取学员的课时余额（聚合所有有效会员卡）

        Returns:
            dict: {"total": int, "used": int, "remaining": int}
        """
        result = await db.execute(
            select(
                func.coalesce(func.sum(MembershipCard.total_credits), 0).label("total"),
                func.coalesce(func.sum(MembershipCard.used_credits), 0).label("used"),
            ).where(
                MembershipCard.student_id == student_id,
                MembershipCard.status == CardStatus.ACTIVE.value,
            )
        )
        row = result.one()
        total = int(row.total)
        used = int(row.used)
        return {"total": total, "used": used, "remaining": max(total - used, 0)}

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
            db,
            card_id=card_id,
            operation_type=operation_type,
            page=page,
            page_size=page_size,
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
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.status == CardStatus.FROZEN.value:
            raise HTTPException(status_code=400, detail="会员卡已处于冻结状态")
        if card.status == CardStatus.EXPIRED.value:
            raise HTTPException(status_code=400, detail="会员卡已过期，无法冻结")
        if card.status == CardStatus.CANCELLED.value:
            raise HTTPException(status_code=400, detail="会员卡已作废，无法冻结")
        # F6.3 T6.3.6：未激活（PENDING）卡没有有效期，禁止冻结，
        # 避免冻结顺延逻辑把 expire_at 写成 NULL + 天数错乱。
        if card.status == CardStatus.PENDING.value:
            raise HTTPException(status_code=400, detail="未激活卡不可冻结")

        now = datetime.now(UTC)

        # 如果卡已过期（expire_at < now），不允许冻结
        if card.expire_at and card.expire_at < now:
            raise HTTPException(
                status_code=400,
                detail=f"会员卡已于 {card.expire_at.strftime('%Y-%m-%d %H:%M')} 过期，无法冻结",
            )

        # 计算并保存冻结时的剩余天数（用于解冻时重新计算有效期）
        if card.expire_at:
            remaining_seconds = (card.expire_at - now).total_seconds()
            card.frozen_remaining_days = max(0, int(remaining_seconds / 86400))
        else:
            # 无限卡没有有效期，设置为None
            card.frozen_remaining_days = None

        card.status = CardStatus.FROZEN.value
        card.frozen_reason = reason
        card.frozen_at = now

        # 设置冻结到期时间（日期为 freeze_days 天后，时间为 23:59:59），并顺延卡的有效期
        frozen_until_date = (now + timedelta(days=freeze_days)).replace(
            hour=23, minute=59, second=59, microsecond=0
        )
        card.frozen_until = frozen_until_date
        card.expire_at = card.expire_at + timedelta(days=freeze_days) if card.expire_at else None

        freeze = MembershipCardFreeze(
            tenant_id=tenant_id,
            card_id=card.id,
            reason=reason,
            operator_id=operator_id,
            frozen_at=now,
            unfrozen_at=frozen_until_date if auto_unfreeze else None,
        )
        db.add(freeze)
        await db.flush()
        return card

    async def expire_card(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
    ) -> MembershipCard:
        """将单张到期的会员卡标记为 EXPIRED（F6.3 T6.3.6）

        - 逐卡 ``FOR UPDATE`` + 状态重检，重复执行 no-op（幂等）。
        - 扫描对象为 ACTIVE / PENDING（兼容历史带 expire_at 的 PENDING 卡）。
        - 次卡剩余次数清零逻辑保持原样；期卡只写 ``change_amount=0`` 的 EXPIRE。
        - 不 commit，由 Scheduler 逐租户统一提交。
        """
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        now = datetime.now(UTC)

        if card.expire_at is None or card.expire_at >= now:
            return card
        if card.status not in (CardStatus.ACTIVE.value, CardStatus.PENDING.value):
            return card

        remaining = (card.total_credits or 0) - card.used_credits

        if card.card_type == CardType.COUNT.value and remaining > 0:
            clear_txn = MembershipCardTransaction(
                tenant_id=card.tenant_id,
                card_id=card.id,
                operation_type=TransactionType.EXPIRE.value,
                change_amount=-remaining,
                balance_after=0,
                remark=f"会员卡到期，剩余{remaining}次自动清零",
            )
            db.add(clear_txn)
            card.used_credits = card.total_credits

        card.status = CardStatus.EXPIRED.value

        if remaining == 0:
            db.add(
                MembershipCardTransaction(
                    tenant_id=card.tenant_id,
                    card_id=card.id,
                    operation_type=TransactionType.EXPIRE.value,
                    change_amount=0,
                    balance_after=0,
                    remark="会员卡自动过期",
                )
            )

        await db.flush()
        return card

    async def cancel_pending_card(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        *,
        days: int,
    ) -> MembershipCard:
        """作废超期未激活的 PENDING 期卡（F6.3 T6.3.6）

        - 计时起点 = ``created_at``（已确认决策）。
        - 逐卡 ``FOR UPDATE`` + 状态重检；非 period / 非 PENDING / 未超期 → no-op。
        - 是否已被使用（COMPLETED/NO_SHOW）由调用方（Scheduler 经 BookingService）决定。
        - 不 commit，由 Scheduler 逐租户统一提交。
        """
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        now = datetime.now(UTC)

        if card.card_type != CardType.PERIOD.value:
            return card
        if card.status != CardStatus.PENDING.value:
            return card

        cutoff = now - timedelta(days=days)
        created_at = card.created_at
        if created_at is None or created_at >= cutoff:
            return card

        card.status = CardStatus.CANCELLED.value
        card.cancelled_at = now
        card.cancelled_reason = f"超期未激活（{days}天）"

        db.add(
            MembershipCardTransaction(
                tenant_id=card.tenant_id,
                card_id=card.id,
                operation_type=TransactionType.EXPIRE.value,
                change_amount=0,
                balance_after=0,
                remark="PENDING期卡超期未激活，自动作废",
            )
        )
        await db.flush()
        return card

    async def check_card_conflict(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
    ) -> dict:
        """检查会员卡是否存在同课程类型的时间冲突

        Returns:
            dict: {
                "has_conflict": bool,
                "conflict_cards": list[dict],
                "conflict_count": int
            }
        """
        card = await self.get_card(db, card_id, tenant_id)

        all_existing_cards = await self.card_repo.get_active_cards_by_student(
            db, card.student_id, tenant_id
        )

        conflicting_cards = []
        card_course_type = card.applicable_course_type_code

        if card_course_type:
            for existing_card in all_existing_cards:
                if existing_card.id == card.id:
                    continue

                existing_course_type = existing_card.applicable_course_type_code
                if existing_course_type == card_course_type:
                    existing_valid_from = existing_card.valid_from
                    existing_expire_at = existing_card.expire_at

                    if existing_valid_from and existing_expire_at and card.valid_from and card.expire_at:
                        if card.valid_from <= existing_expire_at and existing_valid_from <= card.expire_at:
                            conflicting_cards.append(existing_card)

        return {
            "has_conflict": len(conflicting_cards) > 0,
            "conflict_cards": conflicting_cards,
            "conflict_count": len(conflicting_cards),
        }

    async def unfreeze_card(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        operator_id: int,
    ) -> MembershipCard:
        """解冻会员卡（提前解冻）"""
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.status != CardStatus.FROZEN.value:
            raise HTTPException(status_code=400, detail="会员卡未处于冻结状态")

        now = datetime.now(UTC)

        conflict_check = await self.check_card_conflict(db, card_id, tenant_id)
        if conflict_check["has_conflict"]:
            card_count = len(conflict_check["conflict_cards"])
            conflict_type = card.applicable_course_type_code
            raise HTTPException(
                status_code=409,
                detail=f"解冻后将与 {card_count} 张同课程类型的有效卡（{conflict_type}）产生时间冲突。请先将冲突卡作废或冻结后再解冻。",
            )

        # 根据冻结时保存的剩余天数重新计算有效期
        if card.frozen_remaining_days is not None and card.frozen_remaining_days > 0:
            card.expire_at = now + timedelta(days=card.frozen_remaining_days)

        card.status = CardStatus.ACTIVE.value
        card.frozen_reason = None
        card.frozen_at = None
        card.frozen_until = None
        card.frozen_remaining_days = None

        freezes, _ = await self.freeze_repo.list_freezes(db, card_id=card_id, page=1, page_size=1)
        if freezes and freezes[0].unfrozen_at is None:
            freezes[0].unfrozen_at = now

        await db.flush()
        return card

    async def student_unfreeze_card(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        student_id: int,
    ) -> MembershipCard:
        """学员提前解冻会员卡"""
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.student_id != student_id:
            raise HTTPException(status_code=403, detail="无权操作此会员卡")
        if card.status != CardStatus.FROZEN.value:
            raise HTTPException(status_code=400, detail="会员卡未处于冻结状态")

        if card.frozen_until is None:
            raise HTTPException(status_code=400, detail="无限期冻结，请联系管理员处理")

        now = datetime.now(UTC)

        conflict_check = await self.check_card_conflict(db, card_id, tenant_id)
        if conflict_check["has_conflict"]:
            card_count = len(conflict_check["conflict_cards"])
            conflict_type = card.applicable_course_type_code
            raise HTTPException(
                status_code=409,
                detail=f"解冻后将与 {card_count} 张同课程类型的有效卡（{conflict_type}）产生时间冲突。请先将冲突卡作废或冻结后再解冻。",
            )

        # 根据冻结时保存的剩余天数重新计算有效期
        if card.frozen_remaining_days is not None and card.frozen_remaining_days > 0:
            card.expire_at = now + timedelta(days=card.frozen_remaining_days)

        card.status = CardStatus.ACTIVE.value
        card.frozen_reason = None
        card.frozen_at = None
        card.frozen_until = None
        card.frozen_remaining_days = None

        freezes, _ = await self.freeze_repo.list_freezes(db, card_id=card_id, page=1, page_size=1)
        if freezes and freezes[0].unfrozen_at is None:
            freezes[0].unfrozen_at = now

        await db.flush()
        return card

    async def admin_force_unfreeze_card(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        operator_id: int,
        force: bool = False,
        remark: str = "",
    ) -> MembershipCard:
        """管理员强制解冻会员卡（允许冲突）

        Args:
            force: 是否强制解冻（忽略冲突检查）
            remark: 操作备注
        """
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.status != CardStatus.FROZEN.value:
            raise HTTPException(status_code=400, detail="会员卡未处于冻结状态")

        now = datetime.now(UTC)

        if not force:
            conflict_check = await self.check_card_conflict(db, card_id, tenant_id)
            if conflict_check["has_conflict"]:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": f"解冻后将与 {conflict_check['conflict_count']} 张同课程类型的有效卡产生时间冲突",
                        "conflict_cards": conflict_check["conflict_cards"],
                        "suggestion": "请使用 force=true 参数强制解冻，或先处理冲突卡",
                    },
                )

        # 根据冻结时保存的剩余天数重新计算有效期
        if card.frozen_remaining_days is not None and card.frozen_remaining_days > 0:
            card.expire_at = now + timedelta(days=card.frozen_remaining_days)

        card.status = CardStatus.ACTIVE.value
        card.frozen_reason = None
        card.frozen_at = None
        card.frozen_until = None
        card.frozen_remaining_days = None

        freezes, _ = await self.freeze_repo.list_freezes(db, card_id=card_id, page=1, page_size=1)
        if freezes and freezes[0].unfrozen_at is None:
            freezes[0].unfrozen_at = now

        remark = remark or ("管理员强制解冻（允许冲突）" if force else "管理员提前解冻")
        txn = MembershipCardTransaction(
            tenant_id=tenant_id,
            card_id=card.id,
            operation_type=TransactionType.ADJUST.value,
            change_amount=0,
            balance_after=(card.total_credits or 0) - card.used_credits,
            operator_id=operator_id,
            remark=remark,
        )
        db.add(txn)

        await db.flush()
        return card

    async def unfreeze_and_cancel_conflicts(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        operator_id: int,
        conflict_card_ids: list[int],
        cancel_reason: str = "解冻冲突卡自动作废",
    ) -> dict:
        """解冻并作废冲突卡

        Args:
            card_id: 要解冻的卡ID
            conflict_card_ids: 要作废的冲突卡ID列表
            cancel_reason: 作废原因

        Returns:
            dict: {
                "unfrozen_card": 解冻的卡,
                "cancelled_cards": 作废的卡列表,
                "success_count": 成功作废数量,
                "failed_cards": 失败的卡ID和原因
            }
        """
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.status != CardStatus.FROZEN.value:
            raise HTTPException(status_code=400, detail="会员卡未处于冻结状态")

        cancelled_cards = []
        failed_cards = []

        # F4.3: 对 conflict_card_ids 排序后再加锁，消除并发死锁风险
        # （见 .trae/rules/database/transaction.md §锁顺序：多表/多行加锁按固定顺序防死锁）
        conflict_card_ids = sorted(conflict_card_ids)
        for conflict_id in conflict_card_ids:
            try:
                conflict_card = await self.get_card_with_lock(db, conflict_id, tenant_id)

                if conflict_card.student_id != card.student_id:
                    failed_cards.append({
                        "card_id": conflict_id,
                        "error": "不是同一学员的卡"
                    })
                    continue

                if conflict_card.status not in [CardStatus.ACTIVE.value, CardStatus.PENDING.value]:
                    failed_cards.append({
                        "card_id": conflict_id,
                        "error": f"卡状态为{conflict_card.status}，无法作废"
                    })
                    continue

                now = datetime.now(UTC)
                remaining = (conflict_card.total_credits or 0) - conflict_card.used_credits

                if remaining > 0:
                    txn = MembershipCardTransaction(
                        tenant_id=tenant_id,
                        card_id=conflict_card.id,
                        operation_type=TransactionType.EXPIRE.value,
                        change_amount=-remaining,
                        balance_after=0,
                        operator_id=operator_id,
                        remark=f"解冻卡{card_id}时自动作废，剩余{remaining}次清零",
                    )
                    db.add(txn)
                    conflict_card.used_credits = conflict_card.total_credits

                conflict_card.status = CardStatus.CANCELLED.value
                conflict_card.cancelled_at = now
                conflict_card.cancelled_reason = cancel_reason

                cancelled_cards.append(conflict_card)

            except HTTPException as e:
                failed_cards.append({
                    "card_id": conflict_id,
                    "error": e.detail
                })
            except Exception as e:
                failed_cards.append({
                    "card_id": conflict_id,
                    "error": str(e)
                })

        if failed_cards:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "部分冲突卡作废失败",
                    "failed_cards": failed_cards,
                },
            )

        now = datetime.now(UTC)

        # 根据冻结时保存的剩余天数重新计算有效期
        if card.frozen_remaining_days is not None and card.frozen_remaining_days > 0:
            card.expire_at = now + timedelta(days=card.frozen_remaining_days)

        card.status = CardStatus.ACTIVE.value
        card.frozen_reason = None
        card.frozen_at = None
        card.frozen_until = None
        card.frozen_remaining_days = None

        freezes, _ = await self.freeze_repo.list_freezes(db, card_id=card_id, page=1, page_size=1)
        if freezes and freezes[0].unfrozen_at is None:
            freezes[0].unfrozen_at = now

        txn = MembershipCardTransaction(
            tenant_id=tenant_id,
            card_id=card.id,
            operation_type=TransactionType.ADJUST.value,
            change_amount=0,
            balance_after=(card.total_credits or 0) - card.used_credits,
            operator_id=operator_id,
            remark=f"解冻并作废{len(cancelled_cards)}张冲突卡",
        )
        db.add(txn)

        await db.flush()

        return {
            "unfrozen_card": card,
            "cancelled_cards": cancelled_cards,
            "success_count": len(cancelled_cards),
            "failed_cards": failed_cards,
        }

    async def unfreeze_and_freeze_conflicts(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        operator_id: int,
        conflict_card_ids: list[int],
        freeze_reason: str = "解冻冲突卡自动冻结",
        freeze_days: int = 365,
    ) -> dict:
        """解冻并冻结冲突卡

        Args:
            card_id: 要解冻的卡ID
            conflict_card_ids: 要冻结的冲突卡ID列表
            freeze_reason: 冻结原因
            freeze_days: 冻结天数

        Returns:
            dict: {
                "unfrozen_card": 解冻的卡,
                "frozen_cards": 冻结的卡列表,
                "success_count": 成功冻结数量,
                "failed_cards": 失败的卡ID和原因
            }
        """
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.status != CardStatus.FROZEN.value:
            raise HTTPException(status_code=400, detail="会员卡未处于冻结状态")

        frozen_cards = []
        failed_cards = []
        now = datetime.now(UTC)

        # F4.3: 对 conflict_card_ids 排序后再加锁，消除并发死锁风险
        # （见 .trae/rules/database/transaction.md §锁顺序：多表/多行加锁按固定顺序防死锁）
        conflict_card_ids = sorted(conflict_card_ids)
        for conflict_id in conflict_card_ids:
            try:
                conflict_card = await self.get_card_with_lock(db, conflict_id, tenant_id)

                if conflict_card.student_id != card.student_id:
                    failed_cards.append({
                        "card_id": conflict_id,
                        "error": "不是同一学员的卡"
                    })
                    continue

                if conflict_card.status != CardStatus.ACTIVE.value:
                    failed_cards.append({
                        "card_id": conflict_id,
                        "error": f"卡状态为{conflict_card.status}，无法冻结"
                    })
                    continue

                # 保存冻结时的剩余天数
                if conflict_card.expire_at:
                    remaining_seconds = (conflict_card.expire_at - now).total_seconds()
                    conflict_card.frozen_remaining_days = max(0, int(remaining_seconds / 86400))
                else:
                    conflict_card.frozen_remaining_days = None

                conflict_card.status = CardStatus.FROZEN.value
                conflict_card.frozen_reason = freeze_reason
                conflict_card.frozen_at = now
                frozen_until = (now + timedelta(days=freeze_days)).replace(
                    hour=23, minute=59, second=59, microsecond=0
                )
                conflict_card.frozen_until = frozen_until
                conflict_card.expire_at = conflict_card.expire_at + timedelta(days=freeze_days) if conflict_card.expire_at else None

                freeze = MembershipCardFreeze(
                    tenant_id=tenant_id,
                    card_id=conflict_card.id,
                    reason=freeze_reason,
                    operator_id=operator_id,
                    frozen_at=now,
                )
                db.add(freeze)

                frozen_cards.append(conflict_card)

            except HTTPException as e:
                failed_cards.append({
                    "card_id": conflict_id,
                    "error": e.detail
                })
            except Exception as e:
                failed_cards.append({
                    "card_id": conflict_id,
                    "error": str(e)
                })

        if failed_cards:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "部分冲突卡冻结失败",
                    "failed_cards": failed_cards,
                },
            )

        now = datetime.now(UTC)

        # 根据冻结时保存的剩余天数重新计算有效期
        if card.frozen_remaining_days is not None and card.frozen_remaining_days > 0:
            card.expire_at = now + timedelta(days=card.frozen_remaining_days)

        card.status = CardStatus.ACTIVE.value
        card.frozen_reason = None
        card.frozen_at = None
        card.frozen_until = None
        card.frozen_remaining_days = None

        freezes, _ = await self.freeze_repo.list_freezes(db, card_id=card_id, page=1, page_size=1)
        if freezes and freezes[0].unfrozen_at is None:
            freezes[0].unfrozen_at = now

        txn = MembershipCardTransaction(
            tenant_id=tenant_id,
            card_id=card.id,
            operation_type=TransactionType.ADJUST.value,
            change_amount=0,
            balance_after=(card.total_credits or 0) - card.used_credits,
            operator_id=operator_id,
            remark=f"解冻并冻结{len(frozen_cards)}张冲突卡",
        )
        db.add(txn)

        await db.flush()

        return {
            "unfrozen_card": card,
            "frozen_cards": frozen_cards,
            "success_count": len(frozen_cards),
            "failed_cards": failed_cards,
        }

    async def activate_card(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        student_id: int,
    ) -> MembershipCard:
        """学员主动激活会员卡（仅学员本人可操作）

        支持场景：
        - 激活待激活的卡（PENDING → ACTIVE）
        - 提前激活冻结的卡（FROZEN → ACTIVE）- 需要验证冻结到期时间
        """
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.student_id != student_id:
            raise HTTPException(status_code=403, detail="无权操作此会员卡")
        if card.status not in [CardStatus.PENDING.value, CardStatus.FROZEN.value]:
            raise HTTPException(status_code=400, detail="会员卡状态不允许激活")

        # 如果是冻结状态，验证是否允许提前激活
        if card.status == CardStatus.FROZEN.value:
            # 检查是否有冻结到期时间
            if card.frozen_until is None:
                raise HTTPException(status_code=400, detail="无限期冻结，请联系管理员处理")

            now = datetime.now(UTC)
            # 如果冻结还未到期，不允许学员提前激活（需要管理员操作）
            if card.frozen_until > now:
                raise HTTPException(
                    status_code=400,
                    detail=f"会员卡冻结中，到期时间：{card.frozen_until.strftime('%Y-%m-%d %H:%M')}，请联系管理员提前解冻",
                )

            # 冻结已到期，清除冻结信息
            card.frozen_reason = None
            card.frozen_at = None
            card.frozen_until = None

        # 先计算生效时间和到期时间（用于冲突检查）
        now = datetime.now(UTC)
        valid_from = datetime(
            year=now.year, month=now.month, day=now.day, hour=0, minute=0, second=0, tzinfo=UTC
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

        # 检查学员是否已有同课程类型且时间重叠的有效卡（防止同一时段多张卡重叠）
        # 注意：这里检查所有有效卡，不只是同产品的卡
        all_existing_cards = await self.card_repo.get_active_cards_by_student(
            db, card.student_id, tenant_id
        )

        # 过滤出课程类型相同且时间重叠的卡
        conflicting_cards = []
        new_card_course_type = card.applicable_course_type_code

        if new_card_course_type:
            for existing_card in all_existing_cards:
                existing_course_type = existing_card.applicable_course_type_code
                # 如果课程类型相同
                if existing_course_type == new_card_course_type:
                    # 检查时间是否重叠
                    existing_valid_from = existing_card.valid_from
                    existing_expire_at = existing_card.expire_at

                    if existing_valid_from and existing_expire_at:
                        # 检查时间重叠：新卡的valid_from <= 旧卡的expire_at AND 旧卡的valid_from <= 新卡的expire_at
                        if valid_from <= existing_expire_at and existing_valid_from <= expire_at:
                            conflicting_cards.append(existing_card)

        if conflicting_cards:
            card_count = len(conflicting_cards)
            raise HTTPException(
                status_code=409,
                detail=f"该学员已有 {card_count} 张同课程类型的有效卡（{new_card_course_type}）。请先将旧卡作废或冻结后再激活新卡。",
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
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
        operator_id: int,
    ) -> MembershipCard:
        """管理员手动激活会员卡"""
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.status != CardStatus.PENDING.value:
            raise HTTPException(status_code=400, detail="会员卡已激活或已过期，无法重复激活")

        now = datetime.now(UTC)

        # 先计算生效时间和到期时间（用于冲突检查）
        valid_from = datetime(
            year=now.year, month=now.month, day=now.day, hour=0, minute=0, second=0, tzinfo=UTC
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

        # 检查学员是否已有同课程类型且时间重叠的有效卡（防止同一时段多张卡重叠）
        # 注意：这里检查所有有效卡，不只是同产品的卡
        all_existing_cards = await self.card_repo.get_active_cards_by_student(
            db, card.student_id, tenant_id
        )

        # 过滤出课程类型相同且时间重叠的卡
        conflicting_cards = []
        new_card_course_type = card.applicable_course_type_code

        if new_card_course_type:
            for existing_card in all_existing_cards:
                existing_course_type = existing_card.applicable_course_type_code
                # 如果课程类型相同
                if existing_course_type == new_card_course_type:
                    # 检查时间是否重叠
                    existing_valid_from = existing_card.valid_from
                    existing_expire_at = existing_card.expire_at

                    if existing_valid_from and existing_expire_at:
                        # 检查时间重叠：新卡的valid_from <= 旧卡的expire_at AND 旧卡的valid_from <= 新卡的expire_at
                        if valid_from <= existing_expire_at and existing_valid_from <= expire_at:
                            conflicting_cards.append(existing_card)

        if conflicting_cards:
            card_count = len(conflicting_cards)
            raise HTTPException(
                status_code=409,
                detail=f"该学员已有 {card_count} 张同课程类型的有效卡（{new_card_course_type}）。请先将旧卡作废或冻结后再激活新卡。",
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
        check_at: datetime | None = None,
    ) -> MembershipCard:
        """扣减次数（约课时调用）

        使用悲观锁防止并发扣次导致次数为负。

        Args:
            check_at: 有效期判断基准时间；预约场景传排期开始时间，
                避免“卡到期后仍能预约未来课程”。不传则使用当前时间。
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

        # 期卡有效期验证（预约场景以排期时间为基准）
        check_time = check_at or datetime.now(UTC)
        if check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=UTC)
        if card.valid_from and check_time < card.valid_from:
            raise HTTPException(
                status_code=400,
                detail=f"会员卡尚未生效，生效时间：{card.valid_from.strftime('%Y-%m-%d')}",
            )
        if card.expire_at and check_time > card.expire_at:
            raise HTTPException(
                status_code=400,
                detail=f"会员卡已过期，到期时间：{card.expire_at.strftime('%Y-%m-%d')}",
            )

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
                    detail=f"会员卡数据异常（已使用次数为负：{card.used_credits}），请联系管理员",
                )

            card.used_credits += 1
            balance_after = card.total_credits - card.used_credits

            # 最终安全检查：确保余额不为负
            if balance_after < 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"会员卡扣次异常（余额计算为负：{balance_after}），请联系管理员检查数据",
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
        # F6.3 T6.3.5：期卡/无限卡不预扣次数，取消时直接 no-op；
        # 次卡仍按原逻辑回补。必须在 used_credits<=0 校验之前返回，
        # 否则期卡取消会因为剩余次数为 0 而 400，拖垮整个取消事务。
        if card.card_type != CardType.COUNT.value:
            return card
        if card.used_credits <= 0:
            raise HTTPException(status_code=400, detail="会员卡已使用次数为0，无法恢复")

        card.used_credits -= 1
        # 期卡/无限卡：total_credits 为 None，余额记为 0
        balance_after = (
            (card.total_credits - card.used_credits) if card.total_credits is not None else 0
        )

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
        """计算到期时间，时分秒统一设置为23:59:59

        注意：起始日期算作第1天，所以实际加的天数是 days-1
        例如：valid_from=2026-09-19, validity_days=3
        - 第1天：2026-09-19
        - 第2天：2026-09-20
        - 第3天：2026-09-21
        - expire_at = 2026-09-21 23:59:59
        """
        expire_date = start_at.date() + timedelta(days=days - 1)
        return datetime(
            year=expire_date.year,
            month=expire_date.month,
            day=expire_date.day,
            hour=23,
            minute=59,
            second=59,
            tzinfo=start_at.tzinfo or UTC,
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
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
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
        card = await self.get_card_with_lock(db, card_id, tenant_id)
        if not card:
            raise HTTPException(status_code=404, detail="会员卡不存在")
        if card.status == CardStatus.CANCELLED.value:
            raise HTTPException(status_code=400, detail="会员卡已处于作废状态")

        now = datetime.now(UTC)
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

    async def batch_cancel_cards(
        self,
        db: AsyncSession,
        card_ids: list[int],
        tenant_id: int,
        reason: str,
        operator_id: int,
    ) -> dict:
        """批量作废会员卡（管理员操作）

        Returns:
            dict: {
                "success_count": 成功作废的数量,
                "failed_count": 失败的数量,
                "failed_cards": 失败的卡ID和原因列表
            }
        """
        success_count = 0
        failed_count = 0
        failed_cards = []

        # F4.3: 对 card_ids 排序后再加锁（cancel_card 内 get_card_with_lock FOR UPDATE），
        # 消除并发死锁风险（同模式扩展修复）
        # （见 .trae/rules/database/transaction.md §锁顺序：多表/多行加锁按固定顺序防死锁）
        card_ids = sorted(card_ids)
        for card_id in card_ids:
            try:
                # 复用单个作废逻辑
                await self.cancel_card(db, card_id, tenant_id, reason, operator_id)
                success_count += 1
            except HTTPException as e:
                failed_count += 1
                failed_cards.append({"card_id": card_id, "error": e.detail})
            except Exception as e:
                failed_count += 1
                failed_cards.append({"card_id": card_id, "error": str(e)})

        return {
            "success_count": success_count,
            "failed_count": failed_count,
            "failed_cards": failed_cards,
            "total": len(card_ids),
        }


membership_card_service = MembershipCardService()
