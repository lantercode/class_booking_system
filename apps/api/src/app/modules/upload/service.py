"""
Upload Service - 文件上传核心业务逻辑层

职责：
- 四关校验：类型白名单 + 实际解码（Pillow）+ 按 biz_type 的大小上限 + biz_type 枚举
- 生成 object_key（含 tenant_id 前缀）
- 策略模式分发：local 本地存储 / OSS 云端存储
- 写 file_objects 审计表 + 提交事务
- 拼装可访问 URL

边界：
- 本 Service 不持有核心业务规则，仅封装存储与审计。
- 业务表（users.avatar_url / courses.cover_url）由调用方自行落库，
  调用方应只存 object_key，完整 URL 由 Service 层统一拼装。
"""

import logging
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    BusinessException,
    NotFoundException,
    PermissionException,
    ValidationException,
)
from app.core.oss_client import get_oss_client, resolve_object_url
from app.core.tenant_context import get_tenant_id
from app.modules.upload.image_probe import ImageInfo, ImageValidationError, probe_image
from app.modules.upload.repository import FileObjectRepository
from app.modules.upload.schemas import UploadImageResponse
from app.modules.upload.video_transcode import ensure_playable_h264

logger = logging.getLogger(__name__)

# ============================================================
# 常量
# ============================================================

# 图片 MIME / 扩展名白名单
ALLOWED_IMAGE_MIMES: Final[set[str]] = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_IMAGE_EXTS: Final[set[str]] = {"jpg", "jpeg", "png", "webp"}

# 视频 MIME / 扩展名白名单（小程序原生支持 mp4/webm/mov）
ALLOWED_VIDEO_MIMES: Final[set[str]] = {"video/mp4", "video/webm", "video/quicktime"}
ALLOWED_VIDEO_EXTS: Final[set[str]] = {"mp4", "webm", "mov"}

ALLOWED_BIZ_TYPES: Final[set[str]] = {
    "avatar",
    "course_cover",
    "classroom_cover",
    "banner",
    "video_cover",
    "video",
    "notice",
}

# 各业务场景的大小上限（字节）
MAX_SIZE_BY_BIZ: Final[dict[str, int]] = {
    "avatar": 5 * 1024 * 1024,
    "course_cover": 5 * 1024 * 1024,
    "classroom_cover": 5 * 1024 * 1024,
    "banner": 5 * 1024 * 1024,
    "video_cover": 5 * 1024 * 1024,
    "video": 200 * 1024 * 1024,
    "notice": 5 * 1024 * 1024,
}

# 需要按视频规则校验（跳过 Pillow 解码）的 biz_type
VIDEO_BIZ_TYPES: Final[frozenset[str]] = frozenset({"video"})

# object_key 中禁止出现的片段（防路径穿越，避免预签名越出本租户命名空间）
_INVALID_KEY_FRAGMENTS: Final[tuple[str, ...]] = ("..", "\\")


def _strip_storage_url(value: str, settings: Settings) -> str | None:
    """若 value 是本系统存储地址，剥离前缀还原为 object_key；否则返回 None。

    支持两种历史/展示形态：
    - 本地静态路径：``/uploads/t/1/avatar/x.png``
    - 本桶 OSS 地址（预签名或被 CDN 包装）：``https://{bucket}.{endpoint}/t/1/avatar/x.png?...``
    """
    prefix = settings.LOCAL_UPLOAD_PUBLIC_URL_PREFIX.rstrip("/")
    if prefix and value.startswith(f"{prefix}/"):
        return value[len(prefix) + 1 :]

    if not value.lower().startswith(("http://", "https://")):
        return None

    try:
        parsed = urlsplit(value)
    except ValueError:
        return None

    path = parsed.path.lstrip("/")
    if not path:
        return None

    if settings.STORAGE_BACKEND == "oss" and settings.OSS_BUCKET and settings.OSS_ENDPOINT:
        expected_host = f"{settings.OSS_BUCKET}.{settings.OSS_ENDPOINT}".lower()
        if parsed.netloc.lower() == expected_host:
            return path

    if prefix and f"{prefix}/" in f"/{path}":
        return path.split(f"{prefix}/", 1)[1]
    return None


