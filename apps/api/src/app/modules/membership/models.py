"""
Membership Card Models - 会员卡模型

包含：
- MembershipCardProduct: 会员卡产品（商品配置）
- MembershipCard: 用户持有的会员卡
- MembershipCardTransaction: 消费流水记录
- MembershipCardFreeze: 冻结记录
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TenantMixin, TimestampMixin


# ============================================================
# 枚举定义
# ============================================================

class CardType(Enum):
    """会员卡类型"""
    COUNT = "count"           # 次卡（按次数扣费）
    PERIOD = "period"         # 期卡（有效期内无限次）
    UNLIMITED = "unlimited"   # 无限卡（永久有效）


class CardStatus(Enum):
    """会员卡状态"""
    PENDING = 0     # 待激活
    ACTIVE = 1      # 正常可用
    EXPIRED = 2     # 已过期
    FROZEN = 3      # 已冻结
    DEPLETED = 4    # 已用完（次卡）
    REFUNDED = 5    # 已退款
    CANCELLED = 6   # 已取消


class TransactionType(Enum):
    """流水操作类型"""
    ISSUE = "issue"         # 发放/开卡
    CONSUME = "consume"     # 扣减课时（约课）
    RESTORE = "restore"     # 恢复课时（取消约课）
    RECHARGE = "recharge"   # 充值
    REFUND = "refund"       # 退款
    ADJUST = "adjust"       # 手动调整
    EXPIRE = "expire"       # 过期清零


class ProductStatus(Enum):
    """产品状态"""
    OFFLINE = 0  # 下架
    ONLINE = 1   # 上架


# ============================================================
# 数据模型
# ============================================================

class MembershipCardProduct(Base, TenantMixin, TimestampMixin):
    """
    会员卡产品（商品配置）
    
    管理员创建的产品模板，定义：
    - 价格
    - 次数/有效期
    - 适用课程范围
    - 使用限制
    """
    __tablename__ = "membership_card_products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="产品名称")
    card_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="卡类型")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, comment="售价")
    total_credits: Mapped[int | None] = mapped_column(Integer, comment="总次数（次卡专用）")
    validity_days: Mapped[int | None] = mapped_column(Integer, comment="有效天数（从购买日起算）")
    applicable_course_ids: Mapped[list[int] | None] = mapped_column(
        ARRAY(Integer), nullable=True, comment="适用课程ID列表，NULL表示不限",
    )
    applicable_course_type_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)), nullable=True, comment="适用的课程类型代码列表，NULL表示不限",
    )
    max_weekly_usage: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="每周最多使用次数，NULL表示不限",
    )
    description: Mapped[str | None] = mapped_column(Text, comment="产品描述")
    status: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=ProductStatus.ONLINE.value, comment="状态",
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序权重")
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="删除时间（软删除）",
    )

    __table_args__ = (
        Index("idx_products_tenant_status", "tenant_id", "status"),
        Index("idx_products_tenant_type", "tenant_id", "card_type"),
        Index("idx_products_deleted_at", "deleted_at"),
    )


class MembershipCard(Base, TenantMixin, TimestampMixin):
    """
    用户会员卡
    
    学员实际持有的会员卡，从产品创建。
    记录：
    - 总次数/已使用次数
    - 有效期
    - 状态
    - 冻结信息
    """
    __tablename__ = "membership_cards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    student_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, comment="学员ID",
    )
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("membership_card_products.id", ondelete="SET NULL"),
        nullable=True, comment="关联产品ID",
    )
    card_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="卡类型（冗余字段）")
    total_credits: Mapped[int | None] = mapped_column(Integer, comment="总次数")
    used_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="已使用次数")
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="生效时间")
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="过期时间")
    applicable_course_ids: Mapped[list[int] | None] = mapped_column(
        ARRAY(Integer), nullable=True, comment="适用课程ID列表（从产品继承）",
    )
    applicable_course_type_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)), nullable=True, comment="适用的课程类型代码列表（从产品继承）",
    )
    max_weekly_usage: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="每周使用上限（从产品继承）",
    )
    status: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=CardStatus.PENDING.value, comment="状态",
    )
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="冻结时间")
    frozen_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="冻结到期时间（NULL表示无限期冻结）")
    frozen_reason: Mapped[str | None] = mapped_column(String(255), comment="冻结原因")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, comment="操作人ID")
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="作废时间")
    cancelled_reason: Mapped[str | None] = mapped_column(String(255), comment="作废原因")

    __table_args__ = (
        Index("idx_cards_student", "tenant_id", "student_id", "status"),
        Index("idx_cards_product", "tenant_id", "product_id"),
        Index("idx_cards_expire", "tenant_id", "expire_at", "status"),
        CheckConstraint(
            "used_credits >= 0 AND (total_credits IS NULL OR used_credits <= total_credits)",
            name="chk_credits_range",
        ),
    )

    @property
    def remaining_credits(self) -> int | None:
        """剩余次数"""
        if self.total_credits is None:
            return None
        return self.total_credits - self.used_credits


class MembershipCardTransaction(Base, TenantMixin, TimestampMixin):
    """
    会员卡消费流水
    
    记录每次课时变动，用于审计和追溯。
    余额计算公式：
        当前余额 = total_credits - used_credits
        或通过流水累加：SUM(change_amount)
    """
    __tablename__ = "membership_card_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    card_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("membership_cards.id", ondelete="RESTRICT"), nullable=False, comment="会员卡ID",
    )
    booking_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True, comment="关联预约ID",
    )
    operation_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="操作类型")
    change_amount: Mapped[int] = mapped_column(Integer, nullable=False, comment="变动数量（正数增加，负数扣减）")
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False, comment="变动后剩余次数")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, comment="操作人ID")
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, comment="幂等键",
    )
    remark: Mapped[str | None] = mapped_column(String(255), comment="备注")

    __table_args__ = (
        Index("idx_transactions_card", "tenant_id", "card_id"),
        Index("idx_transactions_booking", "tenant_id", "booking_id"),
        Index("idx_transactions_created", "tenant_id", text("created_at DESC")),
        Index("idx_transactions_idempotency", "idempotency_key", unique=True,
              postgresql_where=text("idempotency_key IS NOT NULL")),
    )


class MembershipCardFreeze(Base, TenantMixin, TimestampMixin):
    """
    会员卡冻结记录
    
    记录冻结/解冻操作历史。
    """
    __tablename__ = "membership_card_freezes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    public_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False, default=uuid4,
    )
    card_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("membership_cards.id", ondelete="RESTRICT"), nullable=False, comment="会员卡ID",
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False, comment="冻结原因")
    frozen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="冻结时间",
    )
    unfrozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="解冻时间")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, comment="操作人ID")

    __table_args__ = (
        Index("idx_freezes_card", "tenant_id", "card_id"),
        Index("idx_freezes_created", "tenant_id", text("created_at DESC")),
    )