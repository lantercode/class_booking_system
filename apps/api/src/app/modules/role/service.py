"""
Role Service - 角色权限业务逻辑层

处理角色和权限的核心业务逻辑，包括：
- 角色 CRUD
- 权限查询
- 角色-权限绑定
- 权限缓存管理
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.role.repository import RoleRepository, PermissionRepository
from app.modules.role.schemas import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListResponse,
    PermissionResponse,
    PermissionListResponse,
    AssignPermissionsRequest,
)
from app.modules.auth.models import Role, Permission
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    BusinessException,
)
from app.core.rbac.cache import clear_user_permission_cache

logger = logging.getLogger(__name__)


class RoleService:
    """角色管理服务"""

    def __init__(self):
        self.role_repo = RoleRepository()
        self.permission_repo = PermissionRepository()

    async def create_role(
        self,
        db: AsyncSession,
        data: RoleCreate,
    ) -> RoleResponse:
        """
        创建角色
        
        Args:
            db: 数据库会话
            data: 角色创建数据
        
        Returns:
            角色响应对象
        
        Raises:
            ValidationException: 角色代码已存在
        """
        logger.info(f"[RoleService] 创建角色: code={data.code}")
        
        # 检查角色代码唯一性
        if await self.role_repo.exists_by_code(db, data.code):
            raise ValidationException(f"角色代码 '{data.code}' 已存在")
        
        # 准备角色数据
        role_data: Dict[str, Any] = {
            "code": data.code,
            "name": data.name,
            "description": data.description,
            "is_system": False,  # 用户创建的角色不是系统角色
        }
        
        # 创建角色
        role = await self.role_repo.create(db, role_data)
        
        # 分配权限（如果指定了）
        if data.permission_ids:
            await self.role_repo.assign_permissions(db, role.id, data.permission_ids)
        
        await db.commit()
        await db.refresh(role)
        
        # 获取权限列表
        permissions = await self.permission_repo.get_role_permissions(db, role.id)
        permission_codes = [p.code for p in permissions]
        
        logger.info(f"[RoleService] ✅ 角色创建成功: id={role.id}, code={role.code}")
        
        return RoleResponse(
            id=role.id,
            tenant_id=role.tenant_id,
            code=role.code,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            created_at=role.created_at,
            updated_at=role.updated_at,
            permissions=permission_codes,
        )

    async def update_role(
        self,
        db: AsyncSession,
        role_id: int,
        data: RoleUpdate,
    ) -> RoleResponse:
        """
        更新角色信息
        
        Args:
            db: 数据库会话
            role_id: 角色ID
            data: 更新数据
        
        Returns:
            更新后的角色响应
        
        Raises:
            NotFoundException: 角色不存在
            ValidationException: 不能修改系统角色
        """
        logger.info(f"[RoleService] 更新角色: role_id={role_id}")
        
        # 检查角色是否存在
        role = await self.role_repo.get_by_id(db, role_id)
        if not role:
            raise NotFoundException("角色不存在")
        
        # 检查是否为系统角色
        if role.is_system:
            raise ValidationException("不能修改系统内置角色")
        
        # 准备更新数据
        update_data: Dict[str, Any] = {}
        
        if data.name is not None:
            update_data["name"] = data.name
        if data.description is not None:
            update_data["description"] = data.description
        
        # 执行更新
        if update_data:
            role = await self.role_repo.update(db, role_id, update_data)
        
        await db.commit()
        await db.refresh(role)
        
        # 获取权限列表
        permissions = await self.permission_repo.get_role_permissions(db, role.id)
        permission_codes = [p.code for p in permissions]
        
        logger.info(f"[RoleService] ✅ 角色更新成功: id={role_id}")
        
        return RoleResponse(
            id=role.id,
            tenant_id=role.tenant_id,
            code=role.code,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            created_at=role.created_at,
            updated_at=role.updated_at,
            permissions=permission_codes,
        )

    async def delete_role(
        self,
        db: AsyncSession,
        role_id: int,
        redis_client=None,
    ) -> bool:
        """
        删除角色
        
        Args:
            db: 数据库会话
            role_id: 角色ID
            redis_client: Redis客户端（用于清除权限缓存）
        
        Returns:
            是否删除成功
        
        Raises:
            NotFoundException: 角色不存在
            ValidationException: 不能删除系统角色
        """
        logger.warning(f"[RoleService] 删除角色: role_id={role_id}")
        
        # 检查角色是否存在
        role = await self.role_repo.get_by_id(db, role_id)
        if not role:
            raise NotFoundException("角色不存在")
        
        # 检查是否为系统角色
        if role.is_system:
            raise ValidationException("不能删除系统内置角色")
        
        # 获取所有关联此角色的用户（用于清除缓存）
        from app.modules.auth.models import UserRole
        user_role_query = select(UserRole.user_id).where(UserRole.role_id == role_id)
        user_role_result = await db.execute(user_role_query)
        user_ids = [row[0] for row in user_role_result.all()]
        
        # 删除角色（会自动级联删除 UserRole 和 RolePermission）
        success = await self.role_repo.delete(db, role_id, hard_delete=True)
        
        if success:
            # 清除所有关联用户的权限缓存
            from app.core.tenant_context import get_tenant_id
            tenant_id = get_tenant_id()
            if redis_client and user_ids:
                for user_id in user_ids:
                    await clear_user_permission_cache(redis_client, tenant_id, user_id)
            
            logger.warning(f"[RoleService] ✅ 角色删除成功: id={role_id}")
        
        return success

    async def get_role_by_id(
        self,
        db: AsyncSession,
        role_id: int,
    ) -> RoleResponse:
        """
        获取角色详情
        
        Args:
            db: 数据库会话
            role_id: 角色ID
        
        Returns:
            角色响应
        
        Raises:
            NotFoundException: 角色不存在
        """
        role = await self.role_repo.get_by_id(db, role_id)
        if not role:
            raise NotFoundException("角色不存在")
        
        permissions = await self.permission_repo.get_role_permissions(db, role.id)
        permission_codes = [p.code for p in permissions]
        
        return RoleResponse(
            id=role.id,
            tenant_id=role.tenant_id,
            code=role.code,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            created_at=role.created_at,
            updated_at=role.updated_at,
            permissions=permission_codes,
        )

    async def list_roles(
        self,
        db: AsyncSession,
        *,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> RoleListResponse:
        """
        获取角色列表（分页）
        
        Args:
            db: 数据库会话
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
        
        Returns:
            分页角色列表
        """
        items, total = await self.role_repo.search(
            db,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        
        # 转换为响应对象
        role_responses = []
        for role in items:
            permissions = await self.permission_repo.get_role_permissions(db, role.id)
            permission_codes = [p.code for p in permissions]
            
            role_responses.append(RoleResponse(
                id=role.id,
                tenant_id=role.tenant_id,
                code=role.code,
                name=role.name,
                description=role.description,
                is_system=role.is_system,
                created_at=role.created_at,
                updated_at=role.updated_at,
                permissions=permission_codes,
            ))
        
        return RoleListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=role_responses,
        )

    async def assign_permissions(
        self,
        db: AsyncSession,
        role_id: int,
        permission_ids: List[int],
        redis_client=None,
    ) -> bool:
        """
        为角色分配权限（覆盖式）
        
        Args:
            db: 数据库会话
            role_id: 角色ID
            permission_ids: 权限ID列表
            redis_client: Redis客户端
        
        Returns:
            是否成功
        
        Raises:
            NotFoundException: 角色不存在
            ValidationException: 权限不存在
        """
        logger.info(f"[RoleService] 分配权限: role_id={role_id}, permission_ids={permission_ids}")
        
        # 检查角色是否存在
        role = await self.role_repo.get_by_id(db, role_id)
        if not role:
            raise NotFoundException("角色不存在")
        
        # 检查是否为系统角色
        if role.is_system:
            raise ValidationException("不能修改系统内置角色的权限")
        
        # 验证权限ID是否有效
        for permission_id in permission_ids:
            if not await self.permission_repo.exists(db, permission_id):
                raise ValidationException(f"权限ID {permission_id} 不存在")
        
        # 分配权限
        await self.role_repo.assign_permissions(db, role_id, permission_ids)
        
        await db.commit()
        
        # 获取所有关联此角色的用户并清除缓存
        from app.modules.auth.models import UserRole
        user_role_query = select(UserRole.user_id).where(UserRole.role_id == role_id)
        user_role_result = await db.execute(user_role_query)
        user_ids = [row[0] for row in user_role_result.all()]
        
        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if redis_client and user_ids:
            for user_id in user_ids:
                await clear_user_permission_cache(redis_client, tenant_id, user_id)
        
        logger.info(f"[RoleService] ✅ 权限分配成功: role_id={role_id}")
        
        return True

    async def list_permissions(
        self,
        db: AsyncSession,
        *,
        module: Optional[str] = None,
    ) -> PermissionListResponse:
        """
        获取权限列表
        
        Args:
            db: 数据库会话
            module: 模块筛选（可选）
        
        Returns:
            权限列表
        """
        if module:
            permissions = await self.permission_repo.get_by_module(db, module)
        else:
            permissions = await self.permission_repo.get_all(db)
        
        total = len(permissions)
        
        permission_responses = [
            PermissionResponse(
                id=p.id,
                code=p.code,
                name=p.name,
                module=p.module,
                description=p.description,
            )
            for p in permissions
        ]
        
        return PermissionListResponse(
            total=total,
            items=permission_responses,
        )

    async def get_role_permissions(
        self,
        db: AsyncSession,
        role_id: int,
    ) -> PermissionListResponse:
        """
        获取角色的权限列表
        
        Args:
            db: 数据库会话
            role_id: 角色ID
        
        Returns:
            权限列表
        
        Raises:
            NotFoundException: 角色不存在
        """
        role = await self.role_repo.get_by_id(db, role_id)
        if not role:
            raise NotFoundException("角色不存在")
        
        permissions = await self.permission_repo.get_role_permissions(db, role_id)
        
        permission_responses = [
            PermissionResponse(
                id=p.id,
                code=p.code,
                name=p.name,
                module=p.module,
                description=p.description,
            )
            for p in permissions
        ]
        
        return PermissionListResponse(
            total=len(permissions),
            items=permission_responses,
        )