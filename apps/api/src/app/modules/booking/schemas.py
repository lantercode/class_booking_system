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


class BookingUpdate(BaseModel):
    """更新预约请求体"""
    status: int | None = Field(None, ge=1, le=5, description="状态：1已预约/2已取消/3已签到/4已完成/5未到场")
    cancelled_reason: str | None = Field(None, max_length=255, description="取消原因")


class BookingResponse(BaseModel):
    """预约响应体"""
    id: int = Field(..., description="预约ID")
    public_id: str = Field(..., description="对外公开ID（UUID）")
    tenant_id: int = Field(..., description="租户ID")
    schedule_id: int = Field(..., description="排期ID")
    student_id: int = Field(..., description="学员ID")
    status: int = Field(..., description="状态：1已预约/2已取消/3已签到/4已完成/5未到场")
    source: str = Field(..., description="预约来源：self=学员自行预约/admin=管理员代约/teacher=教师代约")
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

    model_config = {"from_attributes": True}


class BookingListResponse(BaseModel):
    """预约列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=500, description="每页数量")
    items: list[BookingResponse]
