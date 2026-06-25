from contextvars import ContextVar
from typing import Optional

tenant_id = ContextVar("tenant_id", default=None)
user_id = ContextVar("user_id", default=None)
role_id = ContextVar("role_id", default=None)

def get_tenant_id() -> Optional[int]:
    """
        获取当前租户 ID

        Returns:
            当前租户 ID（如果存在），否则返回 None
    """
    return tenant_id.get()

def get_user_id() -> Optional[int]:
    """
        获取当前用户 ID

        Returns:
            当前用户 ID（如果存在），否则返回 None
    """
    return user_id.get()

def get_role_id() -> Optional[int]:
    """
        获取当前角色 ID

        Returns:
            当前角色 ID（如果存在），否则返回 None
    """
    return role_id.get()

def set_tenant_id(value: int) -> None:
    """
        设置当前租户 ID

        Args:
            tenant_id: 要设置的租户 ID
    """
    tenant_id.set(value)

def set_user_id(value: int) -> None:

    """
        设置当前用户 ID

        Args:
            user_id: 要设置的用户 ID
    """
    user_id.set(value)

def set_role_id(value: str) -> None:

    """
        设置当前角色 ID

        Args:
            role_id: 要设置的角色 ID
    """
    role_id.set(value)
