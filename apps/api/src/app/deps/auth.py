import logging

from fastapi import Depends, Header

from app.core.config import get_settings
from app.core.exceptions import AuthException
from app.core.security import decode_token, is_token_blacklisted
from app.core.tenant_context import set_role_id, set_tenant_id, set_user_id

logger = logging.getLogger(__name__)

_redis_client = None


async def get_redis_client():
    global _redis_client

    if _redis_client is None:
        # 延迟初始化，只在第一次调用时创建连接
        try:
            from redis.asyncio import Redis as AsyncRedis

            settings = get_settings()
            # 注意：禁止输出 REDIS_URL（生产环境含密码，见 F1.4 / D-F1.2-1）
            logger.debug("正在连接 Redis...")
            _redis_client = AsyncRedis.from_url(settings.REDIS_URL, decode_responses=True)
            # 测试连接
            await _redis_client.ping()
            logger.debug("Redis 连接测试成功")
        except ImportError:
            raise AuthException("Redis 库未安装，请执行: uv pip install 'redis>=4.0,<5.0'")
        except Exception as e:
            # 不携带 REDIS_URL，避免泄露认证信息
            logger.error(f"Redis 连接失败: {type(e).__name__}: {e}")
            raise AuthException(f"Redis 连接失败: {type(e).__name__} - {e}")

    return _redis_client


async def get_current_user(
    authorization: str | None = Header(None),
    redis_client=Depends(get_redis_client),
):
    """获取当前登录用户信息"""
    # 1. 检查 authorization 是否为空 → raise AuthException("未提供认证信息")
    if not authorization:
        raise AuthException("未提供认证信息")
    # 2. 检查是否以 "Bearer " 开头 → raise AuthException("认证格式错误")
    if not authorization.startswith("Bearer "):
        raise AuthException("认证信息格式错误")
    # 3. 提取 token 字符串 (去掉 "Bearer " 前缀)
    token = authorization[7:]
    # 4. 调用 decode_token(token) 解码
    payload = decode_token(token)
    # 5. 如果返回 None → raise AuthException("Token 已过期或无效")
    if payload is None:
        raise AuthException("Token 已过期或无效")
    # 6. 黑名单校验：登出/吊销的 token 不得建立请求上下文（在 ContextVar 写入之前）
    if await is_token_blacklisted(token, redis_client):
        raise AuthException("Token 已失效，请重新登录")
    # 7. 调用 set_tenant_id(), set_user_id(), set_role_id()
    set_tenant_id(payload.get("tenant_id"))
    set_user_id(payload.get("user_id"))
    set_role_id(payload.get("role_id"))
    # 8. 返回 payload
    return payload


async def get_optional_user(
    authorization: str | None = Header(None),
    redis_client=Depends(get_redis_client),
):
    """
    获取当前登录用户信息可选认证 - 尝试获取当前用户，但不会强制要求登录

    用途：
    - 有些接口登录和不登录都能访问
    - 登录后可以返回个性化数据

    Returns:
        登录时: 返回用户信息字典
        未登录/Token 无效/已吊销时: 返回 None (不抛异常)
    """

    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]
    payload = decode_token(token)
    if payload is None:
        return None

    # 已吊销的 token 按匿名处理（不建立上下文、不抛异常）
    if await is_token_blacklisted(token, redis_client):
        return None

    set_tenant_id(payload.get("tenant_id"))
    set_user_id(payload.get("user_id"))

    return payload
