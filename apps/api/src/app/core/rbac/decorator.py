"""
RBAC 权限装饰器模块 - FastAPI 兼容版本

提供两个核心装饰器：
1. require_permissions - 基于权限码的访问控制
2. require_roles - 基于角色的访问控制

使用示例:
    from app.core.rbac import require_permissions, require_roles

    # 示例1: 要求单个权限
    @router.post("/users")
    @require_permissions("user:create")
    async def create_user(...):
        pass

    # 示例2: 要求多个权限（全部满足）
    @router.delete("/users/{id}")
    @require_permissions("user:delete", "user:read", require_all=True)
    async def delete_user(...):
        pass

    # 示例3: 要求多个权限（满足其一即可）
    @router.get("/admin/settings")
    @require_permissions("admin:config", "super:manage", require_all=False)
    async def admin_settings(...):
        pass

    # 示例4: 要求角色
    @router.get("/admin/dashboard")
    @require_roles("admin", "super_admin")
    async def dashboard(...):
        pass

工作原理:
    1. 装饰器在请求处理前拦截
    2. 通过 FastAPI Depends 注入依赖（db, current_user, redis_client）
    3. 从 ContextVar 获取当前用户信息
    4. 调用 checker 模块检查权限/角色
    5. 通过则继续执行原函数，否则抛出 PermissionException(403)
"""

import functools
import logging
from typing import List, Optional, Union
from inspect import Parameter, signature

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionException
from app.core.database import get_session
from app.deps.auth import get_current_user, get_redis_client
from .checker import check_permissions, check_roles

logger = logging.getLogger(__name__)


def require_permissions(
    *permission_codes: str,
    require_all: bool = True
):
    """
    权限检查装饰器（基于权限码）- FastAPI 兼容版本
    
    Args:
        *permission_codes: 一个或多个权限码字符串
            - 'user:create' 创建用户
            - 'class:read' 查看课程
            - 'booking:create' 创建预约
            
        require_all: 权限匹配模式
            - True (默认): AND 逻辑，必须拥有所有列出的权限
            - False: OR 逻辑，拥有其中任一权限即可
            
    Returns:
        装饰器函数（可直接用于路由）
        
    Raises:
        PermissionException(403): 当用户没有所需权限时
        
    使用示例:
        # 场景1: 需要单个权限
        @router.post("/users")
        @require_permissions("user:create")
        async def create_user(...):
            pass
        
        # 场景2: 需要多个权限（AND）
        @router.put("/users/{id}")
        @require_permissions("user:delete", "user:read", require_all=True)
        async def delete_user(...):
            pass
            
        # 场景3: 需要多个权限（OR）
        @router.get("/admin/settings")
        @require_permissions("admin:config", "super:manage", require_all=False)
        async def admin_settings(...):
            pass
    """
    required_perms = list(permission_codes)
    
    if not required_perms:
        raise ValueError("至少需要提供一个权限码")
    
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                db = kwargs.get('db')
                current_user = kwargs.get('current_user')
                redis_client = kwargs.get('redis_client')
                
                user_id = current_user.get("user_id") if current_user else None
                tenant_id = current_user.get("tenant_id") if current_user else None
                
                if not user_id or not tenant_id:
                    logger.error(f"[RBAC] Token 中缺少 user_id 或 tenant_id: {current_user}")
                    raise PermissionException("用户身份信息不完整")
                
                logger.debug(
                    f"[RBAC] 正在检查权限: user={user_id}, tenant={tenant_id}, "
                    f"required={required_perms}, mode={'AND' if require_all else 'OR'}"
                )
                
                has_permission = await check_permissions(
                    db_session=db,
                    required_permissions=required_perms,
                    require_all=require_all,
                    redis_client=redis_client,
                    user_id=user_id,
                    tenant_id=tenant_id,
                )
                
                if not has_permission:
                    perms_str = ", ".join(required_perms)
                    mode_str = "所有" if require_all else "任一"
                    logger.warning(
                        f"[RBAC] ❌ 权限拒绝: user={user_id} 缺少权限 [{perms_str}] (需要{mode_str})"
                    )
                    raise PermissionException(
                        f"权限不足，需要 {mode_str} 权限: {perms_str}"
                    )
                
                logger.debug(f"[RBAC] ✅ 权限通过: user={user_id}")
                return await func(*args, **kwargs)
                
            except PermissionException:
                raise
                
            except Exception as e:
                logger.error(f"[RBAC] 权限检查异常: {type(e).__name__}: {e}")
                raise PermissionException("权限验证失败，请联系管理员")
        
        return wrapper
    
    return decorator


