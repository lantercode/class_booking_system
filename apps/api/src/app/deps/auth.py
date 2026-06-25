from fastapi import Header, Depends
from typing import Optional

from app.core.security import decode_token
from app.core.exceptions import AuthException
from app.core.tenant_context import set_tenant_id, set_user_id, set_role_id

async def get_current_user(authorization: Optional[str] = Header(None)):
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
    # 6. 调用 set_tenant_id(), set_user_id(), set_role_id()
    set_tenant_id(payload.get("tenant_id"))
    set_user_id(payload.get("user_id"))
    set_role_id(payload.get("role_id"))
    # 7. 返回 payload
    return payload

async def get_optional_user(authorization: Optional[str] = Header(None)):
    """
        获取当前登录用户信息可选认证 - 尝试获取当前用户，但不会强制要求登录

        用途：
        - 有些接口登录和不登录都能访问
        - 登录后可以返回个性化数据

        Returns:
            登录时: 返回用户信息字典
            未登录时: 返回 None (不抛异常)
    """

    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]
    payload = decode_token(token)
    if payload is None:
        return None

    set_tenant_id(payload.get("tenant_id"))
    set_user_id(payload.get("user_id"))

    return payload