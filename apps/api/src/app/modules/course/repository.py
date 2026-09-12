"""
Course Repository - 课程数据访问层

提供课程相关的数据库操作，继承 TenantAwareRepository 实现自动多租户隔离。
"""


from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import TenantAwareRepository
from app.modules.course.models import Course, CourseType


class CourseTypeRepository(TenantAwareRepository[CourseType]):
    """课程类型数据访问层"""

    model_class = CourseType

    async def list_types(
        self,
        db: AsyncSession,
        *,
        status: int | None = None,
    ) -> tuple[list[CourseType], int]:
        """获取课程类型列表"""
        base_query = select(CourseType)
        count_query = select(func.count()).select_from(CourseType)

        if status is not None:
            base_query = base_query.where(CourseType.status == status)
            count_query = count_query.where(CourseType.status == status)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            base_query = base_query.where(CourseType.tenant_id == tenant_id)
            count_query = count_query.where(CourseType.tenant_id == tenant_id)

        base_query = base_query.order_by(CourseType.sort_order.asc(), CourseType.created_at.desc())

        result = await db.execute(base_query)
        items = list(result.scalars().all())

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        return items, total

    async def exists_by_code(
        self,
        db: AsyncSession,
        code: str,
        *,
        exclude_id: int | None = None,
    ) -> bool:
        """检查类型代码是否已存在"""
        query = select(func.count()).select_from(CourseType).where(
            CourseType.code == code,
        )

        if exclude_id:
            query = query.where(CourseType.id != exclude_id)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(CourseType.tenant_id == tenant_id)

        result = await db.execute(query)
        count = result.scalar() or 0
        return count > 0

    async def exists_by_name(
        self,
        db: AsyncSession,
        name: str,
        *,
        exclude_id: int | None = None,
    ) -> bool:
        """检查类型名称是否已存在"""
        query = select(func.count()).select_from(CourseType).where(
            CourseType.name == name,
        )

        if exclude_id:
            query = query.where(CourseType.id != exclude_id)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(CourseType.tenant_id == tenant_id)

        result = await db.execute(query)
        count = result.scalar() or 0
        return count > 0

    async def get_by_code(
        self,
        db: AsyncSession,
        code: str,
    ) -> CourseType | None:
        """通过代码获取课程类型"""
        query = select(CourseType).where(CourseType.code == code)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(CourseType.tenant_id == tenant_id)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def count_courses_by_type(
        self,
        db: AsyncSession,
        course_type_code: str,
    ) -> int:
        """统计使用该类型的课程数量"""
        query = select(func.count()).select_from(Course).where(
            Course.course_type_code == course_type_code,
            Course.deleted_at.is_(None),
        )

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Course.tenant_id == tenant_id)

        result = await db.execute(query)
        return result.scalar() or 0


class CourseRepository(TenantAwareRepository[Course]):
    """课程数据访问层"""

    model_class = Course

    async def search(
        self,
        db: AsyncSession,
        *,
        keyword: str | None = None,
        category: str | None = None,
        level: str | None = None,
        status: int | None = None,
        course_type_code: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Course], int]:
        """搜索课程（支持关键词、分类、等级、状态、课程类型筛选、分页）"""
        base_query = select(Course).where(Course.deleted_at.is_(None))
        count_query = select(func.count()).select_from(Course).where(Course.deleted_at.is_(None))

        if keyword:
            keyword_pattern = f"%{keyword}%"
            search_condition = or_(
                Course.name.ilike(keyword_pattern),
                Course.description.ilike(keyword_pattern),
            )
            base_query = base_query.where(search_condition)
            count_query = count_query.where(search_condition)

        if category:
            base_query = base_query.where(Course.category == category)
            count_query = count_query.where(Course.category == category)

        if level:
            base_query = base_query.where(Course.level == level)
            count_query = count_query.where(Course.level == level)

        if status is not None:
            base_query = base_query.where(Course.status == status)
            count_query = count_query.where(Course.status == status)

        if course_type_code:
            base_query = base_query.where(Course.course_type_code == course_type_code)
            count_query = count_query.where(Course.course_type_code == course_type_code)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            base_query = base_query.where(Course.tenant_id == tenant_id)
            count_query = count_query.where(Course.tenant_id == tenant_id)

        base_query = base_query.order_by(Course.created_at.desc())

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
        exclude_id: int | None = None,
    ) -> bool:
        """检查课程名称是否已存在"""
        query = select(func.count()).select_from(Course).where(
            Course.name == name,
            Course.deleted_at.is_(None),
        )

        if exclude_id:
            query = query.where(Course.id != exclude_id)

        from app.core.tenant_context import get_tenant_id
        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(Course.tenant_id == tenant_id)

        result = await db.execute(query)
        count = result.scalar() or 0
        return count > 0