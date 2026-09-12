"""
Membership Card Schemas - 会员卡模块数据模型

使用 Pydantic v2 进行请求/响应验证。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


def _uuid_to_str(v) -> str | None:
    """将 UUID 转为字符串"""
    if v is None:
        return None
    if isinstance(v, UUID):
        return str(v)
    return str(v)


def _format_datetime(dt: datetime | None) -> str | None:
    """将 datetime 格式化为 yyyy-MM-dd HH:mm:ss"""
    if dt is None:
        return None
    return dt.strftime('%Y-%m-%d %H:%M:%S')


# ============================================================
# 产品相关
# ============================================================

class MembershipCardProductCreate(BaseModel):
    """创建会员卡产品请求体"""
    name: str = Field(..., max_length=100, description="产品名称")
    card_type: str = Field(..., description="卡类型：count/period/unlimited")
    price: float = Field(..., ge=0, description="售价")
    total_credits: int | None = Field(None, ge=1, description="总次数（次卡专用）")
    validity_days: int | None = Field(None, ge=1, description="有效天数")
    applicable_course_type_codes: list[str] = Field(..., min_length=1, description="适用的课程类型代码列表（必填，至少一项）")
    applicable_course_ids: list[int] | None = Field(None, description="适用课程ID列表，NULL表示不限")
    max_weekly_usage: int | None = Field(None, ge=1, description="每周最多使用次数，NULL表示不限")
    description: str | None = Field(None, max_length=500, description="产品描述")
    sort_order: int = Field(0, description="排序")


class MembershipCardProductUpdate(BaseModel):
    """更新会员卡产品请求体"""
    name: str | None = Field(None, max_length=100, description="产品名称")
    price: float | None = Field(None, ge=0, description="售价")
    total_credits: int | None = Field(None, description="总次数（次卡专用）")
    validity_days: int | None = Field(None, ge=1, description="有效天数")
    applicable_course_ids: list[int] | None = Field(None, description="适用课程ID列表，NULL表示不限")
    applicable_course_type_codes: list[str] | None = Field(None, description="适用的课程类型代码列表，NULL表示不限")
    max_weekly_usage: int | None = Field(None, ge=1, description="每周最多使用次数，NULL表示不限")
    description: str | None = Field(None, max_length=500, description="产品描述")
    status: int | None = Field(None, ge=0, le=1, description="状态：0下架/1上架")
    sort_order: int | None = Field(None, description="排序")


class MembershipCardProductResponse(BaseModel):
    """会员卡产品响应体"""
    id: int = Field(..., description="产品ID")
    public_id: str = Field(..., description="对外公开ID（UUID）")
    name: str = Field(..., description="产品名称")
    card_type: str = Field(..., description="卡类型")
    price: float = Field(..., description="售价")
    total_credits: int | None = Field(None, description="总次数")
    validity_days: int | None = Field(None, description="有效天数")
    applicable_course_ids: list[int] | None = Field(None, description="适用课程ID列表")
    applicable_course_type_codes: list[str] | None = Field(None, description="适用的课程类型代码列表")
    max_weekly_usage: int | None = Field(None, description="每周最多使用次数")
    description: str | None = Field(None, description="产品描述")
    status: int = Field(..., description="状态")
    sort_order: int = Field(..., description="排序")
    deleted_at: datetime | None = Field(None, description="删除时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}

    @field_validator("public_id", mode="before")
    @classmethod
    def validate_public_id(cls, v):
        return _uuid_to_str(v)


class MembershipCardProductListResponse(BaseModel):
    """产品列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=500, description="每页数量")
    items: list[MembershipCardProductResponse]


# ============================================================
# 会员卡相关
# ============================================================

class MembershipCardCreate(BaseModel):
    """发放会员卡请求体"""
    student_id: int = Field(..., description="学员ID")
    product_id: int | None = Field(None, description="关联产品ID")
    total_credits: int | None = Field(None, description="总次数（次卡专用）")
    validity_days: int | None = Field(None, ge=1, description="有效天数（次卡必填，期卡必填）")
    valid_from: datetime | str | None = Field(None, description="生效时间（NULL表示立即激活，支持 YYYY-MM-DD 或 ISO 格式）")
    applicable_course_ids: list[int] | None = Field(None, description="适用课程ID列表")
    applicable_course_type_codes: list[str] | None = Field(None, description="适用的课程类型代码列表")
    max_weekly_usage: int | None = Field(None, ge=1, description="每周最多使用次数")
    allow_duplicate: bool = Field(False, description="是否允许重复发卡（默认False，True表示允许续卡）")
    remark: str | None = Field(None, max_length=255, description="备注")

    @field_validator("valid_from", mode="before")
    @classmethod
    def parse_valid_from(cls, v):
        """将 YYYY-MM-DD 格式的字符串转为 datetime"""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # 如果是 YYYY-MM-DD 格式，补充时分秒
            if len(v) == 10 and v.count('-') == 2:
                v = f"{v} 00:00:00"
            # 解析 datetime
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                return v
        return v


