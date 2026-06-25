
# 数据库连接和会话管理的核心模块，为整个Fast API应用提供统一的数据库访问层
# import
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator
from app.core.config import get_settings

# 模块级单例（engine + sessionmaker）
settings = get_settings()
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG,
    pool_pre_ping=True
)
SessionLocal = async_sessionmaker(
    engine, 
    expire_on_commit=False
)

# fastAPI依赖函数
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

