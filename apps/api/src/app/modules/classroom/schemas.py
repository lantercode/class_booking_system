"""
Classroom Schemas - 教室模块数据模型

使用 Pydantic v2 进行请求/响应验证。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ClassroomCreate(BaseModel):
    """创建教室请求体"""
    name: str = Field(..., min_length=1, max_length=50, description="教室名称")
    equipment: list[str] | None = Field(default=[], description="设备列表")


class ClassroomUpdate(BaseModel):
    """更新教室请求体（部分更新）"""
    name: str | None = Field(None, min_length=1, max_length=50, description="教室名称")
    equipment: list[str] | None = Field(None, description="设备列表")
    status: int | None = Field(None, ge=0, le=1, description="状态：0禁用/1启用")


class ClassroomResponse(BaseModel):
    """教室响应体"""
    id: int
    tenant_id: int
    name: str
    equipment: list[str] | None = None
    status: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClassroomListResponse(BaseModel):
    """教室列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页数量")
    items: list[ClassroomResponse]
