"""
Role Repository - 角色权限数据访问层

提供角色和权限相关的数据库操作。
"""

from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy import select, and_, or_, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.auth.models import Role, Permission, RolePermission


class RoleRepository(TenantAwareRepository[Role]):
    """
    角色数据访问层
    
    继承 TenantAwareRepository，自动处理多租户隔离。
    """
    
    model_class = Role

    async def get_by_code(
        self,
        db: AsyncSession,
        code: str,
    ) -> Optional[Role]:
        """
        根据角色代码查询角色
        
        Args:
            db: 数据库会话
            code: 角色代码
        
        Returns:
            角色对象或 None
        """
        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        
        query = select(Role).where(Role.code == code)
        
        # 优先查找租户自定义角色，再查找系统角色
        if tenant_id:
            query = query.where(
                or_(
                    Role.tenant_id == tenant_id,
                    Role.tenant_id.is_(None)
                )
            ).order_by(Role.tenant_id.is_not(None).desc())
        
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def search(
        self,
        db: AsyncSession,
        *,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Role], int]:
        """
        搜索角色（支持关键词筛选、分页）
        
        Args:
            db: 数据库会话
            keyword: 搜索关键词（匹配代码/名称）
            page: 页码
            page_size: 每页数量
        
        Returns:
            角色列表和总数
        """
        base_query = select(Role)
        count_query = select(func.count()).select_from(Role)
        
        # 关键词搜索
        if keyword:
            keyword_pattern = f"%{keyword}%"
            search_condition = or_(
                Role.code.ilike(keyword_pattern),
                Role.name.ilike(keyword_pattern),
            )
            base_query = base_query.where(search_condition)
            count_query = count_query.where(search_condition)
        
        # 添加租户过滤
        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            # 显示当前租户角色 + 系统角色（tenant_id IS NULL）
            tenant_condition = or_(
                Role.tenant_id == tenant_id,
                Role.tenant_id.is_(None)
            )
            base_query = base_query.where(tenant_condition)
            count_query = count_query.where(tenant_condition)
        
        # 排序：系统角色在前，按创建时间排序
        base_query = base_query.order_by(
            Role.tenant_id.is_(None).desc(),
            Role.created_at.desc()
        )
        
        # 分页
        offset_val = (page - 1) * page_size
        base_query = base_query.offset(offset_val).limit(page_size)
        
        # 执行查询
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        result = await db.execute(base_query)
        items = list(result.scalars().all())
        
        return items, total

    async def exists_by_code(
        self,
        db: AsyncSession,
        code: str,
        *,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        检查角色代码是否已存在
        
        Args:
            db: 数据库会话
            code: 角色代码
            exclude_id: 排除指定 ID
        
        Returns:
            是否存在
        """
        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        
        query = select(func.count()).select_from(Role).where(
            Role.code == code,
            Role.tenant_id == tenant_id
        )
        
        if exclude_id:
            query = query.where(Role.id != exclude_id)
        
        result = await db.execute(query)
        count = result.scalar() or 0
        
        return count > 0

    async def delete_role_permissions(
        self,
        db: AsyncSession,
        role_id: int,
    ) -> None:
        """
        删除角色的所有权限绑定
        
        Args:
            db: 数据库会话
            role_id: 角色ID
        """
        await db.execute(
            delete(RolePermission).where(RolePermission.role_id == role_id)
        )

    async def assign_permissions(
        self,
        db: AsyncSession,
        role_id: int,
        permission_ids: List[int],
    ) -> None:
        """
        为角色分配权限（覆盖式）
        
        Args:
            db: 数据库会话
            role_id: 角色ID
            permission_ids: 权限ID列表
        """
        # 先删除现有权限
        await self.delete_role_permissions(db, role_id)
        
        # 添加新权限
        for permission_id in permission_ids:
            role_permission = RolePermission(
                role_id=role_id,
                permission_id=permission_id
            )
            db.add(role_permission)


class PermissionRepository:
    """
    权限数据访问层
    
    权限是全局的（不分租户），所以不继承 TenantAwareRepository。
    """

    @staticmethod
    async def get_all(db: AsyncSession) -> List[Permission]:
        """获取所有权限"""
        query = select(Permission).order_by(Permission.module, Permission.code)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(db: AsyncSession, permission_id: int) -> Optional[Permission]:
        """根据ID获取权限"""
        query = select(Permission).where(Permission.id == permission_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> Optional[Permission]:
        """根据代码获取权限"""
        query = select(Permission).where(Permission.code == code)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_module(db: AsyncSession, module: str) -> List[Permission]:
        """根据模块获取权限"""
        query = select(Permission).where(Permission.module == module).order_by(Permission.code)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_role_permissions(db: AsyncSession, role_id: int) -> List[Permission]:
        """获取角色的所有权限"""
        query = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.module, Permission.code)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_permission_ids_by_role(db: AsyncSession, role_id: int) -> List[int]:
        """获取角色的权限ID列表"""
        query = select(RolePermission.permission_id).where(RolePermission.role_id == role_id)
        result = await db.execute(query)
        return [row[0] for row in result.all()]

    @staticmethod
    async def get_permission_codes_by_role(db: AsyncSession, role_id: int) -> List[str]:
        """获取角色的权限代码列表"""
        query = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        result = await db.execute(query)
        return [row[0] for row in result.all()]

    @staticmethod
    async def count(db: AsyncSession) -> int:
        """统计权限总数"""
        query = select(func.count()).select_from(Permission)
        result = await db.execute(query)
        return result.scalar() or 0

    @staticmethod
    async def exists(db: AsyncSession, permission_id: int) -> bool:
        """检查权限是否存在"""
        query = select(func.count()).select_from(Permission).where(Permission.id == permission_id)
        result = await db.execute(query)
        return (result.scalar() or 0) > 0