from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user.models import User
from app.modules.auth.models import Role, UserRole
from app.modules.tenant.models import Tenant


class AuthRepository:
    """认证相关的数据库操作"""

    # 用户查询 @staticmethod：这个方法不需要访问类（cls）或实例（self），只是“挂在类里面的普通函数”。
    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
        """
        根据id查询用户

        Args:
            session: 数据库会话
            user_id: 用户 ID

        Returns:
            用户对象，不存在则返回 None
        """
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_phone(session: AsyncSession, tenant_id: int, phone: str) -> User | None:
        """
        根据手机号查询用户

        Args:
            session: 数据库会话
            tenant_id: 租户 ID
            phone: 手机号

        returns:
            用户对象，不存在则返回None
        """
        result = await session.execute(select(User).where(User.tenant_id == tenant_id, User.phone == phone, User.deleted_at.is_(None)))
        return result.scalar_one_or_none()

    # 用户创建
    @staticmethod
    async def create_user(session: AsyncSession, user_data: dict) -> User:
        """
        创建新用户

        Args:
            session: 数据库会话
            user_data: 用户数据字典

        Returns：
            新创建的用户对象
        """
        user = User(**user_data)
        session.add(user)
        await session.flush()
        return user


    # 用户更新
    @staticmethod
    async def update_user(session: AsyncSession, user: User, data: dict) -> User:
        """
        更新用户信息

        Args:
            session: 数据库会话
            user: 用户对象
            data: 要更新的用户对象
        """
        if not data:
            raise ValueError("No data to update")

        for key, value in data.items(): # 先遍历完所有的字段
            setattr(user, key, value)

        await session.flush()
        return user

    # 角色管理
    @staticmethod
    async def assign_role(session: AsyncSession, user_id: int, role_id: int) -> None:
        """
        为用户分配角色

        Args:
            session: 数据库会话
            user_id: 用户 ID
            role_id: 角色 ID
        """
        user_role = UserRole(user_id=user_id, role_id=role_id)
        session.add(user_role)
        await session.flush()

    @staticmethod
    async def get_user_roles(session: AsyncSession, user_id:  int) -> list[Role]:
        """
        获取用户角色列表

        Args:
            session: 数据库会话
            user_id: 用户 ID
        """
        result = await session.execute(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_tenant_by_slug(session: AsyncSession, slug: str) -> Tenant | None:
        """
        根据 slug 查询租户

        Args:
            session: 数据库会话
            slug: 租户 slug

        Returns:
            租户对象，不存在则返回 None
        """
        result = await session.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_role_by_code(session: AsyncSession, code: str, tenant_id: int) -> Role | None:
        """
        根据 code 查询角色

        Args:
            session: 数据库会话
            code: 角色 code
            tenant_id: 租户 ID

        Returns:
            角色对象，不存在则返回 None
        """
        result = await session.execute(select(Role).where(Role.code == code, Role.tenant_id == tenant_id))
        return result.scalar_one_or_none()
