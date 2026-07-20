"""
User Service - 用户业务逻辑层

处理用户管理的核心业务逻辑，包括：
- 用户创建/更新/删除
- 密码管理
- 角色绑定
- 权限缓存管理
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user.repository import UserRepository
from app.modules.auth.repository import AuthRepository
from app.modules.auth.models import Role, UserRole
from app.modules.user.models import User, UserStatus
from app.modules.user.schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    ChangePasswordRequest,
)
from app.core.security import hash_password, verify_password
from app.core.exceptions import (
    ValidationException,
    AuthException,
    NotFoundException,
)
from app.core.rbac.cache import clear_user_permission_cache

logger = logging.getLogger(__name__)


class UserService:
    """用户管理服务"""

    def __init__(self):
        self.user_repo = UserRepository()

    async def create_user(
        self,
        db: AsyncSession,
        data: UserCreate,
        operator_id: Optional[int] = None,
    ) -> UserResponse:
        """
        创建新用户
        
        Args:
            db: 数据库会话
            data: 用户创建数据
            operator_id: 操作人ID（用于审计日志）
        
        Returns:
            用户响应对象
        
        Raises:
            ValidationException: 手机号已存在
        """
        logger.info(f"[UserService] 创建用户: phone={data.phone}")
        
        # 检查手机号唯一性
        if await self.user_repo.exists_by_phone(db, data.phone):
            raise ValidationException("手机号已被注册")
        
        # 检查邮箱唯一性（如果提供了邮箱）
        if data.email and await self.user_repo.exists_by_email(db, data.email):
            raise ValidationException("邮箱已被使用")
        
        # 准备用户数据
        user_data: Dict[str, Any] = {
            "phone": data.phone,
            "password_hash": hash_password(data.password),
            "status": UserStatus.ACTIVE.value,
        }
        
        # 可选字段
        if data.email:
            user_data["email"] = data.email
        if data.nickname:
            user_data["nickname"] = data.nickname
        if data.real_name:
            user_data["real_name"] = data.real_name
        if data.avatar_url:
            user_data["avatar_url"] = data.avatar_url
        if data.gender is not None:
            user_data["gender"] = data.gender
        if data.birthday:
            user_data["birthday"] = data.birthday
        
        # 创建用户
        user = await self.user_repo.create(db, user_data)
        
        # 分配角色（支持 role_ids 和 role_codes）
        role_ids_to_assign = list(data.role_ids) if data.role_ids else []
        if data.role_codes:
            from app.core.tenant_context import get_tenant_id
            tenant_id = get_tenant_id()
            for code in data.role_codes:
                role = await AuthRepository.get_role_by_code(db, code, tenant_id)
                if role:
                    role_ids_to_assign.append(role.id)
        for role_id in role_ids_to_assign:
            await AuthRepository.assign_role(db, user.id, role_id)
        
        await db.commit()
        await db.refresh(user)
        
        # 获取用户角色列表
        roles = await AuthRepository.get_user_roles(db, user.id)
        role_codes = [role.code for role in roles]
        
        logger.info(f"[UserService] ✅ 用户创建成功: id={user.id}")
        
        return UserResponse(
            id=user.id,
            public_id=str(user.public_id),
            tenant_id=user.tenant_id,
            phone=user.phone,
            email=user.email,
            nickname=user.nickname,
            real_name=user.real_name,
            avatar_url=user.avatar_url,
            gender=user.gender,
            birthday=user.birthday,
            status=user.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=role_codes,
        )

    async def update_user(
        self,
        db: AsyncSession,
        user_id: int,
        data: UserUpdate,
        redis_client=None,
    ) -> UserResponse:
        """
        更新用户信息
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            data: 更新数据
            redis_client: Redis客户端（用于清除权限缓存）
        
        Returns:
            更新后的用户响应
        
        Raises:
            NotFoundException: 用户不存在
            ValidationException: 手机号/邮箱重复
        """
        logger.info(f"[UserService] 更新用户: user_id={user_id}")
        
        # 检查用户是否存在
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundException("用户不存在")
        
        # 准备更新数据
        update_data: Dict[str, Any] = {}
        
        # 检查手机号变更
        if data.phone and data.phone != user.phone:
            if await self.user_repo.exists_by_phone(db, data.phone, exclude_id=user_id):
                raise ValidationException("手机号已被使用")
            update_data["phone"] = data.phone
        
        # 检查邮箱变更
        if data.email and data.email != user.email:
            if await self.user_repo.exists_by_email(db, data.email, exclude_id=user_id):
                raise ValidationException("邮箱已被使用")
            update_data["email"] = data.email
        
        # 其他字段
        if data.nickname is not None:
            update_data["nickname"] = data.nickname
        if data.real_name is not None:
            update_data["real_name"] = data.real_name
        if data.avatar_url is not None:
            update_data["avatar_url"] = data.avatar_url
        if data.gender is not None:
            update_data["gender"] = data.gender
        if data.birthday is not None:
            update_data["birthday"] = data.birthday
        if data.status is not None:
            update_data["status"] = data.status
        
        # 执行更新
        if update_data:
            user = await self.user_repo.update(db, user_id, update_data)
        
        await db.commit()
        await db.refresh(user)
        
        # 更新角色（如果传入 role_ids）
        if data.role_ids is not None:
            await self.assign_roles(db, user_id, data.role_ids, redis_client=redis_client)
        
        # 获取角色列表
        roles = await AuthRepository.get_user_roles(db, user.id)
        role_codes = [role.code for role in roles]
        
        logger.info(f"[UserService] ✅ 用户更新成功: id={user_id}")
        
        return UserResponse(
            id=user.id,
            public_id=str(user.public_id),
            tenant_id=user.tenant_id,
            phone=user.phone,
            email=user.email,
            nickname=user.nickname,
            real_name=user.real_name,
            avatar_url=user.avatar_url,
            gender=user.gender,
            birthday=user.birthday,
            status=user.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=role_codes,
        )

    async def delete_user(
        self,
        db: AsyncSession,
        user_id: int,
        operator_id: int,
        redis_client=None,
    ) -> bool:
        """
        删除用户（软删除）
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            operator_id: 操作人ID（不能删除自己）
            redis_client: Redis客户端
        
        Returns:
            是否删除成功
        
        Raises:
            ValidationException: 不能删除自己 / 教师有未完成排课
            NotFoundException: 用户不存在
        """
        logger.warning(f"[UserService] 删除用户: user_id={user_id}, operator_id={operator_id}")
        
        # 检查是否删除自己
        if user_id == operator_id:
            raise ValidationException("不能删除自己的账号")

        # 检查教师是否有未完成的排课
        from app.modules.schedule.models import CourseSchedule, ScheduleStatus
        from datetime import datetime, timezone
        from app.core.tenant_context import get_tenant_id as _get_tenant_id

        tenant_id = _get_tenant_id()
        active_schedule_query = select(CourseSchedule).where(
            CourseSchedule.teacher_id == user_id,
            CourseSchedule.status == ScheduleStatus.NORMAL.value,
            CourseSchedule.start_at > datetime.now(timezone.utc),
        )
        if tenant_id:
            active_schedule_query = active_schedule_query.where(
                CourseSchedule.tenant_id == tenant_id,
            )

        result = await db.execute(active_schedule_query.limit(1))
        if result.scalar_one_or_none():
            raise ValidationException("该教师有未完成的排课，请先取消或完成排课后再删除")
        
        # 执行软删除
        success = await self.user_repo.delete(db, user_id)
        
        if not success:
            raise NotFoundException("用户不存在")
        
        # 清除权限缓存
        if redis_client:
            await clear_user_permission_cache(redis_client, tenant_id, user_id)
        
        logger.warning(f"[UserService] ✅ 用户删除成功: id={user_id}")
        
        return True

    async def get_user_by_id(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> UserResponse:
        """
        获取用户详情
        
        Args:
            db: 数据库会话
            user_id: 用户ID
        
        Returns:
            用户响应
        
        Raises:
            NotFoundException: 用户不存在
        """
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundException("用户不存在")
        
        roles = await AuthRepository.get_user_roles(db, user.id)
        role_codes = [role.code for role in roles]
        
        return UserResponse(
            id=user.id,
            public_id=str(user.public_id),
            tenant_id=user.tenant_id,
            phone=user.phone,
            email=user.email,
            nickname=user.nickname,
            real_name=user.real_name,
            avatar_url=user.avatar_url,
            gender=user.gender,
            birthday=user.birthday,
            status=user.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=role_codes,
        )

    async def list_users(
        self,
        db: AsyncSession,
        *,
        keyword: Optional[str] = None,
        status: Optional[int] = None,
        role_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> UserListResponse:
        """
        获取用户列表（分页）
        
        Args:
            db: 数据库会话
            keyword: 搜索关键词
            status: 状态筛选
            role_code: 角色筛选
            page: 页码
            page_size: 每页数量
        
        Returns:
            分页用户列表
        """
        items, total = await self.user_repo.search(
            db,
            keyword=keyword,
            status=status,
            page=page,
            page_size=page_size,
        )
        
        # 转换为响应对象
        user_responses = []
        for user in items:
            roles = await AuthRepository.get_user_roles(db, user.id)
            role_codes = [role.code for role in roles]
            
            # 角色筛选
            if role_code and role_code not in role_codes:
                continue
            
            user_responses.append(UserResponse(
                id=user.id,
                public_id=str(user.public_id),
                tenant_id=user.tenant_id,
                phone=user.phone,
                email=user.email,
                nickname=user.nickname,
                real_name=user.real_name,
                avatar_url=user.avatar_url,
                gender=user.gender,
                birthday=user.birthday,
                status=user.status,
                last_login_at=user.last_login_at,
                created_at=user.created_at,
                updated_at=user.updated_at,
                roles=role_codes,
            ))
        
        return UserListResponse(
            total=len(user_responses) if role_code else total,
            page=page,
            page_size=page_size,
            items=user_responses,
        )

    async def change_password(
        self,
        db: AsyncSession,
        user_id: int,
        data: ChangePasswordRequest,
    ) -> bool:
        """
        修改密码（用户自己操作）
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            data: 密码修改请求
        
        Returns:
            是否成功
        
        Raises:
            AuthException: 旧密码错误
            NotFoundException: 用户不存在
        """
        logger.info(f"[UserService] 修改密码: user_id={user_id}")
        
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundException("用户不存在")
        
        # 验证旧密码
        if not verify_password(data.old_password, user.password_hash):
            raise AuthException("旧密码错误")
        
        # 更新密码
        await self.user_repo.update_password(db, user_id, hash_password(data.new_password))
        
        logger.info(f"[UserService] ✅ 密码修改成功: user_id={user_id}")
        
        return True

    async def reset_password(
        self,
        db: AsyncSession,
        user_id: int,
        new_password: str,
        operator_id: int,
    ) -> bool:
        """
        重置密码（管理员操作）
        
        Args:
            db: 数据库会话
            user_id: 目标用户ID
            new_password: 新密码
            operator_id: 操作人ID
        
        Returns:
            是否成功
        
        Raises:
            NotFoundException: 用户不存在
            ValidationException: 不能重置自己的密码（安全限制）
        """
        logger.warning(f"[UserService] 重置密码: user_id={user_id}, operator_id={operator_id}")
        
        # 安全限制：不允许重置自己的密码（防止误操作）
        if user_id == operator_id:
            raise ValidationException("请使用'修改密码'功能修改自己的密码")
        
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundException("用户不存在")
        
        # 更新密码
        await self.user_repo.update_password(db, user_id, hash_password(new_password))
        
        logger.warning(f"[UserService] ✅ 密码重置成功: user_id={user_id}")
        
        return True

    async def assign_roles(
        self,
        db: AsyncSession,
        user_id: int,
        role_ids: List[int],
        redis_client=None,
    ) -> bool:
        """
        为用户分配角色（覆盖式）
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            role_ids: 要分配的角色ID列表
            redis_client: Redis客户端
        
        Returns:
            是否成功
        
        Raises:
            NotFoundException: 用户不存在
        """
        logger.info(f"[UserService] 分配角色: user_id={user_id}, role_ids={role_ids}")
        
        # 检查用户存在
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise NotFoundException("用户不存在")
        
        # 删除现有角色
        await db.execute(
            UserRole.__table__.delete().where(UserRole.user_id == user_id)
        )
        
        # 添加新角色
        for role_id in role_ids:
            await AuthRepository.assign_role(db, user_id, role_id)
        
        await db.commit()
        
        # 清除权限缓存（关键步骤！）
        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if redis_client:
            await clear_user_permission_cache(redis_client, tenant_id, user_id)
        
        logger.info(f"[UserService] ✅ 角色分配成功: user_id={user_id}")
        
        return True

    async def get_user_roles(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """
        获取用户的角色列表
        
        Args:
            db: 数据库会话
            user_id: 用户ID
        
        Returns:
            角色列表
        """
        roles = await AuthRepository.get_user_roles(db, user_id)
        
        return [
            {
                "id": role.id,
                "code": role.code,
                "name": role.name,
                "description": role.description,
            }
            for role in roles
        ]