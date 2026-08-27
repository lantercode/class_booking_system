from datetime import datetime

from pydantic import BaseModel, Field

# ==================== 请求 Schemas ====================

class RegisterRequest(BaseModel):
    """用户注册请求"""
    tenant_slug: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="租户标识符",
        examples=["dance-school"]
    )

    phone: str = Field(
        ...,
        pattern=r"^1[3-9]\d{9}$",
        description="手机号码",
        examples=["13800138000"]
    )

    password: str = Field(
        ...,
        min_length=8,
        max_length=20,
        description="密码（8-20位，需包含大小写字母+数字+特殊字符）",
        examples=["P@ssw0rd123"]
    )

    verify_code: str = Field(
        ...,
        min_length=4,
        max_length=6,
        description="验证码（4-6位数字或字母）",
        examples=["000000"]
    )

    nickname: str = Field(
        ...,
        min_length=2,
        max_length=20,
        description="用户昵称（2-20个字符）",
        examples=["小明"]
    )


class LoginRequest(BaseModel):
    """用户登录请求"""
    tenant_slug: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="租户标识符",
        examples=["dance-school"]
    )
    phone: str = Field(
        ...,
        pattern=r"^1[3-9]\d{9}$",
        description="手机号码",
        examples=["13800138000"]
    )

    password: str = Field(
        ...,
        min_length=8,
        max_length=20,
        description="密码",
        examples=["P@ssw0rd123"]
    )


class WechatLoginRequest(BaseModel):
    """微信登录请求"""
    code: str = Field(
        ...,
        description="微信登录凭证"
    )

    tenant_slug: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="租户标识符",
        examples=["dance-school"]
    )

    app_id: str | None = Field(
        None,
        description="小程序 AppId，不传则使用默认配置"
    )


class WechatBindRequest(BaseModel):
    """微信绑定请求"""
    bind_token: str = Field(
        ...,
        description="上一步自动登录返回的临时凭证"
    )

    phone: str | None = Field(
        None,
        pattern=r"^1[3-9]\d{9}$",
        description="手机号码（手动输入时使用）",
        examples=["13800138000"]
    )

    encrypted_data: str | None = Field(
        None,
        description="微信手机号授权返回的加密数据"
    )

    iv: str | None = Field(
        None,
        description="微信手机号授权返回的初始向量"
    )

    tenant_slug: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="租户标识符",
        examples=["dance-school"]
    )



class RefreshTokenRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str = Field(
        ...,
        description="刷新令牌",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."]
    )


class UpdateUserRequest(BaseModel):
    """更新用户信息请求"""
    nickname: str | None = Field(
        None,
        min_length=2,
        max_length=20,
        description="用户昵称",
        examples=["新昵称"]
    )

    avatar: str | None = Field(
        None,
        description="头像 URL",
        examples=["https://example.com/avatar.jpg"]
    )

    gender: str | None = Field(
        None,
        pattern=r"^(male|female|other)$",
        description="性别（male/female/other）",
        examples=["male"]
    )


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    old_password: str = Field(
        ...,
        min_length=8,
        max_length=20,
        description="旧密码",
        examples=["OldP@ss123"]
    )

    new_password: str = Field(
        ...,
        min_length=8,
        max_length=20,
        description="新密码",
        examples=["NewP@ss456"]
    )


# ==================== 响应 Schemas ====================

class TokenResponse(BaseModel):
    """令牌响应（双 Token）"""
    access_token: str = Field(
        ...,
        description="访问令牌（有效期 2 小时）",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...access..."]
    )

    refresh_token: str = Field(
        ...,
        description="刷新令牌（有效期 7 天）",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...refresh..."]
    )

    token_type: str = Field(
        default="bearer",
        description="令牌类型",
        examples=["bearer"]
    )

    expires_in: int = Field(
        default=7200,
        description="访问令牌过期时间（秒）",
        examples=[7200]
    )


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int = Field(
        ...,
        description="用户 ID",
        examples=[1]
    )

    phone: str = Field(
        ...,
        description="手机号（脱敏显示）",
        examples=["138****8000"]
    )

    nickname: str = Field(
        ...,
        min_length=2,
        max_length=20,
        description="用户昵称",
        examples=["小明"]
    )

    avatar: str | None = Field(
        None,
        description="头像 URL",
        examples=["https://example.com/avatar.jpg"]
    )

    gender: str | None = Field(
        None,
        description="性别",
        examples=["male"]
    )

    status: int = Field(
        ...,
        description="用户状态（1=正常 2=禁用）",
        examples=[1]
    )

    created_at: datetime = Field(
        ...,
        description="注册时间",
        examples=["2026-06-25T10:30:00Z"]
    )


class AuthResponse(TokenResponse):
    """认证响应（继承 TokenResponse + 用户信息）"""
    user: UserResponse = Field(
        ...,
        description="当前用户信息"
    )

class WechatLoginResponse(BaseModel):
    """微信登录响应"""
    need_bind: bool = Field(
        ...,
        description="是否需要绑定手机号",
        examples=[True]
    )
    bind_token: str | None = Field(
        None,
        description="绑定凭证"
    )
    access_token: str | None = Field(
        None,
        description="访问令牌"
    )
    refresh_token: str | None = Field(
        None,
        description="刷新令牌"
    )
    token_type: str | None = Field(
        default="bearer",
        description="令牌类型",
        examples=["bearer"]
    )
    expires_in: int = Field(
        default=7200,
        description="访问令牌过期时间（秒）",
        examples=[7200]
    )
    user: UserResponse | None = Field(
        None,
        description="当前用户信息"
    )
    decrypted_phone: str | None = Field(
        None,
        description="解密后的微信绑定手机号（手机号未注册时返回）",
        examples=["13800138000"]
    )
    error_msg: str | None = Field(
        None,
        description="错误提示信息",
        examples=["该手机号未在系统中注册，请联系机构前台"]
    )


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str = Field(
        ...,
        description="提示消息",
        examples=["操作成功"]
    )
