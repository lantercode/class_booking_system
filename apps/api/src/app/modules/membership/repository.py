"""
Membership Card Repository - 会员卡数据访问层

提供会员卡相关的数据库操作，继承 TenantAwareRepository 实现自动多租户隔离。
"""

from datetime import datetime

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.membership.models import (
    MembershipCard,
    MembershipCardFreeze,
    MembershipCardProduct,
    MembershipCardTransaction,
    CardStatus,
)


class MembershipCardProductRepository(TenantAwareRepository[MembershipCardProduct]):
    """会员卡产品数据访问层"""

    model_class = MembershipCardProduct

    async def list_products(
        self,
        db: AsyncSession,
        *,
        status: int | None = None,
        card_type: str | None = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MembershipCardProduct], int]:
        """获取产品列表（默认显示上架和下架的产品，过滤已删除的）"""
        base_query = select(MembershipCardProduct)
        count_query = select(func.count()).select_from(MembershipCardProduct)

        # 默认过滤已删除的数据
        if not include_deleted:
            base_query = base_query.where(MembershipCardProduct.deleted_at.is_(None))
            count_query = count_query.where(MembershipCardProduct.deleted_at.is_(None))

        if status is not None:
            base_query = base_query.where(MembershipCardProduct.status == status)
            count_query = count_query.where(MembershipCardProduct.status == status)

        if card_type is not None:
            base_query = base_query.where(MembershipCardProduct.card_type == card_type)
            count_query = count_query.where(MembershipCardProduct.card_type == card_type)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            base_query = base_query.where(MembershipCardProduct.tenant_id == tenant_id)
            count_query = count_query.where(MembershipCardProduct.tenant_id == tenant_id)

        base_query = base_query.order_by(MembershipCardProduct.sort_order.asc())

        offset_val = (page - 1) * page_size
        base_query = base_query.offset(offset_val).limit(page_size)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        result = await db.execute(base_query)
        items = list(result.scalars().all())

        return items, total

    async def list_deleted_products(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MembershipCardProduct], int]:
        """获取回收站中的产品列表（已删除）"""
        base_query = select(MembershipCardProduct).where(
            MembershipCardProduct.deleted_at.isnot(None)
        )
        count_query = select(func.count()).select_from(MembershipCardProduct).where(
            MembershipCardProduct.deleted_at.isnot(None)
        )

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            base_query = base_query.where(MembershipCardProduct.tenant_id == tenant_id)
            count_query = count_query.where(MembershipCardProduct.tenant_id == tenant_id)

        base_query = base_query.order_by(MembershipCardProduct.deleted_at.desc())

        offset_val = (page - 1) * page_size
        base_query = base_query.offset(offset_val).limit(page_size)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        result = await db.execute(base_query)
        items = list(result.scalars().all())

        return items, total

    async def restore_product(
        self,
        db: AsyncSession,
        product_id: int,
    ) -> MembershipCardProduct | None:
        """恢复已删除的产品"""
        result = await db.execute(
            select(MembershipCardProduct).where(
                MembershipCardProduct.id == product_id,
                MembershipCardProduct.deleted_at.isnot(None),
            )
        )
        product = result.scalar_one_or_none()
        if product:
            product.deleted_at = None
            product.status = ProductStatus.OFFLINE.value  # 恢复后默认为下架状态
            await db.flush()
        return product


