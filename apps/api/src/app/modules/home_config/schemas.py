"""Home Config Schemas - 首页配置 DTO"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class HomeConfigResponse(BaseModel):
    """首页配置响应（draft / published 通用）"""

    model_config = {"from_attributes": True}

    id: int
    tenant_id: int
    scope: str
    version: int
    payload: dict[str, Any]
    published_at: datetime | None = None
    operator_id: int | None = None
    created_at: datetime
    updated_at: datetime


class HomeConfigDraftUpdate(BaseModel):
    """更新 draft 的入参"""

    payload: dict[str, Any] = Field(..., description="完整首页配置 JSON，顶层需含 schema_version")

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, v: dict[str, Any]) -> dict[str, Any]:
        # 1. 必须带 schema_version
        sv = v.get("schema_version")
        if sv is None:
            raise ValueError("payload 必须包含顶层字段 schema_version")
        if sv != 1:
            raise ValueError(f"schema_version 不匹配，当前只支持 1，收到 {sv}")

        # 2. modules 数组每个元素 type 枚举值校验（以 solution-design.md payload 结构为准）
        VALID_TYPES = {"banner", "teachers", "courses", "video", "notice"}
        modules = v.get("modules", [])
        if not isinstance(modules, list):
            raise ValueError("modules 必须是数组")
        for idx, m in enumerate(modules):
            if not isinstance(m, dict):
                raise ValueError(f"modules[{idx}] 必须是对象")
            t = m.get("type")
            if t not in VALID_TYPES:
                raise ValueError(
                    f"modules[{idx}].type={t!r} 非法，允许值: {sorted(VALID_TYPES)}"
                )
        return v


class HomeConfigVersionItem(BaseModel):
    """已发布版本列表项"""

    model_config = {"from_attributes": True}

    id: int
    version: int
    published_at: datetime | None = None
    operator_id: int | None = None
    created_at: datetime
