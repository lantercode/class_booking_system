"""
User Schemas - 用户模块数据模型

使用 Pydantic v2 进行请求/响应验证。
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    """用户基础信息（用于请求）"""
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$", description="手机号")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    nickname: Optional[str] = Field(None, min_length=1, max_length=50, description="昵称")
    real_name: Optional[str] = Field(None, min_length=1, max_length=50, description="真实姓名")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    gender: Optional[int] = Field(None, ge=0, le=2, description="性别：0未知/1男/2女")
    birthday: Optional[datetime] = Field(None, description="生日")


class UserCreate(UserBase):
    """创建用户请求体"""
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    role_ids: Optional[List[int]] = Field(default=[], description="初始角色ID列表")
    role_codes: Optional[List[str]] = Field(default=[], description="初始角色代码列表（如 ['teacher']）")


class UserUpdate(BaseModel):
    """更新用户请求体（部分更新）"""
    phone: Optional[str] = Field(None, pattern=r"^1[3-9]\d{9}$", description="手机号")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    nickname: Optional[str] = Field(None, min_length=1, max_length=50, description="昵称")
    real_name: Optional[str] = Field(None, min_length=1, max_length=50, description="真实姓名")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    gender: Optional[int] = Field(None, ge=0, le=2, description="性别")
    birthday: Optional[datetime] = Field(None, description="生日")
    status: Optional[int] = Field(None, ge=0, le=1, description="状态：0禁用/1启用")
    role_ids: Optional[List[int]] = Field(None, description="角色ID列表（传入则覆盖更新）")


class UserResponse(BaseModel):
    """用户响应体"""
    id: int
    public_id: str
    tenant_id: int
    phone: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    real_name: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: Optional[int] = None
    birthday: Optional[datetime] = None
    status: int
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    roles: List[str] = Field(default=[], description="角色代码列表")

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """用户列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页数量")
    items: List[UserResponse]


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")


class ResetPasswordRequest(BaseModel):
    """重置密码请求（管理员操作）"""
    user_id: int = Field(..., description="用户ID")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")