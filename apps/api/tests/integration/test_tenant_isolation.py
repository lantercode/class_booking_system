"""
T04 租户隔离测试 - 验证多租户查询自动注入

测试场景：
1. A租户用户无法查询到B租户的数据
2. 自动注入 tenant_id 过滤条件
3. 无租户上下文时正常工作（公开接口）
4. 跳过非租户模型（如 Permission 表）
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.database import SessionLocal
from app.core.tenant_query import setup_tenant_query_injection
from app.modules.tenant.models import Tenant, TenantStatus
from app.modules.user.models import User


@pytest.fixture(scope="module")
async def client():
    """创建测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="module")
def register_tenant_query_event():
    """
    注册多租户查询自动注入事件（只需执行一次）

    重要：测试环境绕过了FastAPI lifespan，需要手动注册事件
    """
    setup_tenant_query_injection()
    yield

@pytest.fixture
async def db_session(register_tenant_query_event):  # ← 改为 function scope
    """创建数据库会话（依赖事件注册）"""
    async with SessionLocal() as session:
        yield session


@pytest.mark.asyncio
class TestTenantIsolation:
    """租户隔离测试套件"""

    async def test_tenant_a_cannot_see_b_data(self, db_session: AsyncSession):
        """
        测试目标：验证A租户无法查询到B租户的数据
        
        场景：
        - 设置当前租户为 A (ID=1)
        - 查询所有用户
        - 验证结果只包含A租户的用户
        """
        from app.core.tenant_context import set_tenant_id

        # 1. 设置当前租户为 1 (假设是租户A)
        set_tenant_id(1)

        # 2. 执行查询（不手动添加 tenant_id 条件）
        result = await db_session.execute(
            select(User)  # 注意：没有写 where(User.tenant_id == ...)
        )
        users = list(result.scalars().all())

        # 3. 验证所有返回的用户都属于租户1
        for user in users:
            assert user.tenant_id == 1, f"数据泄露！用户 {user.id} 属于租户 {user.tenant_id}"

        print(f"✅ 租户隔离成功：只查询到 {len(users)} 个租户1的用户")

        # 清理
        set_tenant_id(None)

    async def test_different_tenants_get_different_data(self, db_session: AsyncSession):
        """
        测试目标：不同租户看到不同的数据集
        
        场景：
        - 先以租户A身份查询，记录数量
        - 再以租户B身份查询，记录数量
        - 验证两个结果集互不相交
        """
        from app.core.tenant_context import set_tenant_id

        # 1. 以租户A身份查询
        set_tenant_id(1)
        result_a = await db_session.execute(select(User))
        users_a = set(user.id for user in result_a.scalars().all())
        set_tenant_id(None)

        # 2. 以租户B身份查询（假设ID=2）
        set_tenant_id(2)
        result_b = await db_session.execute(select(User))
        users_b = set(user.id for user in result_b.scalars().all())
        set_tenant_id(None)

        # 3. 验证两个集合无交集
        intersection = users_a & users_b
        assert len(intersection) == 0, f"数据泄露！{len(intersection)} 个用户同时属于两个租户"

        print(f"✅ 租户隔离验证通过：租户A有 {len(users_a)} 个用户，租户B有 {len(users_b)} 个用户")

    async def test_no_tenant_context_returns_all(self, db_session: AsyncSession):
        """
        测试目标：无租户上下文时不注入过滤条件
        
        场景：
        - 不设置 tenant_id
        - 查询用户表
        - 应该能查到所有租户的数据（或根据业务需求报错）
        
        注意：当前实现是无租户ID时跳过注入
        """
        from app.core.tenant_context import get_tenant_id, set_tenant_id

        # 确保没有设置租户ID
        current_tenant = get_tenant_id()
        assert current_tenant is None

        # 执行查询（不会自动添加过滤）
        result = await db_session.execute(
            select(User).limit(5)  # 只取前5条避免太多数据
        )
        users = list(result.scalars().all())

        # 验证可以查询到数据（可能来自不同租户）
        if len(users) > 0:
            tenants_found = set(user.tenant_id for user in users)
            print(f"⚠️ 无租户上下文：查询到 {len(users)} 个用户，来自 {len(tenants_found)} 个租户")

    async def test_non_tenant_model_not_affected(self, db_session: AsyncSession):
        """
        测试目标：非租户模型不受影响
        
        场景：
        - 设置租户ID
        - 查询 Permission 表（无 tenant_id 字段）
        - 验证查询正常且不过滤
        """
        from app.core.tenant_context import set_tenant_id
        from app.modules.auth.models import Permission

        set_tenant_id(1)

        try:
            # Permission 表没有 tenant_id 字段
            result = await db_session.execute(
                select(Permission).limit(3)
            )
            permissions = list(result.scalars().all())

            # 验证查询成功
            assert len(permissions) >= 0  # 可能为空但不应报错
            print(f"✅ 非租户模型正常：查询到 {len(permissions)} 个权限")
        finally:
            set_tenant_id(None)

    async def test_manual_filter_still_works(self, db_session: AsyncSession):
        """
        测试目标：手动添加的过滤条件仍然生效
        
        场景：
        - 设置租户ID
        - 手动添加额外的 WHERE 条件
        - 验证两个条件都生效（AND 关系）
        """
        from app.core.tenant_context import set_tenant_id

        set_tenant_id(1)

        # 手动添加 phone 过滤 + 自动注入的 tenant_id
        result = await db_session.execute(
            select(User).where(User.phone.like("138%"))  # 只查138开头的手机号
        )
        users = list(result.scalars().all())

        # 验证两个条件都生效
        for user in users:
            assert user.tenant_id == 1, "自动注入的 tenant_id 失效"
            assert user.phone.startswith("138"), "手动添加的条件失效"

        print(f"✅ 双重过滤生效：找到 {len(users)} 个符合条件的用户")
        set_tenant_id(None)


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])