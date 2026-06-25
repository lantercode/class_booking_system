"""
T02 单元测试 - ORM 模型验证

测试内容：
- 模型实例化
- 字段默认值
- 表名定义
- 基础约束

运行方式：
    cd apps/api
    uv run pytest tests/unit/test_models.py -v
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# 导入要测试的模型
from app.modules.tenant.models import Tenant, TenantStatus
from app.modules.user.models import User, UserStatus
from app.modules.auth.models import Role, Permission


class TestTenantModel:
    """租户模型测试"""

    def test_tenant_table_name(self):
        """测试表名是否正确"""
        assert Tenant.__tablename__ == "tenants"

    def test_tenant_instance_creation(self):
        """测试能否创建租户实例"""
        tenant = Tenant(
            name="测试舞蹈工作室",
            slug="test-studio",
            status=TenantStatus.ACTIVE.value,
            plan="pro"
        )

        assert tenant.name == "测试舞蹈工作室"
        assert tenant.slug == "test-studio"
        assert tenant.status == 1  # TenantStatus.ACTIVE.value
        assert tenant.plan == "pro"

    def test_tenant_default_status(self):
        """测试状态默认值"""
        # 注意：这里不传 status 参数
        # 但由于我们在 seed.py 中发现必须传 .value，
        # 所以这个测试可能需要调整
        pass  # TODO: 根据实际情况实现


class TestUserModel:
    """用户模型测试"""

    def test_user_table_name(self):
        """测试表名是否正确"""
        assert User.__tablename__ == "users"

    def test_user_instance_creation(self):
        """测试能否创建用户实例"""
        user = User(
            tenant_id=1,
            phone="13800138000",
            password_hash="$2b$12$testhash",
            nickname="测试用户",
            platform_role="admin",
            status=UserStatus.ACTIVE.value,
        )

        assert user.tenant_id == 1
        assert user.phone == "13800138000"
        assert user.nickname == "测试用户"
        assert user.platform_role == "admin"
        assert user.status == 1


class TestRoleModel:
    """角色模型测试"""

    def test_role_table_name(self):
        """测试表名是否正确"""
        assert Role.__tablename__ == "roles"

    def test_role_instance_creation(self):
        """测试能否创建角色实例"""
        role = Role(
            tenant_id=1,
            code="test_role",
            name="测试角色",
            is_system=False,
            description="这是一个测试角色"
        )

        assert role.code == "test_role"
        assert role.name == "测试角色"
        assert role.is_system is False


class TestPermissionModel:
    """权限模型测试"""

    def test_permission_table_name(self):
        """测试表名是否正确"""
        assert Permission.__tablename__ == "permissions"

    def test_permission_instance_creation(self):
        """测试能否创建权限实例"""
        perm = Permission(
            code="test:permission",
            name="测试权限",
            module="test",
            description="这是一个测试权限"
        )

        assert perm.code == "test:permission"
        assert perm.module == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])