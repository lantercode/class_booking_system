"""
T02 种子数据脚本 - 创建系统运行所需的初始数据

包含：
- 默认租户机构（舞蹈工作室）
- 4 个系统角色：超管、管理员、老师、学员
- 9 个基础权限项
- 默认管理员账号

运行方式：
    cd apps/api
    uv run python scripts/seed.py
"""

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import SessionLocal
from app.modules.tenant.models import Tenant, TenantStatus
from app.modules.user.models import User, UserStatus
from app.modules.auth.models import Role, Permission, UserRole, RolePermission
from app.core.security import hash_password


async def create_default_tenant(session: AsyncSession) -> Tenant:
    """创建默认租户机构"""
    # TODO: 实现这个函数
    tenant = Tenant(
        name="舞蹈机构",
        slug="dance-school",
        contact_phone="12345678901",
        status=TenantStatus.ACTIVE.value,
        plan="pro",
        settings={
            "theme": "default",
            "language": "zh-CN",
            "timezone": "Asia/Shanghai",
        }
    )
    session.add(tenant)
    await session.flush() # 刷新以获取自增 ID
    return tenant # ✅ 返回创建的对象

async def create_system_roles(session: AsyncSession, tenant_id: int) -> list[Role]:
    """创建 4 个系统角色"""
    # TODO: 实现这个函数
    roles_data = [
        {"code": "super_admin", "name": "超级管理员", "is_system": True, "description": "拥有所有权限"},
        {"code": "admin", "name": "管理员", "is_system": True, "description": "管理机构日常运营"},
        {"code": "teacher", "name": "老师", "is_system": False, "description": "授课老师"},
        {"code": "student", "name": "学员", "is_system": False, "description": "普通学员"},
    ]
    roles = []
    for role_data in roles_data:
        role = Role(
            tenant_id=tenant_id,
            code=role_data["code"],
            name=role_data["name"],
            is_system=role_data["is_system"],
            description=role_data["description"],
        )
        session.add(role)
        roles.append(role)
    await session.flush()
    return roles


async def create_permissions(session: AsyncSession) -> list[Permission]:
    """创建 9 个基础权限项"""
    # TODO: 实现这个函数
    permissions_data = [
        # 课程管理 (3个)
        {"code": "course:create", "name": "创建课程", "module": "course"},
        {"code": "course:update", "name": "编辑课程", "module": "course"},
        {"code": "course:delete", "name": "删除课程", "module": "course"},

        # 排课管理 (2个)
        {"code": "schedule:create", "name": "创建排课", "module": "schedule"},
        {"code": "schedule:cancel", "name": "取消排课", "module": "schedule"},

        # 预约管理 (2个)
        {"code": "booking:view", "name": "查看预约", "module": "booking"},
        {"code": "booking:manage", "name": "管理预约", "module": "booking"},

        # 用户管理 (1个)
        {"code": "user:manage", "name": "管理用户", "module": "user"},

        # 数据统计 (1个)
        {"code": "stats:view", "name": "查看统计", "module": "stats"},
    ]

    permissions = []
    for perm_data in permissions_data:
        perm = Permission(
            code=perm_data["code"],
            name=perm_data["name"],
            module=perm_data["module"],
        )
        session.add(perm)
        permissions.append(perm)
    await session.flush()
    return permissions


async def assign_role_permissions(
        session: AsyncSession,
        roles: list[Role],
        permissions: list[Permission]
) -> None:
    """分配权限给角色"""
    # TODO: 实现这个函数
    # 超级管理员拥有所有权限
    super_admin_role = next(r for r in roles if r.code == "super_admin")
    for perm in permissions:
        session.add(RolePermission(
            role_id=super_admin_role.id,
            permission_id=perm.id
        ))

    # 管理员角色拥有部分权限课程、排课、预约、用户
    admin_role = next(r for r in roles if r.code == "admin")
    admin_permission_codes = {
        "course:create", "course:update",
        "schedule:create", "schedule:cancel",
        "booking:view", "booking:manage",
        "user:manage"
    }
    for perm in permissions:
        if perm.code in admin_permission_codes:
            session.add(RolePermission(
                role_id=admin_role.id,
                permission_id=perm.id
            ))

    # 老师角色拥有部分权限 排课、预约
    teacher_role = next(r for r in roles if r.code == "teacher")
    teacher_permission_codes = {
        "schedule:create", "schedule:cancel",
        "booking:view", "booking:manage"
    }
    for perm in permissions:
        if perm.code in teacher_permission_codes:
            session.add(RolePermission(
                role_id=teacher_role.id,
                permission_id=perm.id
            ))

    # 学员只有查看预约的权限
    student_role = next(r for r in roles if r.code == "student")
    student_perm = next(p for p in permissions if p.code == "booking:view")
    session.add(RolePermission(
        role_id=student_role.id,
        permission_id=student_perm.id
    ))

    await session.flush()


async def create_admin_user(
        session: AsyncSession,
        tenant_id: int,
        roles: list[Role]
) -> User:
    """创建默认管理员账号"""
    # TODO: 实现这个函数
    password_hash = hash_password("admin123456")

    user = User(
        tenant_id=tenant_id,
        phone="12345678901",
        password_hash=password_hash,
        nickname="系统管理员",
        platform_role="super_admin",
        status=UserStatus.ACTIVE.value
    )
    session.add(user)
    await session.flush()

    # 分配超级管理员角色
    super_admin_role = next(r for r in roles if r.code == "super_admin")
    session.add(UserRole(
        user_id=user.id,
        role_id=super_admin_role.id
    ))
    await session.flush()
    return user


async def main():
    """主函数 - 执行所有种子数据的写入"""
    print("🌱 开始创建种子数据...")

    async with SessionLocal() as session:
        try:
            # 1. 创建默认租户
            tenant = await create_default_tenant(session)
            print(f"✅ 创建租户: {tenant.name}")

            # 2. 创建系统角色
            roles = await create_system_roles(session, tenant.id)
            print(f"✅ 创建 {len(roles)} 个角色")

            # 3. 创建权限项
            permissions = await create_permissions(session)
            print(f"✅ 创建 {len(permissions)} 个权限")

            # 4. 分配权限给角色
            await assign_role_permissions(session, roles, permissions)
            print("✅ 分配角色权限完成")

            # 5. 创建默认管理员
            admin_user = await create_admin_user(session, tenant.id, roles)
            print(f"✅ 创建管理员: {admin_user.phone}")

            # 提交事务
            await session.commit()
            print("\n🎉 种子数据创建完成！")

        except Exception as e:
            await session.rollback()
            print(f"\n❌ 种子数据创建失败: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())