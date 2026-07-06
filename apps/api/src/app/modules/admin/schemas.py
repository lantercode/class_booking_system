"""
管理后台模块 - 数据模型定义

使用 Pydantic v2 进行请求/响应验证。
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    """用户基础信息"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$", description="手机号")
    is_active: bool = Field(True, description="是否激活")


class UserCreate(UserBase):
    """创建用户请求体"""
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    role_ids: List[int] = Field(default=[], description="分配的角色ID列表")


class UserUpdate(BaseModel):
    """更新用户请求体（部分更新）"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r"^1[3-9]\d{9}$")
    is_active: Optional[bool] = None
    role_ids: Optional[List[int]] = None


class UserResponse(UserBase):
    """用户响应体"""
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime
    roles: List[str] = Field(default=[], description="角色代码列表")

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """用户列表响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页数量")
    items: List[UserResponse]


class RoleResponse(BaseModel):
    """角色响应"""
    id: int
    code: str = Field(..., description="角色代码，如 admin, teacher")
    name: str = Field(..., description="角色名称")
    permissions: List[str] = Field(default=[], description="权限列表")

    model_config = {"from_attributes": True}


class PermissionInfo(BaseModel):
    """权限信息"""
    code: str = Field(..., description="权限码，如 user:create")
    name: str = Field(..., description="权限名称")
    module: str = Field(..., description="所属模块")
    description: Optional[str] = None


class PermissionListResponse(BaseModel):
    """当前用户的权限列表"""
    user_id: int
    tenant_id: int
    permissions: List[PermissionInfo]
    roles: List[str]
    cached: bool = Field(..., description="是否来自缓存")
