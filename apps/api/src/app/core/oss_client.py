"""阿里云 OSS 异步客户端（单例）+ 凭证提供器 + 预签名工具。

设计要点：
- 全局复用单个 AsyncClient，避免每次上传/签名都重建连接与会话
- 凭证模式二选一（config.OSS_CREDENTIALS_MODE）：
  * static   : OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET，适用于本地开发与 CI
  * ecs_role : ECS 实例 RAM 角色，由 alibabacloud-credentials 从实例元数据服务
               获取 STS 临时凭证并在到期前自动刷新，AK/SK 不落盘
- Bucket 开启「阻止公共访问」时对外只暴露预签名 URL，不生成裸 URL
"""

from __future__ import annotations

import asyncio
import datetime
import logging

import alibabacloud_oss_v2 as oss
import alibabacloud_oss_v2.aio as oss_aio
from alibabacloud_oss_v2 import Credentials, CredentialsProvider

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# OSS 预签名 URL 最长有效期为 7 天（服务端限制）
OSS_PRESIGN_EXPIRES_SECONDS = 7 * 24 * 3600

_client: oss_aio.AsyncClient | None = None
_client_lock = asyncio.Lock()


class EcsRoleCredentialsProvider(CredentialsProvider):
    """ECS 实例 RAM 角色凭证提供器。

    底层 ``alibabacloud_credentials`` 会：
    - 通过实例元数据服务（100.100.100.200）获取 STS 临时凭证
    - 缓存凭证并在到期前自动刷新
    - 兼容 IMDSv2（可配置 enable_imds_v2）

    注意：``get_credentials`` 由 OSS SDK 在请求链路中同步调用，首次取凭证
    会发起一次元数据服务 HTTP 请求（通常 < 100ms），之后走缓存。
    """

    def __init__(self, role_name: str, timeout: int = 5) -> None:
        from alibabacloud_credentials.client import Client as CredentialClient
        from alibabacloud_credentials.models import Config as CredentialConfig

        self._client = CredentialClient(
            CredentialConfig(type="ecs_ram_role", role_name=role_name, timeout=timeout)
        )

    def get_credentials(self) -> Credentials:
        cred = self._client.get_credential()
        if not cred or not cred.access_key_id:
            raise RuntimeError(
                "未能从 ECS 实例元数据获取 RAM 角色临时凭证，"
                "请确认实例已绑定角色且角色名与 OSS_ROLE_NAME 一致"
            )
        return Credentials(
            access_key_id=cred.access_key_id,
            access_key_secret=cred.access_key_secret,
            security_token=getattr(cred, "security_token", None),
        )


def _build_credentials_provider(settings: Settings) -> CredentialsProvider:
    """按凭证模式构造 OSS 凭证提供器。"""
    if settings.OSS_CREDENTIALS_MODE == "ecs_role":
        logger.info("[OSS] 凭证模式=ecs_role, 角色=%s", settings.OSS_ROLE_NAME)
        return EcsRoleCredentialsProvider(settings.OSS_ROLE_NAME)

    logger.info("[OSS] 凭证模式=static")
    return oss.credentials.StaticCredentialsProvider(
        access_key_id=settings.OSS_ACCESS_KEY_ID,
        access_key_secret=settings.OSS_ACCESS_KEY_SECRET,
    )


def _build_client(settings: Settings) -> oss_aio.AsyncClient:
    cfg = oss.Config(
        region=settings.OSS_REGION,
        endpoint=settings.OSS_ENDPOINT,
        credentials_provider=_build_credentials_provider(settings),
        connect_timeout=10,
        readwrite_timeout=30,
    )
    return oss_aio.AsyncClient(cfg)


async def get_oss_client(settings: Settings | None = None) -> oss_aio.AsyncClient:
    """获取 OSS AsyncClient 单例（懒加载，并发安全）。"""
    global _client
    if _client is not None:
        return _client
    async with _client_lock:
        if _client is None:
            _client = _build_client(settings or get_settings())
        return _client


async def close_oss_client() -> None:
    """应用关闭时释放连接池。"""
    global _client
    if _client is None:
        return
    try:
        await _client.close()
    except Exception as exc:  # noqa: BLE001 - 关闭失败不应影响进程退出
        logger.warning("[OSS] 关闭客户端失败: %s", exc)
    finally:
        _client = None


async def presign_object_url(
    object_key: str,
    expires_seconds: int = OSS_PRESIGN_EXPIRES_SECONDS,
    settings: Settings | None = None,
) -> str:
    """为私有 Bucket 中的对象签发临时 GET URL。"""
    settings = settings or get_settings()
    client = await get_oss_client(settings)
    request = oss.models.GetObjectRequest(bucket=settings.OSS_BUCKET, key=object_key)
    result = await client.presign(
        request, expires=datetime.timedelta(seconds=expires_seconds)
    )
    return result.url


def local_object_url(object_key: str, settings: Settings | None = None) -> str:
    """本地存储对象的相对访问路径。"""
    settings = settings or get_settings()
    if object_key.startswith("http://") or object_key.startswith("https://"):
        return object_key
    if object_key.startswith("/"):
        return object_key
    prefix = settings.LOCAL_UPLOAD_PUBLIC_URL_PREFIX.rstrip("/")
    return f"{prefix}/{object_key}"


async def resolve_object_url(
    object_key: str,
    expires_seconds: int = OSS_PRESIGN_EXPIRES_SECONDS,
    settings: Settings | None = None,
) -> str:
    """object_key → 前端可直接访问的 URL。

    - local：`/uploads/{key}`
    - oss  ：预签名 URL（私有 Bucket 必需）
    - 已经是完整 URL 或绝对路径：原样返回（兼容历史数据）
    """
    settings = settings or get_settings()
    if object_key.startswith("http://") or object_key.startswith("https://"):
        return object_key
    if object_key.startswith("/"):
        return object_key
    if settings.STORAGE_BACKEND == "oss":
        return await presign_object_url(object_key, expires_seconds, settings)
    return local_object_url(object_key, settings)


__all__ = [
    "OSS_PRESIGN_EXPIRES_SECONDS",
    "EcsRoleCredentialsProvider",
    "get_oss_client",
    "close_oss_client",
    "presign_object_url",
    "local_object_url",
    "resolve_object_url",
]