class MembershipCardRepository(TenantAwareRepository[MembershipCard]):
    """会员卡数据访问层"""

    model_class = MembershipCard

    async def get_active_cards_by_student(
        self,
        db: AsyncSession,
        student_id: int,
        tenant_id: int,
    ) -> list[dict]:
        """获取学员的有效会员卡（返回包含关联信息的字典）"""
        from app.modules.user.models import User
        from app.modules.membership.models import MembershipCardProduct

        query = select(
            MembershipCard,
            User.nickname.label("student_nickname"),
            User.phone.label("student_phone"),
            MembershipCardProduct.name.label("product_name"),
        ).outerjoin(User, MembershipCard.student_id == User.id).outerjoin(
            MembershipCardProduct, MembershipCard.product_id == MembershipCardProduct.id
        ).where(
            MembershipCard.student_id == student_id,
            MembershipCard.tenant_id == tenant_id,
            MembershipCard.status.in_([
                CardStatus.ACTIVE.value,      # 正常
                CardStatus.PENDING.value,     # 待激活
            ]),
        ).order_by(MembershipCard.expire_at.asc())

        result = await db.execute(query)
        rows = result.all()
        
        # 转换为字典格式
        cards = []
        for row in rows:
            card = row[0]
            card_dict = {
                "id": card.id,
                "public_id": card.public_id,
                "student_id": card.student_id,
                "product_id": card.product_id,
                "card_type": card.card_type,
                "total_credits": card.total_credits,
                "used_credits": card.used_credits,
                "remaining_credits": (card.total_credits or 0) - card.used_credits if card.total_credits is not None else None,
                "valid_from": card.valid_from,
                "expire_at": card.expire_at,
                "applicable_course_ids": card.applicable_course_ids,
                "applicable_course_type_codes": card.applicable_course_type_codes,
                "max_weekly_usage": card.max_weekly_usage,
                "status": card.status,
                "frozen_at": card.frozen_at,
                "frozen_until": card.frozen_until,
                "frozen_reason": card.frozen_reason,
                "cancelled_at": card.cancelled_at,
                "cancelled_reason": card.cancelled_reason,
                "created_at": card.created_at,
                "updated_at": card.updated_at,
                "student_nickname": row.student_nickname,
                "student_phone": row.student_phone,
                "product_name": row.product_name,
            }
            cards.append(card_dict)
        
        return cards

    async def get_active_cards_by_product(
        self,
        db: AsyncSession,
        student_id: int,
        product_id: int,
        tenant_id: int,
        exclude_pending: bool = False,
    ) -> list[MembershipCard]:
        """检查学员是否已有同产品的有效卡
        
        Args:
            exclude_pending: 是否排除 PENDING 状态的卡
                - False（默认）：用于发卡时检查，包含 PENDING
                - True：用于激活时检查，排除 PENDING（因为 PENDING 卡还没生效）
        
        有效状态包括：ACTIVE、FROZEN、PENDING（待激活但已发放）
        无效状态包括：EXPIRED、DEPLETED、CANCELLED、REFUNDED
        """
        from sqlalchemy import select
        
        valid_statuses = [
            CardStatus.ACTIVE.value,      # 正常
            CardStatus.FROZEN.value,      # 冻结中
        ]
        if not exclude_pending:
            valid_statuses.append(CardStatus.PENDING.value)  # 待激活
        
        query = select(MembershipCard).where(
            MembershipCard.student_id == student_id,
            MembershipCard.product_id == product_id,
            MembershipCard.tenant_id == tenant_id,
            MembershipCard.status.in_(valid_statuses),
        )
        
        result = await db.execute(query)
        return list(result.scalars().all())

    async def list_cards(
        self,
        db: AsyncSession,
        *,
        student_id: int | None = None,
        product_id: int | None = None,
        card_type: str | None = None,
        status: int | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """获取会员卡列表（包含学员和产品关联信息）"""
        from app.modules.user.models import User
        from app.modules.membership.models import MembershipCardProduct

        # 构建带 JOIN 的查询
        base_query = select(
            MembershipCard,
            User.nickname.label("student_nickname"),
            User.phone.label("student_phone"),
            MembershipCardProduct.name.label("product_name"),
        ).outerjoin(User, MembershipCard.student_id == User.id).outerjoin(
            MembershipCardProduct, MembershipCard.product_id == MembershipCardProduct.id
        )

        count_query = select(func.count()).select_from(MembershipCard)

        if student_id is not None:
            base_query = base_query.where(MembershipCard.student_id == student_id)
            count_query = count_query.where(MembershipCard.student_id == student_id)

        if product_id is not None:
            base_query = base_query.where(MembershipCard.product_id == product_id)
            count_query = count_query.where(MembershipCard.product_id == product_id)

        if card_type is not None:
            base_query = base_query.where(MembershipCard.card_type == card_type)
            count_query = count_query.where(MembershipCard.card_type == card_type)

        if status is not None:
            base_query = base_query.where(MembershipCard.status == status)
            count_query = count_query.where(MembershipCard.status == status)

        if keyword:
            like_pattern = f"%{keyword}%"
            base_query = base_query.where(
                or_(
                    User.nickname.like(like_pattern),
                    User.phone.like(like_pattern),
                )
            )
            count_query = count_query.where(
                MembershipCard.student_id.in_(
                    select(User.id).where(
                        or_(
                            User.nickname.like(like_pattern),
                            User.phone.like(like_pattern),
                        )
                    )
                )
            )

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            base_query = base_query.where(MembershipCard.tenant_id == tenant_id)
            count_query = count_query.where(MembershipCard.tenant_id == tenant_id)

        # 默认过滤已作废的卡
        from app.modules.membership.models import CardStatus
        base_query = base_query.where(MembershipCard.status != CardStatus.CANCELLED.value)
        count_query = count_query.where(MembershipCard.status != CardStatus.CANCELLED.value)

        base_query = base_query.order_by(MembershipCard.created_at.desc())

        offset_val = (page - 1) * page_size
        base_query = base_query.offset(offset_val).limit(page_size)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        result = await db.execute(base_query)
        rows = result.all()

        # 组装返回数据
        items = []
        for row in rows:
            card = row[0]
            total_credits = getattr(card, 'total_credits', None)
            used_credits = getattr(card, 'used_credits', 0)
            remaining_credits = None
            if total_credits is not None:
                remaining_credits = total_credits - used_credits

            item = {
                **{c.key: getattr(card, c.key) for c in card.__table__.columns},
                "remaining_credits": remaining_credits,
                "student_nickname": row[1],
                "student_phone": row[2],
                "product_name": row[3],
            }
            items.append(item)

        return items, total

    async def get_expiring_cards(
        self,
        db: AsyncSession,
        before_date: datetime,
    ) -> list[MembershipCard]:
        """获取即将过期的会员卡"""
        from app.core.tenant_context import get_tenant_id

        query = select(MembershipCard).where(
            MembershipCard.expire_at <= before_date,
            MembershipCard.status == 1,  # ACTIVE
            MembershipCard.expire_at.isnot(None),
        )

        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(MembershipCard.tenant_id == tenant_id)

        result = await db.execute(query)
        return list(result.scalars().all())


class MembershipCardTransactionRepository(TenantAwareRepository[MembershipCardTransaction]):
    """会员卡消费流水数据访问层"""

    model_class = MembershipCardTransaction

    async def get_by_idempotency_key(
        self,
        db: AsyncSession,
        idempotency_key: str,
    ) -> MembershipCardTransaction | None:
        """通过幂等键查找流水"""
        from app.core.tenant_context import get_tenant_id

        query = select(MembershipCardTransaction).where(
            MembershipCardTransaction.idempotency_key == idempotency_key,
        )

        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(MembershipCardTransaction.tenant_id == tenant_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def list_transactions(
        self,
        db: AsyncSession,
        *,
        card_id: int | None = None,
        operation_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MembershipCardTransaction], int]:
        """获取消费流水列表"""
        base_query = select(MembershipCardTransaction)
        count_query = select(func.count()).select_from(MembershipCardTransaction)

        if card_id is not None:
            base_query = base_query.where(MembershipCardTransaction.card_id == card_id)
            count_query = count_query.where(MembershipCardTransaction.card_id == card_id)

        if operation_type is not None:
            base_query = base_query.where(MembershipCardTransaction.operation_type == operation_type)
            count_query = count_query.where(MembershipCardTransaction.operation_type == operation_type)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            base_query = base_query.where(MembershipCardTransaction.tenant_id == tenant_id)
            count_query = count_query.where(MembershipCardTransaction.tenant_id == tenant_id)

        base_query = base_query.order_by(MembershipCardTransaction.created_at.desc())

        offset_val = (page - 1) * page_size
        base_query = base_query.offset(offset_val).limit(page_size)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        result = await db.execute(base_query)
        items = list(result.scalars().all())

        return items, total


class MembershipCardFreezeRepository(TenantAwareRepository[MembershipCardFreeze]):
    """会员卡冻结记录数据访问层"""

    model_class = MembershipCardFreeze

    async def list_freezes(
        self,
        db: AsyncSession,
        *,
        card_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[MembershipCardFreeze], int]:
        """获取冻结记录列表"""
        base_query = select(MembershipCardFreeze)
        count_query = select(func.count()).select_from(MembershipCardFreeze)

        if card_id is not None:
            base_query = base_query.where(MembershipCardFreeze.card_id == card_id)
            count_query = count_query.where(MembershipCardFreeze.card_id == card_id)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            base_query = base_query.where(MembershipCardFreeze.tenant_id == tenant_id)
            count_query = count_query.where(MembershipCardFreeze.tenant_id == tenant_id)

        base_query = base_query.order_by(MembershipCardFreeze.created_at.desc())

        offset_val = (page - 1) * page_size
        base_query = base_query.offset(offset_val).limit(page_size)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        result = await db.execute(base_query)
        items = list(result.scalars().all())

        return items, total