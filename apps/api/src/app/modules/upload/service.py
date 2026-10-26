"""
Upload Service - 文件上传核心业务逻辑层

职责：
- 四关校验：类型白名单 + 魔数 + 大小（<=5MB）+ biz_type 枚举
- 生成 object_key（含 tenant_id 前缀）
- 策略模式分发：local 本地存储 / OSS 云端存储
- 写 file_objects 审计表 + 提交事务
- 拼装可访问 URL

边界：
- 本 Service 不持有核心业务规则，仅封装存储与审计。
- 业务表（users.avatar_url / classrooms.cover_image_url）由调用方自行落库，
  调用方应只存 object_key，完整 URL 由 Service 层统一拼装。
"""

import logging
import os
import uuid
from typing import Final
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.modules.upload.repository import FileObjectRepository
from app.modules.upload.schemas import UploadImageResponse

logger = logging.getLogger(__name__)

# ============================================================
# 常量
# ============================================================

ALLOWED_MIME_TYPES: Final[set[str]] = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS: Final[set[str]] = {"jpg", "jpeg", "png", "webp"}
ALLOWED_BIZ_TYPES: Final[set[str]] = {
    "avatar",
    "classroom_cover",
    "banner",
    "video_cover",
    "notice",
}
MAX_IMAGE_SIZE_BYTES: Final[int] = 5 * 1024 * 1024  # 5MB

# 魔数：前 8 字节足够识别
MAGIC_SIGNATURES: dict[str, bytes] = {
    "jpg": b"\xff\xd8\xff",          # JPEG SOI
    "png": b"\x89PNG\r\n\x1a\n",     # PNG
}
# WEBP 较特殊：RIFF....WEBP 共 12 字节
WEBP_MAGIC_PREFIX = b"RIFF"
WEBP_MAGIC_SUFFIX = b"WEBP"


def _detect_image_extension(content: bytes) -> str | None:
    """通过魔数检测图片扩展名；未知返回 None."""
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if (
        len(content) >= 12
        and content[:4] == WEBP_MAGIC_PREFIX
        and content[8:12] == WEBP_MAGIC_SUFFIX
    ):
        return "webp"
    return None


