"""
Payment Service - 支付业务逻辑层

包含：
- 支付回调处理
- 支付成功后激活会员卡
"""

import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.membership.service import membership_card_service
from app.modules.order.models import Order, OrderStatus
from app.modules.payment.models import Payment, PaymentChannel, PaymentStatus

logger = logging.getLogger(__name__)


class PaymentService:
    """支付业务逻辑"""

    async def handle_payment_callback(
        self,
        db: AsyncSession,
        out_trade_no: str,
        transaction_id: str,
        channel: str,
        raw_response: dict | None = None,
    ) -> Payment:
        """处理支付回调"""
        payment = await self._get_payment_by_trade_no(db, out_trade_no)
        if not payment:
            raise HTTPException(status_code=404, detail="支付记录不存在")

        if payment.status == PaymentStatus.PAID.value:
            logger.info(f"支付记录已处理: {out_trade_no}")
            return payment

        payment.status = PaymentStatus.PAID.value
        payment.transaction_id = transaction_id
        payment.paid_at = datetime.now(timezone.utc)
        payment.raw_response = raw_response

        await db.flush()

        order = await self._get_order_by_id(db, payment.order_id)
        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")

        if order.status == OrderStatus.PAID.value:
            logger.info(f"订单已处理: {order.order_no}")
            return payment

        order.status = OrderStatus.PAID.value
        order.paid_at = payment.paid_at

        await db.flush()

        if order.item_type == "card" and order.membership_card_id:
            logger.info(f"支付成功，会员卡已关联: order={order.order_no}, card_id={order.membership_card_id}")

        return payment

    async def _get_payment_by_trade_no(self, db: AsyncSession, out_trade_no: str) -> Payment | None:
        from sqlalchemy import select
        query = select(Payment).where(Payment.out_trade_no == out_trade_no)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def _get_order_by_id(self, db: AsyncSession, order_id: int) -> Order | None:
        from sqlalchemy import select
        query = select(Order).where(Order.id == order_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()


payment_service = PaymentService()