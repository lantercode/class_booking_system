"""
Upload Router - 文件上传路由

统一入口：/api/v1/upload/*
目前只暴露图片上传（多业务场景用 biz_type 区分）。
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.rbac import require_roles
from app.core.response import success
from app.deps.auth import get_current_user
from app.modules.upload.schemas import UploadImageResponse
from app.modules.upload.service import UploadService

router = APIRouter(prefix="/upload", tags=["文件上传"])


@router.post(
    "/image",
    response_model=dict,
    status_code=200,
    summary="上传图片",
    description=(
        "上传图片文件（JPG/PNG/WEBP，最大 5MB），支持多业务场景。"
        "返回 object_key（业务表应存此值）和完整可访问 URL。"
    ),
)
@require_roles("admin", "super_admin")
async def upload_image(
    file: UploadFile = File(..., description="图片文件 (multipart/form-data)"),
    biz_type: str = Form(
        ...,
        description="业务场景枚举：avatar | classroom_cover | banner | video_cover | notice",
    ),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """上传图片（带审计）."""
    uploader_id = current_user.get("user_id") if current_user else None

    service = UploadService(db=db)
    result: UploadImageResponse = await service.upload_image(
        file=file,
        biz_type=biz_type,
        uploader_id=uploader_id,
    )

    return success(
        data={
            "object_key": result.object_key,
            "url": result.url,
            "mime": result.mime,
            "size": result.size,
            "biz_type": result.biz_type,
        },
        msg="图片上传成功",
    )
