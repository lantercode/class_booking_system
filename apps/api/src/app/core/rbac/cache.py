"""
RBAC 权限缓存管理模块

功能：
- 使用 Redis 缓存用户权限列表，提升性能
- 支持主动清除缓存（权限变更时）
- 自动过期机制（TTL 5分钟）
- Redis 不可用时降级到数据库查询

技术细节：
- 使用 Redis Set 存储权限码集合
- Key 格式: perms:{tenant_id}:{user_id}
- TTL: 300 秒（5分钟）
- 操作复杂度: O(1) 成员检查
"""

import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# 缓存配置常量
CACHE_PREFIX = "perms"  # Redis Key 前缀
CACHE_TTL_SECONDS = 300  # 缓存过期时间（5分钟）


def get_cache_key(tenant_id: int, user_id: int) -> str:
    """
    生成用户权限缓存的 Redis Key
    
    Args:
        tenant_id: 租户ID
        user_id: 用户ID
        
    Returns:
        Redis Key 字符串，格式: perms:{tenant_id}:{user_id}
        
    示例:
        >>> get_cache_key(10, 1001)
        'perms:10:1001'
    """
    return f"{CACHE_PREFIX}:{tenant_id}:{user_id}"


async def get_cached_permissions(
    redis_client,
    tenant_id: int,
    user_id: int
) -> Optional[List[str]]:
    """
    从 Redis 获取用户的缓存权限列表
    
    Args:
        redis_client: Redis 异步客户端实例
        tenant_id: 租户ID
        user_id: 用户ID
        
    Returns:
        权限码列表（如 ['booking:create', 'class:read']）
        如果缓存未命中或 Redis 不可用，返回 None
        
    性能:
        - 时间复杂度: O(1) （Redis SMEMBERS 操作）
        - 耗时: < 1ms（局域网 Redis）
    """
    if not redis_client:
        logger.debug("[RBAC Cache] Redis 客户端不可用，跳过缓存")
        return None
    
    cache_key = get_cache_key(tenant_id, user_id)
    
    try:
        # 使用 SMEMBERS 获取 Set 中所有成员（权限码）
        cached_perms = await redis_client.smembers(cache_key)
        
        if cached_perms:
            logger.debug(f"[RBAC Cache] 缓存命中: {cache_key}, {len(cached_perms)} 个权限")
            return list(cached_perms)  # 转换为 list 返回
        else:
            logger.debug(f"[RBAC Cache] 缓存未命中: {cache_key}")
            return None
            
    except Exception as e:
        # Redis 操作失败时记录日志但不抛异常（支持降级）
        logger.warning(f"[RBAC Cache] Redis 读取失败: {type(e).__name__}: {e}")
        return None


async def set_cached_permissions(
    redis_client,
    tenant_id: int,
    user_id: int,
    permissions: List[str]
) -> bool:
    """
    将用户权限列表写入 Redis 缓存
    
    Args:
        redis_client: Redis 异步客户端实例
        tenant_id: 租户ID
        user_id: 用户ID
        permissions: 权限码列表
        
    Returns:
        True 表示写入成功，False 表示失败
        
    注意:
        - 使用 SADD 批量添加权限码到 Set
        - 设置 EXPIRE 自动过期（TTL）
        - 如果权限列表为空，不写入缓存（避免缓存空结果）
    """
    if not redis_client or not permissions:
        logger.debug("[RBAC Cache] 跳过写入：Redis不可用或权限列表为空")
        return False
    
    cache_key = get_cache_key(tenant_id, user_id)
    
    try:
        # 使用 Pipeline 减少网络往返（原子操作）
        pipe = redis_client.pipeline()
        
        # 删除旧缓存（如果存在）
        pipe.delete(cache_key)
        
        # 添加新的权限码到 Set
        pipe.sadd(cache_key, *permissions)
        
        # 设置过期时间
        pipe.expire(cache_key, CACHE_TTL_SECONDS)
        
        # 执行 Pipeline
        await pipe.execute()
        
        logger.debug(
            f"[RBAC Cache] 缓存已写入: {cache_key}, "
            f"{len(permissions)} 个权限, TTL={CACHE_TTL_SECONDS}s"
        )
        return True
        
    except Exception as e:
        logger.error(f"[RBAC Cache] Redis 写入失败: {type(e).__name__}: {e}")
        return False


async def clear_user_permission_cache(
    redis_client,
    tenant_id: int,
    user_id: int
) -> bool:
    """
    清除指定用户的权限缓存（权限变更时调用）
    
    使用场景:
        - 管理员修改用户角色后
        - 管理员修改角色权限后
        - 用户被禁用/启用后
        
    Args:
        redis_client: Redis 异步客户端实例
        tenant_id: 租户ID
        user_id: 用户ID
        
    Returns:
        True 表示清除成功（或缓存不存在），False 表示操作失败
        
    示例:
        >>> await clear_user_permission_cache(redis, 10, 1001)
        True  # 缓存已清除，下次请求会重新从数据库加载
    """
    if not redis_client:
        logger.debug("[RBAC Cache] Redis 客户端不可用，跳过清除")
        return True  # 返回 True 避免阻塞业务逻辑
    
    cache_key = get_cache_key(tenant_id, user_id)
    
    try:
        result = await redis_client.delete(cache_key)
        
        if result:
            logger.info(f"[RBAC Cache] 缓存已清除: {cache_key}")
        else:
            logger.debug(f"[RBAC Cache] 缓存不存在（无需清除）: {cache_key}")
            
        return True
        
    except Exception as e:
        logger.error(f"[RBAC Cache] 清除缓存失败: {type(e).__name__}: {e}")
        return False


async def clear_role_permissions_cache(
    redis_client,
    tenant_id: int,
    role_ids: List[int]
) -> int:
    """
    批量清除拥有指定角色的所有用户的权限缓存
    
    使用场景:
        - 角色的权限定义变更后（如给 admin 角色新增了 user:delete 权限）
        - 需要使该角色下所有用户的缓存失效
        
    ⚠️ 高级功能:
        此操作需要查询数据库获取该角色下的所有用户ID，
        如果用户量很大（>1000），建议使用消息队列异步处理。
    
    Args:
        redis_client: Redis 异步客户端实例
        tenant_id: 租户ID
        role_ids: 角色ID列表
        
    Returns:
        成功清除的用户缓存数量
    """
    # TODO: 实现批量清除逻辑（需要依赖 Repository 层）
    # 这里先提供接口定义，实际实现需要注入 db_session
    logger.info(f"[RBAC Cache] 收到批量清除请求: 角色IDs={role_ids}")
    return 0
