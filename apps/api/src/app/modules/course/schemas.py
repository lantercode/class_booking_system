"""
Course Schemas - 课程模块数据模型

使用 Pydantic v2 进行请求/响应验证。
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CourseCreate(BaseModel):
    """创建课程请求体"""
    name: str = Field(..., min_length=1, max_length=100, description="课程名称")
    category: Optional[str] = Field(None, max_length=50, description="分类")
    level: Optional[str] = Field(None, max_length=20, description="难度等级")
    cover_url: Optional[str] = Field(None, max_length=500, description="封面图URL")
    description: Optional[str] = Field(None, description="课程描述")
    duration_minutes: int = Field(..., ge=1, description="时长（分钟）")
    max_capacity: int = Field(..., ge=1, description="最大容量")
    price: float = Field(0.0, ge=0, description="价格")
    required_credits: int = Field(1, ge=0, description="所需积分")


class CourseUpdate(BaseModel):
    """更新课程请求体（部分更新）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="课程名称")
    category: Optional[str] = Field(None, max_length=50, description="分类")
    level: Optional[str] = Field(None, max_length=20, description="难度等级")
    cover_url: Optional[str] = Field(None, max_length=500, description="封面图URL")
    description: Optional[str] = Field(None, description="课程描述")
    duration_minutes: Optional[int] = Field(None, ge=1, description="时长（分钟）")
    max_capacity: Optional[int] = Field(None, ge=1, description="最大容量")
    price: Optional[float] = Field(None, ge=0, description="价格")
    required_credits: Optional[int] = Field(None, ge=0, description="所需积分")
    status: Optional[int] = Field(None, ge=0, le=1, description="状态：0下架/1上架")


class CourseResponse(BaseModel):
    """课程响应体"""
    id: int
    public_id: str
    tenant_id: int
    name: str
    category: Optional[str] = None
    level: Optional[str] = None
    cover_url: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: int
    max_capacity: int
    price: float
    required_credits: int
    status: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CourseListResponse(BaseModel):
    """课程列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页数量")
    items: List[CourseResponse]