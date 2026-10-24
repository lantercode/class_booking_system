"""通用模块路由 - 健康检查、文件上传等无业务依赖的接口."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import (
    BusinessException,
    ValidationException,
)
from app.core.oss import ALLOWED_IMAGE_TYPES, get_oss_service
from app.core.rbac import require_roles
from app.core.response import success
from app.deps.auth import get_current_user, get_redis_client

router = APIRouter(prefix="/common", tags=["Common"])


# ============================================================
# 健康检查
# ============================================================


@router.get(
    "/health",
    summary="健康检查",
    description="检查服务运行状态和 Redis 连接",
)
async def health() -> dict:
    """健康检查接口"""
    redis_client = await get_redis_client()

    status = {
        "status": "healthy" if redis_client else "degraded",
        "redis": "connected" if redis_client else "disconnected",
    }
    if not redis_client:
        status["status"] = "unhealthy"
        raise HTTPException(503, detail=status)

    return status


# ============================================================
# 文件上传
# ============================================================


@router.post(
    "/upload/image",
    summary="上传图片",
    description="上传图片文件（头像、封面等），支持 JPG/PNG/GIF/WEBP 格式，最大 2MB",
)
@require_roles("admin", "super_admin", "teacher", "student")
async def upload_image(
    file: UploadFile = File(..., description="图片文件"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """上传图片文件"""
    # 验证文件类型
    if file.content_type and file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationException(f"不支持的图片格式：{file.content_type}，仅支持 JPG/PNG/GIF/WEBP")

    # 读取文件内容并验证大小（2MB）
    content = await file.read()
    file_size = len(content)
    max_size = 2 * 1024 * 1024  # 2MB

    if file_size > max_size:
        raise ValidationException(
            f"图片大小不能超过 2MB，当前大小：{file_size / (1024 * 1024):.2f}MB"
        )

    if file_size == 0:
        raise ValidationException("图片文件不能为空")

    # 上传到 OSS
    from io import BytesIO

    file_obj = BytesIO(content)

    oss = get_oss_service()
    result = await oss.upload(
        file_obj,
        path_prefix="avatars",
        filename=file.filename,
        content_type=file.content_type,
        allowed_types=ALLOWED_IMAGE_TYPES,
        max_size_mb=2,
    )

    if not result.success:
        raise BusinessException(f"上传失败：{result.error_message}")

    return success(
        data={
            "url": result.url,
            "filename": result.filename,
            "size": result.size,
            "content_type": result.content_type,
        },
        msg="图片上传成功",
    )
