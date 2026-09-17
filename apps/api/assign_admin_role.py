"""
临时脚本：为指定用户分配 admin 角色

使用方法：
python -m apps.api.assign_admin_role <user_id>

示例：
python -m apps.api.assign_admin_role 1
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.modules.auth.models import Role, UserRole, Tenant


async def assign_admin_role(user_id: int):
    """为用户分配 admin 角色"""
    async with async_session() as session:
        # 1. 查询用户
        from app.modules.auth.models import User
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ 用户 {user_id} 不存在")
            return False
        
        print(f"✅ 找到用户: {user.phone} (ID: {user.id})")
        print(f"   租户 ID: {user.tenant_id}")
        
        # 2. 查询 admin 角色（优先查租户自定义角色，再查系统角色）
        result = await session.execute(
            select(Role).where(
                Role.code == "admin",
                Role.tenant_id.in_([user.tenant_id, None])
            ).order_by(Role.tenant_id.is_not(None).desc())
        )
        admin_role = result.scalar_one_or_none()
        
        if not admin_role:
            print("❌ 未找到 admin 角色，需要先创建角色")
            return False
        
        print(f"✅ 找到 admin 角色: {admin_role.name} (ID: {admin_role.id})")
        
        # 3. 检查是否已分配
        result = await session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == admin_role.id
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            print("⚠️  用户已经拥有 admin 角色")
            return True
        
        # 4. 分配角色
        user_role = UserRole(user_id=user_id, role_id=admin_role.id)
        session.add(user_role)
        await session.commit()
        
        print("✅ 成功为用户分配 admin 角色！")
        print("🔄 请重新登录以使新角色生效")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python -m apps.api.assign_admin_role <user_id>")
        sys.exit(1)
    
    user_id = int(sys.argv[1])
    success = asyncio.run(assign_admin_role(user_id))
    sys.exit(0 if success else 1)