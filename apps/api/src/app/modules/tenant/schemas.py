"""
Tenant Schemas - 租户模块数据模型

用于租户配置与基本信息的更新与响应。
遵守 contracts.md：以 Pydantic 模型作为请求/响应 DTO 的唯一事实源。
"""

from pydantic import BaseModel, Field


# ============================================================
# 租户配置（settings）
# ============================================================


class TenantSettingsUpdate(BaseModel):
    """更新租户配置请求体

    设计说明：
    - 两个字段均带默认值，便于客户端只传需要修改的字段；
    - Router 使用 ``model_dump(exclude_unset=True)`` 仅传递客户端显式提交的字段，
      从而在 Service 层实现"浅合并、保留未传键"的语义。
    """

    booking_cancel_minutes: int = Field(
        default=90,
        ge=1,
        le=480,
        description="预约可提前取消的最少分钟数（1-480）；超出此窗口取消将影响课时",
    )
    booking_advance_days: int = Field(
        default=14,
        ge=1,
        le=90,
        description="预约可提前的最大天数（1-90）",
    )


class TenantSettingsResponse(BaseModel):
    """租户配置响应体（与 TenantService.get_settings 返回结构一致）"""

    booking_cancel_minutes: int = Field(..., description="预约取消时间窗口（分钟）")
    booking_advance_days: int = Field(..., description="预约提前天数")


# ============================================================
# 租户基本信息（info）
# ============================================================


class TenantInfoUpdate(BaseModel):
    """更新租户基本信息请求体

    设计说明：
    - ``name`` 必填（租户名称不可为空）；
    - 其余字段可选，仅当客户端显式传入且非 None 时才更新。
    """

    name: str = Field(..., min_length=1, max_length=100, description="租户名称")
    logo_url: str | None = Field(None, max_length=500, description="Logo URL")
    contact_phone: str | None = Field(None, max_length=20, description="联系电话")
    contact_email: str | None = Field(None, max_length=100, description="联系邮箱")


class TenantInfoResponse(BaseModel):
    """租户基本信息响应体（与 TenantService.get_tenant_info 返回结构一致）"""

    id: int = Field(..., description="租户ID")
    name: str = Field(..., description="租户名称")
    slug: str = Field(..., description="租户 slug")
    logo_url: str | None = Field(None, description="Logo URL")
    contact_phone: str | None = Field(None, description="联系电话")
    contact_email: str | None = Field(None, description="联系邮箱")
