"""
Role Schemas - 角色权限模块数据模型

使用 Pydantic v2 进行请求/响应验证。
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime


class RoleBase(BaseModel):
    """角色基础信息"""
    code: str = Field(..., min_length=2, max_length=50, description="角色代码（唯一标识）")
    name: str = Field(..., min_length=1, max_length=50, description="角色名称")
    description: Optional[str] = Field(None, max_length=255, description="角色描述")


class RoleCreate(RoleBase):
    """创建角色请求体"""
    permission_ids: Optional[List[int]] = Field(default=[], description="初始权限ID列表")


class RoleUpdate(BaseModel):
    """更新角色请求体（部分更新）"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="角色名称")
    description: Optional[str] = Field(None, max_length=255, description="角色描述")


class RoleResponse(RoleBase):
    """角色响应体"""
    id: int
    tenant_id: Optional[int] = None
    is_system: bool = False
    created_at: datetime
    updated_at: datetime
    permissions: List[str] = Field(default=[], description="权限代码列表")

    model_config = {"from_attributes": True}


class RoleListResponse(BaseModel):
    """角色列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页数量")
    items: List[RoleResponse]


class PermissionResponse(BaseModel):
    """权限响应体"""
    id: int
    code: str = Field(..., description="权限代码，如 user:create")
    name: str = Field(..., description="权限名称")
    module: str = Field(..., description="所属模块")
    description: Optional[str] = Field(None, description="权限描述")

    model_config = {"from_attributes": True}


class PermissionListResponse(BaseModel):
    """权限列表响应"""
    total: int = Field(..., description="总数")
    items: List[PermissionResponse]


class AssignPermissionsRequest(BaseModel):
    """分配权限请求体"""
    permission_ids: List[int] = Field(..., description="要分配的权限ID列表")