"""
管理后台模块

提供用户管理、角色管理、权限查看等管理功能。
所有接口都需要相应的权限或角色才能访问。

RBAC 权限使用示例:
    from app.core.rbac import require_permissions, require_roles

    # 基于权限的细粒度控制
    @require_permissions("user:create")
    
    # 基于角色的快速判断
    @require_roles("admin")
    
    # 组合使用（双重验证）
    @require_roles("teacher")
    @require_permissions("grade:input")
"""
