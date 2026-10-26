"""
Upload Schemas - 上传模块数据模型（Pydantic）.
"""

from pydantic import BaseModel, Field


class UploadImageResponse(BaseModel):
    """图片上传响应体 - Service 层返回给 Router，Router 用 success() 包装."""

    object_key: str = Field(
        ...,
        description="存储对象 key（业务表应存此值），如 t/1/avatar/uuid.jpg",
    )
    url: str = Field(..., description="完整可访问 URL（由 Service 根据 STORAGE_BACKEND 拼装）")
    mime: str = Field(..., description="MIME 类型")
    size: int = Field(..., description="文件字节数")
    biz_type: str = Field(
        ...,
        description="业务场景：avatar | classroom_cover | banner | video_cover | notice",
    )

    model_config = {"from_attributes": True}


class UploadImageRequest(BaseModel):
    """路由层不直接使用本 schema（文件用 UploadFile Form 接收），
    此 schema 仅作为 biz_type 的枚举校验参考。"""

    biz_type: str = Field(
        ...,
        pattern=r"^(avatar|classroom_cover|banner|video_cover|notice)$",
        description="业务场景枚举值",
    )
