"""
管理后台模块 - 业务逻辑层

模拟用户管理的 CRUD 操作。
实际项目中这里会调用 Repository 层访问数据库。

注意：此文件仅用于演示 RBAC 权限系统的使用方式，
不包含真实的数据库操作。
"""

import logging
from typing import List, Optional, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac.cache import clear_user_permission_cache
from app.core.exceptions import NotFoundException, BusinessException

logger = logging.getLogger(__name__)


class AdminUserService:
    """用户管理服务（示例）"""

    @staticmethod
    async def create_user(
        db: AsyncSession,
        data: dict,
        current_user: dict,
    ) -> dict:
        """
        创建新用户
        
        业务规则：
        1. 只有拥有 user:create 权限的用户才能调用（由装饰器保证）
        2. 检查手机号是否已存在
        3. 创建用户并分配角色
        4. （可选）清除相关缓存
        
        Args:
            db: 数据库会话
            data: 用户数据（来自请求体）
            current_user: 当前操作人信息
            
        Returns:
            新创建的用户信息
            
        Raises:
            BusinessException: 手机号已存在
        """
        logger.info(
            f"[Admin] 用户 {current_user['user_id']} 正在创建用户: "
            f"phone={data.get('phone')}"
        )
        
        # TODO: 实际实现
        # 1. 检查手机号唯一性
        # existing = await user_repo.get_by_phone(db, data['phone'])
        # if existing:
        #     raise BusinessException("该手机号已被注册")
        
        # 2. 创建用户
        # user = await user_repo.create(db, data)
        
        # 3. 分配角色
        # if data.get('role_ids'):
        #     await user_role_repo.assign_roles(db, user.id, data['role_ids'])
        
        # 返回模拟数据
        new_user = {
            "id": 9999,
            "tenant_id": current_user.get("tenant_id"),
            "username": data.get("username"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "is_active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "roles": ["student"],  # 默认角色
        }
        
        logger.info(f"[Admin] ✅ 用户创建成功: id={new_user['id']}")
        return new_user

    @staticmethod
    async def update_user(
        db: AsyncSession,
        user_id: int,
        data: dict,
        current_user: dict,
    ) -> dict:
        """
        更新用户信息
        
        权限要求：user:update + user:read（AND 逻辑）
        
        重要：如果修改了用户的角色，需要清除其权限缓存！
        """
        logger.info(
            f"[Admin] 用户 {current_user['user_id']} 正在更新用户 {user_id}"
        )
        
        # TODO: 实际实现
        # 1. 检查用户是否存在
        # user = await user_repo.get_by_id(db, user_id)
        # if not user:
        #     raise NotFoundException("用户不存在")
        
        # 2. 更新字段
        # updated_user = await user_repo.update(db, user_id, data)
        
        # 3. 如果角色变更，清除缓存 ⚠️ 关键步骤！
        # if 'role_ids' in data:
        #     redis_client = get_redis_client()  # 从依赖获取
        #     await clear_user_permission_cache(
        #         redis_client,
        #         tenant_id=current_user['tenant_id'],
        #         user_id=user_id
        #     )
        #     logger.info(f"[Admin] 已清除用户 {user_id} 的权限缓存")
        
        updated_user = {
            "id": user_id,
            "tenant_id": current_user.get("tenant_id"),
            "username": data.get("username", "test_user"),
            "email": data.get("email"),
            "phone": "13800138000",
            "is_active": data.get("is_active", True),
            "created_at": datetime(2024, 1, 1),
            "updated_at": datetime.now(),
            "roles": ["teacher"],
        }
        
        logger.info(f"[Admin] ✅ 用户 {user_id} 更新成功")
        return updated_user

    @staticmethod
    async def delete_user(
        db: AsyncSession,
        user_id: int,
        current_user: dict,
        redis_client=None,
    ) -> dict:
        """
        删除用户（高危操作）
        
        权限要求：user:delete（专门的高危权限）
        
        安全措施：
        1. 需要专门的删除权限
        2. 不能删除自己
        3. 删除后清除缓存
        4. 记录详细审计日志
        """
        operator_id = current_user["user_id"]
        
        if user_id == operator_id:
            raise BusinessException("不能删除自己的账号")
        
        logger.warning(
            f"[Admin] ⚠️ 危险操作：用户 {operator_id} 正在删除用户 {user_id}"
        )
        
        # TODO: 实际实现
        # 1. 软删除或硬删除
        # await user_repo.delete(db, user_id)
        
        # 2. 清除缓存
        if redis_client:
            await clear_user_permission_cache(
                redis_client,
                tenant_id=current_user.get("tenant_id"),
                user_id=user_id
            )
        
        logger.warning(f"[Admin] ✅ 用户 {user_id} 已被删除，操作人: {operator_id}")
        return {"message": f"用户 {user_id} 已删除"}

    @staticmethod
    async def list_users(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> dict:
        """
        获取用户列表（分页）
        
        权限要求：user:read
        """
        logger.debug(f"[Admin] 获取用户列表: page={page}, size={page_size}")
        
        # TODO: 实际实现
        # users, total = await user_repo.paginate(
        #     db, 
        #     page=page, 
        #     page_size=page_size,
        #     keyword=keyword
        # )
        
        return {
            "total": 100,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": i,
                    "tenant_id": 10,
                    "username": f"user_{i}",
                    "email": f"user{i}@example.com",
                    "phone": f"1380013{i:04d}",
                    "is_active": i % 2 == 0,
                    "created_at": datetime(2024, 1, i % 28 + 1),
                    "updated_at": datetime.now(),
                    "roles": ["admin"] if i == 1 else ["student"],
                }
                for i in range((page - 1) * page_size + 1, page * page_size + 1)
            ]
        }

    @staticmethod
    async def get_my_permissions(
        db: AsyncSession,
        redis_client,
        current_user: dict,
    ) -> dict:
        """
        获取当前用户的完整权限列表（用于前端渲染菜单/按钮）
        
        这是一个很好的 RBAC 使用示例：
        - 前端调用此接口获取当前用户的所有权限
        - 根据返回的权限列表控制 UI 元素的显示/隐藏
        - 如：有 'user:create' 权限才显示"新建用户"按钮
        """
        from app.core.rbac.checker import get_user_permissions
        
        user_id = current_user["user_id"]
        tenant_id = current_user["tenant_id"]
        
        logger.info(f"[Admin] 获取用户 {user_id} 的权限列表")
        
        permissions = await get_user_permissions(
            db_session=db,
            redis_client=redis_client,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        
        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "permissions": [
                {"code": p, "name": p.split(":")[1], "module": p.split(":")[0]}
                for p in sorted(permissions)
            ],
            "roles": current_user.get("role_codes", []),
            "cached": len(permissions) > 0,  # 简单判断是否命中缓存
        }


# 创建服务实例
admin_user_service = AdminUserService()
