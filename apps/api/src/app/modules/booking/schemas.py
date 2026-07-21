"""
Booking Schemas - 预约模块数据模型

使用 Pydantic v2 进行请求/响应验证。
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BookingCreate(BaseModel):
    """创建预约请求体"""
    schedule_id: int = Field(..., description="排期ID")
    source: Optional[str] = Field("self", description="预约来源: self/admin/teacher")
    membership_card_id: Optional[int] = Field(None, description="会员卡ID")


class BookingUpdate(BaseModel):
    """更新预约请求体"""
    status: Optional[int] = Field(None, ge=1, le=5, description="状态：1已预约/2已取消/3已签到/4已完成/5未到场")
    cancelled_reason: Optional[str] = Field(None, max_length=255, description="取消原因")


class BookingResponse(BaseModel):
    """预约响应体"""
    id: int
    public_id: str
    tenant_id: int
    schedule_id: int
    student_id: int
    status: int
    source: str
    membership_card_id: Optional[int] = None
    booked_at: datetime
    cancelled_at: Optional[datetime] = None
    cancelled_reason: Optional[str] = None
    checked_in_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    student_nickname: Optional[str] = None
    student_phone: Optional[str] = None

    model_config = {"from_attributes": True}


class BookingListResponse(BaseModel):
    """预约列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页数量")
    items: list[BookingResponse]