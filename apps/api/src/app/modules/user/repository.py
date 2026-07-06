"""
User Repository - 用户数据访问层

提供用户相关的数据库操作，继承 TenantAwareRepository 实现自动多租户隔离。
"""

from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.user.models import User, UserStatus


class UserRepository(TenantAwareRepository[User]):
    """
    用户数据访问层
    
    继承 TenantAwareRepository，自动处理：
    - 所有查询自动添加 tenant_id 过滤
    - 创建时自动注入 tenant_id
    - 软删除支持
    """
    
    model_class = User

    async def get_by_phone(
        self,
        db: AsyncSession,
        phone: str,
        *,
        include_deleted: bool = False,
    ) -> Optional[User]:
        """
        根据手机号查询用户（自动注入 tenant_id）
        
        Args:
            db: 数据库会话
            phone: 手机号
            include_deleted: 是否包含已删除用户
        
        Returns:
            用户对象或 None
        """
        query = select(User).where(User.phone == phone)
        
        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))
        
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(
        self,
        db: AsyncSession,
        email: str,
        *,
        include_deleted: bool = False,
    ) -> Optional[User]:
        """
        根据邮箱查询用户
        
        Args:
            db: 数据库会话
            email: 邮箱地址
            include_deleted: 是否包含已删除用户
        
        Returns:
            用户对象或 None
        """
        query = select(User).where(User.email == email)
        
        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))
        
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def search(
        self,
        db: AsyncSession,
        *,
        keyword: Optional[str] = None,
        status: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[User], int]:
        """
        搜索用户（支持关键词、状态筛选、分页）
        
        Args:
            db: 数据库会话
            keyword: 搜索关键词（匹配手机号/昵称/真实姓名）
            status: 用户状态筛选
            page: 页码
            page_size: 每页数量
        
        Returns:
            用户列表和总数
        """
        base_query = select(User).where(User.deleted_at.is_(None))
        count_query = select(func.count()).select_from(User).where(User.deleted_at.is_(None))
        
        # 关键词搜索
        if keyword:
            keyword_pattern = f"%{keyword}%"
            search_condition = or_(
                User.phone.ilike(keyword_pattern),
                User.nickname.ilike(keyword_pattern),
                User.real_name.ilike(keyword_pattern),
            )
            base_query = base_query.where(search_condition)
            count_query = count_query.where(search_condition)
        
        # 状态筛选
        if status is not None:
            base_query = base_query.where(User.status == status)
            count_query = count_query.where(User.status == status)
        
        # 添加多租户过滤（手动添加，因为 search 不是继承的方法）
        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            base_query = base_query.where(User.tenant_id == tenant_id)
            count_query = count_query.where(User.tenant_id == tenant_id)
        
        # 排序
        base_query = base_query.order_by(User.created_at.desc())
        
        # 分页
        offset_val = (page - 1) * page_size
        base_query = base_query.offset(offset_val).limit(page_size)
        
        # 执行查询
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        result = await db.execute(base_query)
        items = list(result.scalars().all())
        
        return items, total

    async def exists_by_phone(
        self,
        db: AsyncSession,
        phone: str,
        *,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        检查手机号是否已存在
        
        Args:
            db: 数据库会话
            phone: 手机号
            exclude_id: 排除指定 ID（用于更新场景）
        
        Returns:
            是否存在
        """
        query = select(func.count()).select_from(User).where(
            User.phone == phone,
            User.deleted_at.is_(None)
        )
        
        if exclude_id:
            query = query.where(User.id != exclude_id)
        
        # 添加租户过滤
        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(User.tenant_id == tenant_id)
        
        result = await db.execute(query)
        count = result.scalar() or 0
        
        return count > 0

    async def exists_by_email(
        self,
        db: AsyncSession,
        email: str,
        *,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        检查邮箱是否已存在
        
        Args:
            db: 数据库会话
            email: 邮箱
            exclude_id: 排除指定 ID
        
        Returns:
            是否存在
        """
        query = select(func.count()).select_from(User).where(
            User.email == email,
            User.email.is_not(None),
            User.deleted_at.is_(None)
        )
        
        if exclude_id:
            query = query.where(User.id != exclude_id)
        
        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(User.tenant_id == tenant_id)
        
        result = await db.execute(query)
        count = result.scalar() or 0
        
        return count > 0

    async def update_password(
        self,
        db: AsyncSession,
        user_id: int,
        password_hash: str,
    ) -> Optional[User]:
        """
        更新用户密码
        
        Args:
            db: 数据库会话
            user_id: 用户 ID
            password_hash: 加密后的密码
        
        Returns:
            更新后的用户对象或 None
        """
        user = await self.get_by_id(db, user_id)
        if not user:
            return None
        
        user.password_hash = password_hash
        await db.commit()
        await db.refresh(user)
        
        return user

    async def update_status(
        self,
        db: AsyncSession,
        user_id: int,
        status: int,
    ) -> Optional[User]:
        """
        更新用户状态
        
        Args:
            db: 数据库会话
            user_id: 用户 ID
            status: 新状态
        
        Returns:
            更新后的用户对象或 None
        """
        user = await self.get_by_id(db, user_id)
        if not user:
            return None
        
        user.status = status
        await db.commit()
        await db.refresh(user)
        
        return user