class MembershipCardResponse(BaseModel):
    """会员卡响应体"""
    id: int = Field(..., description="会员卡ID")
    public_id: str = Field(..., description="对外公开ID（UUID）")
    student_id: int = Field(..., description="学员ID")
    product_id: int | None = Field(None, description="关联产品ID")
    card_type: str = Field(..., description="卡类型")
    total_credits: int | None = Field(None, description="总次数")
    used_credits: int = Field(..., description="已使用次数")
    remaining_credits: int | None = Field(None, description="剩余次数")
    valid_from: str | None = Field(None, description="生效时间")
    expire_at: str | None = Field(None, description="过期时间")
    applicable_course_ids: list[int] | None = Field(None, description="适用课程ID列表")
    applicable_course_type_codes: list[str] | None = Field(None, description="适用的课程类型代码列表")
    max_weekly_usage: int | None = Field(None, description="每周最多使用次数")
    status: int = Field(..., description="状态")
    frozen_at: str | None = Field(None, description="冻结时间")
    frozen_until: str | None = Field(None, description="冻结到期时间")
    frozen_reason: str | None = Field(None, description="冻结原因")
    cancelled_at: str | None = Field(None, description="作废时间")
    cancelled_reason: str | None = Field(None, description="作废原因")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")

    # 以下为关联查询字段（不在 ORM 模型中，需要手动填充）
    student_nickname: str | None = None
    student_phone: str | None = None
    product_name: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("public_id", mode="before")
    @classmethod
    def validate_public_id(cls, v):
        return _uuid_to_str(v)

    @field_validator("valid_from", "expire_at", "frozen_at", "frozen_until", "cancelled_at", "created_at", "updated_at", mode="before")
    @classmethod
    def format_datetime(cls, v):
        return _format_datetime(v)


class MembershipCardListResponse(BaseModel):
    """会员卡列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=500, description="每页数量")
    items: list[MembershipCardResponse]


# ============================================================
# 消费流水相关
# ============================================================

class MembershipCardTransactionResponse(BaseModel):
    """消费流水响应体"""
    id: int = Field(..., description="流水ID")
    public_id: str = Field(..., description="对外公开ID（UUID）")
    card_id: int = Field(..., description="会员卡ID")
    booking_id: int | None = Field(None, description="关联预约ID")
    operation_type: str = Field(..., description="操作类型")
    change_amount: int = Field(..., description="变动数量")
    balance_after: int = Field(..., description="变动后剩余次数")
    operator_id: int | None = Field(None, description="操作人ID")
    idempotency_key: str | None = Field(None, description="幂等键")
    remark: str | None = Field(None, description="备注")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}

    @field_validator("public_id", mode="before")
    @classmethod
    def validate_public_id(cls, v):
        return _uuid_to_str(v)


class MembershipCardTransactionListResponse(BaseModel):
    """消费流水列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=500, description="每页数量")
    items: list[MembershipCardTransactionResponse]


# ============================================================
# 冻结记录相关
# ============================================================

class MembershipCardFreezeRequest(BaseModel):
    """冻结会员卡请求体"""
    reason: str = Field(..., max_length=255, description="冻结原因")
    freeze_days: int = Field(..., ge=1, le=365, description="冻结天数（1-365天）")
    auto_unfreeze: bool = Field(True, description="是否到期自动解冻（默认True）")


class MembershipCardExtendRequest(BaseModel):
    """延长会员卡有效期请求体"""
    extend_days: int = Field(..., ge=1, description="延长天数")
    remark: str | None = Field(None, max_length=255, description="延期原因")


class MembershipCardCancelRequest(BaseModel):
    """作废会员卡请求体"""
    reason: str = Field(..., max_length=255, description="作废原因")


class MembershipCardFreezeResponse(BaseModel):
    """冻结记录响应体"""
    id: int = Field(..., description="冻结记录ID")
    public_id: str = Field(..., description="对外公开ID（UUID）")
    card_id: int = Field(..., description="会员卡ID")
    reason: str = Field(..., description="冻结原因")
    frozen_at: datetime = Field(..., description="冻结时间")
    unfrozen_at: datetime | None = Field(None, description="解冻时间")
    operator_id: int | None = Field(None, description="操作人ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}

    @field_validator("public_id", mode="before")
    @classmethod
    def validate_public_id(cls, v):
        return _uuid_to_str(v)


class MembershipCardFreezeListResponse(BaseModel):
    """冻结记录列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=500, description="每页数量")
    items: list[MembershipCardFreezeResponse]