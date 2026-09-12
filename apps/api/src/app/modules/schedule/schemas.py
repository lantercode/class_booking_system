"""
Schedule Schemas - 排期模块数据模型

使用 Pydantic v2 进行请求/响应验证。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleCreate(BaseModel):
    """创建排期请求体"""
    course_id: int = Field(..., description="课程ID")
    teacher_id: int = Field(..., description="教师ID（用户ID）")
    classroom_id: int | None = Field(None, description="教室ID")
    start_at: datetime = Field(..., description="开始时间")
    end_at: datetime = Field(..., description="结束时间")
    capacity: int = Field(..., ge=1, description="容量上限")
    booking_opens_at: datetime | None = Field(None, description="预约开放时间")
    booking_closes_at: datetime | None = Field(None, description="预约截止时间")
    cancel_deadline: datetime | None = Field(None, description="取消截止时间")
    notes: str | None = Field(None, max_length=500, description="备注")


class ScheduleUpdate(BaseModel):
    """更新排期请求体（部分更新）"""
    course_id: int | None = Field(None, description="课程ID")
    teacher_id: int | None = Field(None, description="教师ID")
    classroom_id: int | None = Field(None, description="教室ID")
    start_at: datetime | None = Field(None, description="开始时间")
    end_at: datetime | None = Field(None, description="结束时间")
    capacity: int | None = Field(None, ge=1, description="容量上限")
    booking_opens_at: datetime | None = Field(None, description="预约开放时间")
    booking_closes_at: datetime | None = Field(None, description="预约截止时间")
    cancel_deadline: datetime | None = Field(None, description="取消截止时间")
    status: int | None = Field(None, ge=1, le=3, description="状态：1正常/2已取消/3已完成")
    notes: str | None = Field(None, max_length=500, description="备注")


class ScheduleCancel(BaseModel):
    """取消排期请求体"""
    cancel_reason: str = Field(..., min_length=1, max_length=500, description="取消原因")


class ScheduleResponse(BaseModel):
    """排期响应体"""
    id: int
    public_id: str
    tenant_id: int
    course_id: int
    teacher_id: int
    classroom_id: int | None = None
    start_at: datetime
    end_at: datetime
    capacity: int
    booked_count: int
    booking_opens_at: datetime | None = None
    booking_closes_at: datetime | None = None
    cancel_deadline: datetime | None = None
    status: int
    display_status: int = Field(..., description="显示状态：1待上课/2上课中/3已取消/4已完成")
    notes: str | None = None
    cancel_reason: str | None = None
    cancelled_by: int | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    teacher_name: str | None = None
    course_name: str | None = None
    classroom_name: str | None = None
    course_type_code: str | None = None

    model_config = {"from_attributes": True}


class ScheduleListResponse(BaseModel):
    """排期列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=500, description="每页数量")
    items: list[ScheduleResponse]
