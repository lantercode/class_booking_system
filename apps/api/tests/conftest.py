"""
T02 测试配置 - pytest 全局 Fixture

提供：
- 数据库会话 (db_session)
- 测试事务自动回滚（不污染真实数据）
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.tenant.models import Tenant, TenantStatus
from app.modules.user.models import User, UserStatus
from app.modules.auth.models import Role, Permission

# 使用与主应用相同的配置
settings = get_settings()
TEST_DATABASE_URL = settings.DATABASE_URL

# 创建测试专用引擎
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,  # 测试时不打印 SQL
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="function")
async def db_session():
    """
    数据库 Session fixture - 每个测试函数使用独立的 session

    特性：
    - 测试前开始事务
    - 测试后回滚事务（不污染数据库）
    - 可以安全地增删改查
    """
    async with TestSessionLocal() as session:
        await session.begin()

        try:
            yield session
        finally:
            await session.rollback()
            await session.close()