"""
Upload Router - 文件上传路由

统一入口：/api/v1/upload/*
目前只暴露图片上传（多业务场景用 biz_type 区分）。
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.oss_client import OSS_PRESIGN_EXPIRES_SECONDS, resolve_object_url
from app.core.rbac import require_roles
from app.core.response import success
from app.core.tenant_context import get_tenant_id
from app.deps.auth import get_current_user
from app.modules.upload.schemas import UploadImageResponse
from app.modules.upload.service import UploadService

router = APIRouter(prefix="/upload", tags=["文件上传"])

# 预签名默认有效期来自配置（默认 1 小时），上限为 OSS 允许的 7 天
DEFAULT_PRESIGN_TTL_SECONDS = get_settings().OSS_PRESIGN_TTL_SECONDS


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
        description=(
            "业务场景枚举：avatar | course_cover | classroom_cover | "
            "banner | video_cover | notice"
        ),
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


@router.get(
    "/url/{object_key:path}",
    response_model=dict,
    summary="换取文件访问地址",
    description=(
        "根据 object_key 返回可访问 URL。私有 OSS Bucket 下返回预签名临时地址，"
        "前端在图片加载失败（签名过期）时调用本接口换新链接。"
        "仅允许访问当前租户命名空间（t/{tenant_id}/）下的对象。"
    ),
)
async def get_object_url(
    object_key: str = Path(..., description="上传时返回的 object_key"),
    expires_seconds: int = Query(
        DEFAULT_PRESIGN_TTL_SECONDS,
        ge=60,
        le=OSS_PRESIGN_EXPIRES_SECONDS,
        description="签名有效期（秒），默认取 OSS_PRESIGN_TTL_SECONDS，仅 OSS 模式生效",
    ),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """按 object_key 换取访问 URL（含租户命名空间校验）。"""
    tenant_id = get_tenant_id()
    if not tenant_id:
        raise HTTPException(status_code=400, detail="租户上下文缺失")

    # 只允许访问本租户前缀下的对象，防止跨租户猜 key
    expected_prefix = f"t/{tenant_id}/"
    if not object_key.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="无权访问该文件")

    url = await resolve_object_url(object_key, expires_seconds=expires_seconds)
    return success(data={"object_key": object_key, "url": url, "expires_seconds": expires_seconds})
