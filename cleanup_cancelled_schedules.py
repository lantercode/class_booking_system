import asyncio
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 数据库连接配置
DATABASE_URL = "postgresql+asyncpg://dance:dance_dev_pass@localhost:5432/dance_saas"

# 创建异步引擎
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def cleanup_cancelled_schedules():
    async with async_session() as session:
        async with session.begin():
            # 先查询已取消的排期数量
            count_query = select(func.count()).select_from(table('course_schedules')).where(table('course_schedules').c.status == 2)
            result = await session.execute(count_query)
            count = result.scalar()
            print(f"发现 {count} 条已取消的排期")
            
            if count > 0:
                # 删除已取消的排期
                delete_stmt = delete(table('course_schedules')).where(table('course_schedules').c.status == 2)
                result = await session.execute(delete_stmt)
                await session.commit()
                print(f"已成功删除 {result.rowcount} 条已取消的排期")
            else:
                print("没有需要清理的已取消排期")

from sqlalchemy import func, table

asyncio.run(cleanup_cancelled_schedules())