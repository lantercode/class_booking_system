"""
Booking Schemas - 预约模块数据模型

使用 Pydantic v2 进行请求/响应验证。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class BookingCreate(BaseModel):
    """创建预约请求体"""

    schedule_id: int = Field(..., description="排期ID")
    source: str | None = Field("self", description="预约来源: self/admin/teacher")
    membership_card_id: int | None = Field(None, description="会员卡ID")


class BookingRescheduleRequest(BaseModel):
    """改期 / 改派请求体（F6.5）"""

    new_schedule_id: int = Field(..., ge=1, description="目标排期ID")
    new_membership_card_id: int | None = Field(
        None, ge=1, description="目标会员卡ID；不传=沿用原卡"
    )
    reason: str | None = Field(None, max_length=200, description="改期原因")


class BookingUpdate(BaseModel):
    """更新预约请求体"""

    status: int | None = Field(
        None, ge=1, le=5, description="状态：1已预约/2已取消/3已签到/4已完成/5未到场"
    )
    cancelled_reason: str | None = Field(None, max_length=255, description="取消原因")


class BookingResponse(BaseModel):
    """预约响应体"""

    id: int = Field(..., description="预约ID")
    public_id: str = Field(..., description="对外公开ID（UUID）")
    tenant_id: int = Field(..., description="租户ID")
    schedule_id: int = Field(..., description="排期ID")
    student_id: int = Field(..., description="学员ID")
    status: int = Field(..., description="状态：1已预约/2已取消/3已签到/4已完成/5未到场")
    display_status: int = Field(..., description="显示状态：1待上课/2已取消/3上课中/4已完成")
    source: str = Field(
        ..., description="预约来源：self=学员自行预约/admin=管理员代约/teacher=教师代约"
    )
    membership_card_id: int | None = Field(None, description="会员卡ID")
    booked_at: datetime = Field(..., description="预约时间")
    cancelled_at: datetime | None = Field(None, description="取消时间")
    cancelled_reason: str | None = Field(None, description="取消原因")
    checked_in_at: datetime | None = Field(None, description="签到时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    student_nickname: str | None = Field(None, description="学员昵称（关联查询）")
    student_phone: str | None = Field(None, description="学员手机号（关联查询）")

    course_name: str | None = Field(None, description="课程名称（关联查询）")
    start_at: datetime | None = Field(None, description="上课开始时间（关联查询）")
    end_at: datetime | None = Field(None, description="上课结束时间（关联查询）")
    classroom_name: str | None = Field(None, description="教室名称（关联查询）")
    teacher_name: str | None = Field(None, description="教师名称（关联查询）")

    card_no: str | None = Field(None, description="会员卡编号（关联查询）")
    card_status: int | None = Field(None, description="会员卡状态：0未激活/1使用中/2已过期/3已冻结/6已作废（关联查询）")
    card_type: str | None = Field(None, description="会员卡类型 count/period（关联查询）")
    remaining_credits: int | None = Field(None, description="剩余课时（次卡，关联查询）")

    model_config = {"from_attributes": True}


class BookingRescheduleResponse(BaseModel):
    """改期 / 改派响应体（F6.5，D-11）"""

    mode: str = Field(..., description="reschedule=改期 / card_swap=同排期改派")
    previous_booking_id: int = Field(..., description="原预约ID")
    previous_status: int = Field(..., description="原预约状态（改期前恒为已预约1）")
    booking: BookingResponse = Field(..., description="改期后新预约 / 改派后的当前预约")


class BookingListResponse(BaseModel):
    """预约列表分页响应"""

    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=500, description="每页数量")
    items: list[BookingResponse]


class AffectedBookingItem(BaseModel):
    """受影响预约明细项（F6.7，K1 口径：BOOKED/CHECKED_IN 且排期未开始）"""

    booking_id: int = Field(..., description="预约ID")
    schedule_id: int = Field(..., description="排期ID")
    status: int = Field(..., description="预约状态：1已预约/3已签到")
    start_at: datetime = Field(..., description="上课开始时间（UTC）")
    end_at: datetime = Field(..., description="上课结束时间（UTC）")
    course_name: str | None = Field(None, description="课程名称（关联查询）")
    classroom_name: str | None = Field(None, description="教室名称（关联查询）")
    teacher_name: str | None = Field(None, description="教师名称（关联查询）")


class AffectedBookingsResponse(BaseModel):
    """会员卡受影响预约分页响应（F6.7）"""

    card_id: int = Field(..., description="会员卡ID")
    card_status: int = Field(..., description="会员卡当前状态（CardStatus 枚举值）")
    total: int = Field(..., description="受影响预约总数（跨分页）")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页数量")
    items: list[AffectedBookingItem]
