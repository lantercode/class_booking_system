"""
User Schemas - 用户模块数据模型

使用 Pydantic v2 进行请求/响应验证。
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """用户基础信息（用于请求）"""
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$", description="手机号")
    email: EmailStr | None = Field(None, description="邮箱")
    nickname: str | None = Field(None, min_length=1, max_length=50, description="昵称")
    real_name: str | None = Field(None, min_length=1, max_length=50, description="真实姓名")
    avatar_url: str | None = Field(None, description="头像URL")
    gender: int | None = Field(None, ge=0, le=2, description="性别：0未知/1男/2女")
    birthday: datetime | None = Field(None, description="生日")


class UserCreate(UserBase):
    """创建用户请求体"""
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    role_ids: list[int] | None = Field(default=[], description="初始角色ID列表")
    role_codes: list[str] | None = Field(default=[], description="初始角色代码列表（如 ['teacher']）")


class UserUpdate(BaseModel):
    """更新用户请求体（部分更新）"""
    phone: str | None = Field(None, pattern=r"^1[3-9]\d{9}$", description="手机号")
    email: EmailStr | None = Field(None, description="邮箱")
    nickname: str | None = Field(None, min_length=1, max_length=50, description="昵称")
    real_name: str | None = Field(None, min_length=1, max_length=50, description="真实姓名")
    avatar_url: str | None = Field(None, description="头像URL")
    gender: int | None = Field(None, ge=0, le=2, description="性别")
    birthday: datetime | None = Field(None, description="生日")
    status: int | None = Field(None, ge=0, le=1, description="状态：0禁用/1启用")
    role_ids: list[int] | None = Field(None, description="角色ID列表（传入则覆盖更新）")


class UserResponse(BaseModel):
    """用户响应体"""
    id: int
    public_id: str
    tenant_id: int
    phone: str
    email: str | None = None
    nickname: str | None = None
    real_name: str | None = None
    avatar_url: str | None = None
    gender: int | None = None
    birthday: datetime | None = None
    status: int
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    roles: list[str] = Field(default=[], description="角色代码列表")

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """用户列表分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=100, description="每页数量")
    items: list[UserResponse]


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")


class ResetPasswordRequest(BaseModel):
    """重置密码请求（管理员操作）"""
    user_id: int = Field(..., description="用户ID")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")


