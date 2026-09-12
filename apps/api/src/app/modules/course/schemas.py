"""
Course Schemas - 课程模块数据模型

使用 Pydantic v2 进行请求/响应验证。
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ============================================================
# 课程类型相关
# ============================================================

class CourseTypeCreate(BaseModel):
    """创建课程类型请求体"""
    name: str = Field(..., min_length=1, max_length=50, description="类型名称")
    code: str = Field(..., min_length=1, max_length=50, description="类型代码")
    description: str | None = Field(None, description="描述")
    required_card_types: list[str] | None = Field(None, description="需要的会员卡类型列表")
    sort_order: int = Field(0, ge=0, description="排序")
    status: int = Field(1, ge=0, le=1, description="状态：0禁用/1启用")


class CourseTypeUpdate(BaseModel):
    """更新课程类型请求体（部分更新）"""
    name: str | None = Field(None, min_length=1, max_length=50, description="类型名称")
    code: str | None = Field(None, min_length=1, max_length=50, description="类型代码")
    description: str | None = Field(None, description="描述")
    required_card_types: list[str] | None = Field(None, description="需要的会员卡类型列表")
    sort_order: int | None = Field(None, ge=0, description="排序")
    status: int | None = Field(None, ge=0, le=1, description="状态：0禁用/1启用")


class CourseTypeResponse(BaseModel):
    """课程类型响应体"""
    id: int
    public_id: str
    tenant_id: int
    name: str
    code: str
    description: str | None = None
    required_card_types: list[str] | None = None
    sort_order: int
    status: int
    course_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CourseTypeListResponse(BaseModel):
    """课程类型列表响应"""
    total: int = Field(..., description="总数")
    items: list[CourseTypeResponse]


# ============================================================
# 课程相关
# ============================================================

class CourseCreate(BaseModel):
    """创建课程请求体"""
    name: str = Field(..., min_length=1, max_length=100, description="课程名称")
    category: str = Field(..., min_length=1, max_length=50, description="分类")
    course_type_code: str = Field(..., min_length=1, max_length=50, description="课程类型代码")
    level: str = Field(..., min_length=1, max_length=20, description="难度等级")
    cover_url: str | None = Field(None, max_length=500, description="封面图URL")
    description: str | None = Field(None, description="课程描述")
    duration_minutes: int = Field(90, ge=1, description="时长（分钟）")
    price: float = Field(0.0, ge=0, description="价格")
    required_credits: int = Field(1, ge=0, description="所需积分")


class CourseUpdate(BaseModel):
    """更新课程请求体（部分更新）"""
    name: str | None = Field(None, min_length=1, max_length=100, description="课程名称")
    category: str | None = Field(None, max_length=50, description="分类")
    course_type_code: str | None = Field(None, min_length=1, max_length=50, description="课程类型代码")
    level: str | None = Field(None, max_length=20, description="难度等级")
    cover_url: str | None = Field(None, max_length=500, description="封面图URL")
    description: str | None = Field(None, description="课程描述")
    duration_minutes: int | None = Field(None, ge=1, description="时长（分钟）")
    price: float | None = Field(None, ge=0, description="价格")
    required_credits: int | None = Field(None, ge=0, description="所需积分")
    status: int | None = Field(None, ge=0, le=1, description="状态：0下架/1上架")


class CourseResponse(BaseModel):
    """课程响应体"""
    id: int
    public_id: str
    tenant_id: int
    name: str
    category: str | None = None
    course_type_code: str | None = None
    level: str | None = None
    cover_url: str | None = None
    description: str | None = None
    duration_minutes: int
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
    page_size: int = Field(..., ge=1, le=500, description="每页数量")
    items: list[CourseResponse]