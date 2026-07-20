"""
Classroom Repository - 教室数据访问层

提供教室相关的数据库操作，继承 TenantAwareRepository 实现自动多租户隔离。
"""

from typing import Optional, List, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.course.models import Classroom, ClassroomStatus


class ClassroomRepository(TenantAwareRepository[Classroom]):
    """教室数据访问层"""

    model_class = Classroom

    async def search(
        self,
        db: AsyncSession,
        *,
        keyword: Optional[str] = None,
        status: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Classroom], int]:
        """搜索教室"""
        base_query = select(Classroom)
        count_query = select(func.count()).select_from(Classroom)

        if keyword:
            keyword_pattern = f"%{keyword}%"
            base_query = base_query.where(Classroom.name.ilike(keyword_pattern))
            count_query = count_query.where(Classroom.name.ilike(keyword_pattern))

        if status is not None:
            base_query = base_query.where(Classroom.status == status)
            count_query = count_query.where(Classroom.status == status)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            base_query = base_query.where(Classroom.tenant_id == tenant_id)
            count_query = count_query.where(Classroom.tenant_id == tenant_id)

        base_query = base_query.order_by(Classroom.created_at.desc())

        offset_val = (page - 1) * page_size
        base_query = base_query.offset(offset_val).limit(page_size)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        result = await db.execute(base_query)
        items = list(result.scalars().all())

        return items, total

    async def exists_by_name(
        self,
        db: AsyncSession,
        name: str,
        *,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """检查教室名称是否已存在"""
        query = select(func.count()).select_from(Classroom).where(
            Classroom.name == name,
        )

        if exclude_id:
            query = query.where(Classroom.id != exclude_id)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Classroom.tenant_id == tenant_id)

        result = await db.execute(query)
        count = result.scalar() or 0
        return count > 0