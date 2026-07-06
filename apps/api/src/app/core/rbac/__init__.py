"""
RBAC (基于角色的访问控制) 权限系统

提供细粒度的权限控制装饰器，支持：
- 基于权限码的访问控制 (require_permissions)
- 基于角色的访问控制 (require_roles)
- Redis 缓存优化性能
- 数据库降级保障可用性

使用示例:
    from app.core.rbac import require_permissions, require_roles

    @router.post("/users")
    @require_permissions("user:create")
    async def create_user(...):
        pass

    @router.get("/admin/dashboard")
    @require_roles("admin", "super_admin")
    async def admin_dashboard(...):
        pass
"""

from .decorator import require_permissions, require_roles
from .cache import clear_user_permission_cache

__all__ = [
    "require_permissions",
    "require_roles",
    "clear_user_permission_cache",
]