def normalize_object_key(
    value: str | None,
    biz_types: Iterable[str],
    *,
    allow_external_url: bool = False,
    field_name: str = "图片地址",
) -> str | None:
    """校验并归一化业务表图片字段（object_key 语义），供各业务 Service 复用。

    - 只接受本租户命名空间下的 ``t/{tenant_id}/{biz_type}/...`` key
    - 同时接受本系统签发的等价 URL（本地 ``/uploads/...`` 或本桶 OSS URL），
      自动剥离前缀还原为 object_key，保证前端回传展示值不会污染入库数据
    - ``allow_external_url=True`` 时额外允许 http(s) 外部链接（课程封面）
    - 空字符串视为「清空」，返回 None

    Raises:
        ValidationException: 跨租户 key / 非预期 biz_type / 路径穿越 / 非白名单外部链接
    """
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None

    tenant_id = get_tenant_id()
    if not tenant_id:
        raise ValidationException("租户上下文缺失，无法校验图片地址")

    settings = get_settings()
    prefixes = tuple(f"t/{tenant_id}/{biz}/" for biz in biz_types)

    candidates = [cleaned]
    stripped = _strip_storage_url(cleaned, settings)
    if stripped and stripped != cleaned:
        candidates.append(stripped)

    for candidate in candidates:
        if not candidate.startswith(prefixes):
            continue
        if any(fragment in candidate for fragment in _INVALID_KEY_FRAGMENTS):
            raise ValidationException(f"{field_name}格式非法")
        return candidate

    if allow_external_url and cleaned.lower().startswith(("http://", "https://")):
        return cleaned

    allowed_hint = "，或 http(s) 外部链接" if allow_external_url else ""
    raise ValidationException(f"{field_name}必须是本租户上传的文件{allowed_hint}")


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

        content, ext = await self._validate_and_read(file, biz_type)
        mime = file.content_type or "application/octet-stream"

        # 视频场景：统一规整为 H.264，避免 HEVC/H.265 在小程序端无法播放
        if biz_type in VIDEO_BIZ_TYPES:
            content, ext, mime = await ensure_playable_h264(content, ext, mime)

        # --- 生成 object_key ---
        tenant_id = get_tenant_id()
        if not tenant_id:
            raise HTTPException(status_code=500, detail="租户上下文缺失，无法生成 object_key")

        object_key = f"t/{tenant_id}/{biz_type}/{uuid.uuid4().hex}.{ext}"

        # --- 存储：策略模式 ---
        try:
            if self.settings.STORAGE_BACKEND == "local":
                await self._store_local(object_key, content)
            elif self.settings.STORAGE_BACKEND == "oss":
                await self._store_oss(object_key, content, mime)
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
            # 补偿：审计失败则回删已落存储的对象，避免产生无元数据的孤儿文件
            await self._delete_storage_quietly(object_key)
            raise HTTPException(status_code=500, detail="文件元数据记录失败") from exc

        # --- 生成访问 URL（local=静态路径；oss=预签名，私有桶必需）---
        try:
            url = await resolve_object_url(object_key, settings=self.settings)
        except Exception as exc:
            logger.error("[UploadService] 生成访问 URL 失败 key=%s err=%s", object_key, exc)
            raise HTTPException(status_code=500, detail="生成文件访问地址失败") from exc

        return UploadImageResponse(
            object_key=object_key,
            url=url,
            mime=mime,
            size=len(content),
            biz_type=biz_type,
        )

    async def delete_object(
        self,
        object_key: str,
        *,
        requester_id: int | None = None,
        is_admin: bool = False,
    ) -> None:
        """删除对象（软删审计记录 + 删除存储实体）。

        保护规则：
        - 只能删除本租户命名空间 ``t/{tenant_id}/`` 下的对象（由 Router 预校验）
        - 非管理员只能删除自己上传的文件
        - 仍被业务表（头像/课程封面/教室封面/分类图标）引用时拒绝删除（409）

        存储删除为尽力而为：软删已提交后存储删除失败只记日志，避免把已删除的
        元数据回滚造成更大不一致；残留对象可由后续 OSS 生命周期规则清理。

        Raises:
            NotFoundException: 审计记录不存在（含已删除）
            PermissionException: 非本人文件且非管理员
            BusinessException: 文件仍被业务引用（code=409）
            HTTPException: 元数据提交失败（500）
        """
        record = await self.repo.get_by_object_key(self.db, object_key)
        if record is None:
            raise NotFoundException("文件不存在或已删除")

        if not is_admin and record.uploader_id != requester_id:
            raise PermissionException("只能删除自己上传的文件")

        ref_count = await self.repo.count_references(self.db, object_key)
        if ref_count > 0:
            raise BusinessException(
                f"该文件仍被 {ref_count} 处业务数据引用，请先解除引用后再删除",
                code=409,
            )

        record.deleted_at = datetime.now(UTC)
        try:
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            logger.error("[UploadService] 软删除失败 key=%s err=%s", object_key, exc, exc_info=True)
            raise HTTPException(status_code=500, detail="删除文件元数据失败") from exc

        await self._delete_storage_quietly(object_key)

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

    async def _validate_and_read(self, file: UploadFile, biz_type: str) -> tuple[bytes, str]:
        """校验 MIME / 扩展名 / 大小，并一次性读取内容。

        Returns:
            (文件内容, 扩展名)
            - 图片场景：Pillow 解码后的可信扩展名
            - 视频场景：直接用文件扩展名（跳过 Pillow 解码）
        """
        is_video = biz_type in VIDEO_BIZ_TYPES
        allowed_mimes = ALLOWED_VIDEO_MIMES if is_video else ALLOWED_IMAGE_MIMES
        allowed_exts = ALLOWED_VIDEO_EXTS if is_video else ALLOWED_IMAGE_EXTS

        # 1) MIME 白名单（客户端声明，仅作早期快速拒绝）
        mime = file.content_type or ""
        if mime and mime not in allowed_mimes:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {mime}；仅支持 {sorted(allowed_mimes)}",
            )

        # 2) 扩展名兜底
        fname = file.filename or ""
        ext_in_name = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        if ext_in_name and ext_in_name not in allowed_exts:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件扩展名: {ext_in_name}；仅支持 {sorted(allowed_exts)}",
            )

        # 3) 读内容 + 按业务场景的大小上限
        try:
            content = await file.read()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="读取文件失败") from exc

        if not content:
            raise HTTPException(status_code=400, detail="文件内容为空")

        max_size = MAX_SIZE_BY_BIZ[biz_type]
        if len(content) > max_size:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"文件过大: {len(content) / 1024 / 1024:.2f}MB "
                    f"> {max_size / 1024 / 1024:.0f}MB（{biz_type} 场景上限）"
                ),
            )

        # 视频场景直接用扩展名，跳过 Pillow 解码
        if is_video:
            ext = ext_in_name or "mp4"
            return content, ext

        # 图片场景：Pillow 解码校验
        try:
            image = probe_image(content)
        except ImageValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return content, image.extension

    # ============================================================
    # 私有：local 存储
    # ============================================================

    async def _store_local(self, object_key: str, content: bytes) -> None:
        """写本地磁盘（访问 URL 统一由 resolve_object_url 生成）."""
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

    # ============================================================
    # 私有：OSS 存储（alibabacloud-oss-v2 async）
    # ============================================================

    async def _store_oss(
        self,
        object_key: str,
        content: bytes,
        mime: str,
    ) -> None:
        """上传到阿里云 OSS（客户端单例由 core.oss_client 统一管理）."""
        import alibabacloud_oss_v2 as oss  # type: ignore[import-untyped]

        client = await get_oss_client(self.settings)
        request = oss.models.PutObjectRequest(
            bucket=self.settings.OSS_BUCKET,
            key=object_key,
            content_type=mime,
            body=content,
        )
        try:
            await client.put_object(request)
        except Exception as exc:
            logger.error(
                "[UploadService] OSS put_object 失败 bucket=%s key=%s err=%s",
                self.settings.OSS_BUCKET,
                object_key,
                exc,
            )
            raise HTTPException(status_code=500, detail="OSS 上传失败") from exc

    # ============================================================
    # 私有：存储删除（补偿 / 删除接口共用，尽力而为）
    # ============================================================

    async def _delete_storage_quietly(self, object_key: str) -> None:
        """删除存储实体，失败只记日志（不向上抛，避免掩盖主流程结果）。"""
        try:
            if self.settings.STORAGE_BACKEND == "local":
                target = Path(self.settings.LOCAL_UPLOAD_DIR) / object_key
                target.unlink(missing_ok=True)
            elif self.settings.STORAGE_BACKEND == "oss":
                import alibabacloud_oss_v2 as oss  # type: ignore[import-untyped]

                client = await get_oss_client(self.settings)
                await client.delete_object(
                    oss.models.DeleteObjectRequest(
                        bucket=self.settings.OSS_BUCKET,
                        key=object_key,
                    )
                )
            else:
                logger.warning(
                    "[UploadService] 未知 STORAGE_BACKEND=%s，跳过实体删除 key=%s",
                    self.settings.STORAGE_BACKEND,
                    object_key,
                )
        except Exception as exc:  # noqa: BLE001 - 删除失败不应影响主流程
            logger.error(
                "[UploadService] 存储实体删除失败 key=%s err=%s",
                object_key,
                exc,
                exc_info=True,
            )