class UploadService:
    """文件上传服务."""

    def __init__(
        self,
        db: AsyncSession,
        settings: Settings | None = None,
    ):
        self.db = db
        self.settings = settings or get_settings()
        self.repo = FileObjectRepository()

    # ============================================================
    # 公开方法
    # ============================================================

    async def upload_image(
        self,
        file: UploadFile,
        biz_type: str,
        uploader_id: int | None = None,
    ) -> UploadImageResponse:
        """上传图片文件并写入审计表。

        Args:
            file: FastAPI UploadFile（multipart 入参）
            biz_type: 业务场景枚举值
            uploader_id: 上传者用户 ID（可为 None）

        Returns:
            UploadImageResponse（含 object_key + 完整 URL）

        Raises:
            HTTPException: 400 入参校验失败；500 存储层异常
        """
        # --- 四关校验 ---
        self._validate_biz_type(biz_type)

        content = await self._validate_and_read(file)
        mime = file.content_type or "application/octet-stream"

        # --- 生成 object_key ---
        from app.core.tenant_context import get_tenant_id

        tenant_id = get_tenant_id()
        if not tenant_id:
            raise HTTPException(status_code=500, detail="租户上下文缺失，无法生成 object_key")

        ext = _detect_image_extension(content)
        if ext is None:
            raise HTTPException(status_code=400, detail="无法识别的图片内容（魔数校验失败）")

        object_key = f"t/{tenant_id}/{biz_type}/{uuid.uuid4().hex}.{ext}"

        # --- 存储：策略模式 ---
        try:
            if self.settings.STORAGE_BACKEND == "local":
                url = await self._store_local(object_key, content)
            elif self.settings.STORAGE_BACKEND == "oss":
                url = await self._store_oss(object_key, content, mime)
            else:
                raise HTTPException(status_code=500, detail="未知的 STORAGE_BACKEND 配置")
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("[UploadService] 存储层异常: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail="文件存储失败，请稍后重试") from exc

        # --- 写审计表 ---
        try:
            await self.repo.create(
                self.db,
                {
                    "object_key": object_key,
                    "mime": mime,
                    "size": len(content),
                    "biz_type": biz_type,
                    "uploader_id": uploader_id,
                },
                auto_commit=False,
            )
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            logger.error("[UploadService] 审计表写入失败: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail="文件元数据记录失败") from exc

        return UploadImageResponse(
            object_key=object_key,
            url=url,
            mime=mime,
            size=len(content),
            biz_type=biz_type,
        )

    # ============================================================
    # 私有：校验
    # ============================================================

    @staticmethod
    def _validate_biz_type(biz_type: str) -> None:
        if biz_type not in ALLOWED_BIZ_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"非法 biz_type，允许值: {sorted(ALLOWED_BIZ_TYPES)}",
            )

    async def _validate_and_read(self, file: UploadFile) -> bytes:
        """校验类型 + 魔数 + 大小，并读取内容（一次性）."""
        # 1) MIME 白名单
        mime = file.content_type or ""
        if mime and mime not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {mime}；仅支持 {sorted(ALLOWED_MIME_TYPES)}",
            )

        # 2) 扩展名兜底
        fname = file.filename or ""
        ext_in_name = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        if ext_in_name and ext_in_name not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件扩展名: {ext_in_name}；仅支持 {sorted(ALLOWED_EXTENSIONS)}",
            )

        # 3) 读内容 + 大小校验
        try:
            content = await file.read()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="读取文件失败") from exc

        if not content:
            raise HTTPException(status_code=400, detail="文件内容为空")

        if len(content) > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"文件过大: {len(content) / 1024 / 1024:.2f}MB "
                    f"> {MAX_IMAGE_SIZE_BYTES / 1024 / 1024:.0f}MB"
                ),
            )

        # 4) 魔数校验（同时覆盖"伪造 MIME / 伪造扩展名"攻击）
        if _detect_image_extension(content) is None:
            raise HTTPException(
                status_code=400,
                detail="文件内容不是有效的图片（魔数校验失败）",
            )

        return content

    # ============================================================
    # 私有：local 存储
    # ============================================================

    async def _store_local(self, object_key: str, content: bytes) -> str:
        """写本地磁盘并返回可访问 URL."""
        base_dir = Path(self.settings.LOCAL_UPLOAD_DIR)
        target = base_dir / object_key
        target.parent.mkdir(parents=True, exist_ok=True)

        # 用普通同步 open：文件 I/O 走内核缓存，Python open 在 async context 下足够快；
        # 如需严格 async 可换成 aiofiles，但这里用内置 os.open + 一次性写入最简洁。
        try:
            with open(target, "wb") as fh:
                fh.write(content)
        except OSError as exc:
            logger.error("[UploadService] 本地写盘失败 path=%s err=%s", target, exc)
            raise HTTPException(status_code=500, detail="本地存储写入失败") from exc

        url_prefix = self.settings.LOCAL_UPLOAD_PUBLIC_URL_PREFIX.rstrip("/")
        return f"{url_prefix}/{object_key}"

    # ============================================================
    # 私有：OSS 存储（alibabacloud-oss-v2 async）
    # ============================================================

    async def _store_oss(
        self,
        object_key: str,
        content: bytes,
        mime: str,
    ) -> str:
        """上传到阿里云 OSS（alibabacloud-oss-v2.aio）."""
        try:
            import alibabacloud_oss_v2.aio as oss_aio  # type: ignore[import-untyped]
            from alibabacloud_oss_v2 import models as oss_models  # type: ignore[import-untyped]
        except ImportError as exc:
            logger.error("[UploadService] alibabacloud-oss-v2 未安装: %s", exc)
            raise HTTPException(
                status_code=500,
                detail="OSS SDK 未安装，请执行 uv add alibabacloud-oss-v2",
            ) from exc

        # OSS V2 配置
        cfg = oss_aio.Config(
            endpoint=self.settings.OSS_ENDPOINT,
            region=self.settings.OSS_REGION,
            credentials_provider=oss_aio.StaticCredentialsProvider(
                access_key_id=self.settings.OSS_ACCESS_KEY_ID,
                access_key_secret=self.settings.OSS_ACCESS_KEY_SECRET,
            ),
        )

        client = oss_aio.Client(cfg)
        try:
            request = oss_models.PutObjectRequest(
                bucket=self.settings.OSS_BUCKET,
                key=object_key,
                content_type=mime,
                body=content,
            )
            await client.put_object(request)
        except Exception as exc:
            logger.error("[UploadService] OSS put_object 失败 bucket=%s key=%s err=%s",
                         self.settings.OSS_BUCKET, object_key, exc)
            raise HTTPException(status_code=500, detail="OSS 上传失败") from exc
        finally:
            try:
                await client.close()
            except Exception:
                pass

        # 拼 URL：优先 OSS_PUBLIC_BASE_URL，否则按 endpoint + bucket 合成
        if self.settings.OSS_PUBLIC_BASE_URL:
            base = self.settings.OSS_PUBLIC_BASE_URL.rstrip("/")
            url = f"{base}/{object_key}"
        else:
            url = f"https://{self.settings.OSS_BUCKET}.{self.settings.OSS_ENDPOINT}/{object_key}"

        return url
