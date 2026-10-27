"""Home Config Service - 首页配置业务逻辑层

核心能力：
- draft 自动创建 / 覆盖更新
- publish 原子事务（查询 draft → 计算 max published version → INSERT 新 published 行）
  并发保护：捕获 IntegrityError → 409
- miniapp / admin 读取最新 published
- 已发布版本列表（本次只列不回滚）
"""

import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.tenant_context import get_tenant_id
from app.modules.home_config.models import HomeConfig
from app.modules.home_config.repository import HomeConfigRepository
from app.modules.home_config.schemas import (
    HomeConfigDraftUpdate,
    HomeConfigResponse,
    HomeConfigVersionItem,
)

logger = logging.getLogger(__name__)

DEFAULT_DRAFT_PAYLOAD: dict = {"schema_version": 1, "modules": []}


class HomeConfigService:
    """首页配置业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = HomeConfigRepository()

    async def _get_tenant_id(self) -> int:
        tid = get_tenant_id()
        if not tid:
            raise HTTPException(status_code=400, detail="缺少租户上下文")
        return tid

    # ------------------------------------------------------------
    # DTO 转换
    # ------------------------------------------------------------

    @staticmethod
    def _to_response(orm: HomeConfig) -> HomeConfigResponse:
        return HomeConfigResponse.model_validate(orm)

    # ------------------------------------------------------------
    # 1. get_draft
    # ------------------------------------------------------------

    async def get_draft(self) -> HomeConfigResponse:
        """读取 draft；不存在则自动创建空 draft"""
        draft = await self.repo.get_draft(self.db)
        if draft is None:
            tenant_id = await self._get_tenant_id()
            draft = HomeConfig(
                tenant_id=tenant_id,
                scope="draft",
                version=1,
                payload=DEFAULT_DRAFT_PAYLOAD,
            )
            self.db.add(draft)
            await self.db.flush()
            await self.db.commit()
            await self.db.refresh(draft)
        return self._to_response(draft)

    # ------------------------------------------------------------
    # 2. update_draft
    # ------------------------------------------------------------

    async def update_draft(self, data: HomeConfigDraftUpdate) -> HomeConfigResponse:
        """整体覆盖 draft payload；找不到则新建"""
        tenant_id = await self._get_tenant_id()
        payload = data.payload

        draft = await self.repo.get_draft(self.db)
        if draft is None:
            draft = HomeConfig(
                tenant_id=tenant_id,
                scope="draft",
                version=1,
                payload=payload,
            )
            self.db.add(draft)
        else:
            draft.payload = payload
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(draft)
        return self._to_response(draft)

    # ------------------------------------------------------------
    # 3. publish —— 核心原子事务
    # ------------------------------------------------------------

    async def publish(self, operator_id: int | None = None) -> HomeConfigResponse:
        """把当前 draft 发布为新 published 版本

        同一事务内：
          1. 查 draft
          2. 查当前租户 published 最大 version
          3. INSERT published（version = max+1）
          4. commit

        并发保护：唯一约束冲突 → 409 "有人先发布了，请稍后再试"
        """
        tenant_id = await self._get_tenant_id()

        try:
            # 1. 查 draft（带行锁，避免 publish 与 update_draft 并发时读到半更新状态）
            draft_result = await self.db.execute(
                select(HomeConfig)
                .where(HomeConfig.scope == "draft", HomeConfig.version == 1)
                .with_for_update()
            )
            draft = draft_result.scalar_one_or_none()
            if draft is None:
                raise HTTPException(status_code=400, detail="请先配置首页内容再发布")

            # 2. 查当前最大 published version
            max_ver_result = await self.db.execute(
                select(func.max(HomeConfig.version)).where(HomeConfig.scope == "published")
            )
            max_version = max_ver_result.scalar() or 0
            next_version = int(max_version) + 1

            # 3. INSERT 新 published
            now = datetime.now(UTC)
            published = HomeConfig(
                tenant_id=tenant_id,
                scope="published",
                version=next_version,
                payload=draft.payload,
                published_at=now,
                operator_id=operator_id,
            )
            self.db.add(published)
            await self.db.flush()
            await self.db.commit()
            await self.db.refresh(published)
            return self._to_response(published)

        except IntegrityError as e:
            await self.db.rollback()
            logger.warning(
                "[HomeConfigService] publish IntegrityError (并发冲突): %s", e
            )
            raise HTTPException(status_code=409, detail="有人先发布了，请稍后再试")

        except HTTPException:
            await self.db.rollback()
            raise

        except Exception:
            await self.db.rollback()
            raise

    # ------------------------------------------------------------
    # 媒体 URL 解析
    # ------------------------------------------------------------

    @staticmethod
    def _build_media_url(object_key: str) -> str:
        """object_key → 完整可访问 URL（local 走 StaticFiles 前缀，oss 走公网域名）"""
        if object_key.startswith("http://") or object_key.startswith("https://"):
            return object_key
        if object_key.startswith("/"):
            return object_key
        settings = get_settings()
        if settings.STORAGE_BACKEND == "oss":
            if settings.OSS_PUBLIC_BASE_URL:
                base = settings.OSS_PUBLIC_BASE_URL.rstrip("/")
            else:
                host = (
                    settings.OSS_ENDPOINT.replace("https://", "")
                    .replace("http://", "")
                    .rstrip("/")
                )
                base = f"https://{settings.OSS_BUCKET}.{host}"
            return f"{base}/{object_key}"
        return f"{settings.LOCAL_UPLOAD_PUBLIC_URL_PREFIX.rstrip('/')}/{object_key}"

    @classmethod
    def _resolve_media_urls(cls, value):
        """递归把 payload 中的 image_key / cover_key 由 object_key 换成完整 URL

        冻结约定（solution-design.md L565/L597）：published 返回给小程序的内容
        必须是可以直接渲染的完整 URL，小程序不关心存储细节。
        draft 不做转换，管理端编辑时仍使用原始 object_key。
        """
        if isinstance(value, dict):
            resolved = {}
            for k, v in value.items():
                if k in ("image_key", "cover_key") and isinstance(v, str) and v:
                    resolved[k] = cls._build_media_url(v)
                else:
                    resolved[k] = cls._resolve_media_urls(v)
            return resolved
        if isinstance(value, list):
            return [cls._resolve_media_urls(v) for v in value]
        return value

    # ------------------------------------------------------------
    # 4. get_published_for_miniapp
    # ------------------------------------------------------------

    async def get_published_for_miniapp(self) -> HomeConfigResponse:
        """给小程序/管理端读取最新 published（媒体字段已解析为完整 URL）"""
        published = await self.repo.get_latest_published(self.db)
        if published is None:
            raise HTTPException(status_code=404, detail="首页尚未发布")
        response = self._to_response(published)
        response.payload = self._resolve_media_urls(response.payload)
        return response

    # ------------------------------------------------------------
    # 5. list_published_versions
    # ------------------------------------------------------------

    async def list_published_versions(self) -> list[HomeConfigVersionItem]:
        """列出所有已发布版本（version 降序），本次只列不回滚"""
        items = await self.repo.list_published_versions(self.db)
        return [
            HomeConfigVersionItem(
                id=it.id,
                version=it.version,
                published_at=it.published_at,
                operator_id=it.operator_id,
                created_at=it.created_at,
            )
            for it in items
        ]