def require_roles(
    *role_codes: str,
    require_all: bool = False
):
    """
    角色检查装饰器（基于角色代码）- FastAPI 兼容版本
    
    与 require_permissions 的区别：
    - permissions 是细粒度的操作权限（如 user:create）
    - roles 是粗粒度的身份标签（如 admin, teacher, student）
    - 通常用于快速判断用户类型，而非具体操作能力
    
    Args:
        *role_codes: 一个或多个角色代码字符串
            - 'admin' 管理员
            - 'teacher' 教师
            - 'student' 学生
            - 'super_admin' 超级管理员
            
        require_all: 角色匹配模式
            - False (默认): OR 逻辑，拥有其中一个角色即可
            - True: AND 逻辑，必须拥有所有角色（较少使用）
            
    Returns:
        装饰器函数（可直接用于路由）
        
    Raises:
        PermissionException(403): 当用户没有所需角色时
        
    使用示例:
        # 场景1: 只有管理员能访问
        @router.get("/admin/dashboard")
        @require_roles("admin")
        async def admin_dashboard(...):
            pass
        
        # 场景2: 管理员或超级管理员都能访问
        @router.get("/admin/settings")
        @require_roles("admin", "super_admin")
        async def admin_settings(...):
            pass
            
        # 场景3: 必须同时是教师和班主任（AND）
        @router.get("/teacher/grade-management")
        @require_roles("teacher", "head_teacher", require_all=True)
        async def grade_management(...):
            pass
    """
    required_roles_list = list(role_codes)
    
    if not required_roles_list:
        raise ValueError("至少需要提供一个角色代码")
    
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                db = kwargs.get('db')
                current_user = kwargs.get('current_user')
                redis_client = kwargs.get('redis_client')
                
                user_id = current_user.get("user_id") if current_user else None
                tenant_id = current_user.get("tenant_id") if current_user else None
                
                if not user_id or not tenant_id:
                    logger.error(f"[RBAC] Token 中缺少 user_id 或 tenant_id: {current_user}")
                    raise PermissionException("用户身份信息不完整")
                
                logger.debug(
                    f"[RBAC] 正在检查角色: user={user_id}, tenant={tenant_id}, "
                    f"required={required_roles_list}, mode={'AND' if require_all else 'OR'}"
                )
                
                has_role = await check_roles(
                    db_session=db,
                    required_role_codes=required_roles_list,
                    require_all=require_all,
                    redis_client=redis_client,
                    user_id=user_id,
                    tenant_id=tenant_id,
                )
                
                if not has_role:
                    roles_str = ", ".join(required_roles_list)
                    mode_str = "所有" if require_all else "任一"
                    logger.warning(
                        f"[RBAC] ❌ 角色拒绝: user={user_id} 缺少角色 [{roles_str}] (需要{mode_str})"
                    )
                    raise PermissionException(
                        f"权限不足，需要{mode_str}角色: {roles_str}"
                    )
                
                logger.debug(f"[RBAC] ✅ 角色通过: user={user_id}")
                return await func(*args, **kwargs)
                
            except PermissionException:
                raise
                
            except Exception as e:
                logger.error(f"[RBAC] 角色检查异常: {type(e).__name__}: {e}")
                raise PermissionException("权限验证失败，请联系管理员")
        
        return wrapper
    
    return decorator