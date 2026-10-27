"""
Upload Repository - 文件对象数据访问层

继承 TenantAwareRepository，所有查询自动注入 tenant_id 隔离。
"""

from sqlalchemy import func, select, union_all

from app.core.base_repository import TenantAwareRepository
from app.modules.course.models import Classroom, Course, CourseCategory
from app.modules.upload.models import FileObject
from app.modules.user.models import User


class FileObjectRepository(TenantAwareRepository[FileObject]):
    """file_objects 表 Repository。

    TenantAwareRepository.create() 会自动从 ContextVar 取 tenant_id 注入，
    上层 Service 调用时无需手动传 tenant_id。
    """

    model_class = FileObject

    async def get_by_object_key(
        self,
        db,
        object_key: str,
        *,
        include_deleted: bool = False,
    ) -> FileObject | None:
        """按 object_key 查询审计记录（自动附加当前租户过滤）。"""
        return await self.get_one(
            db,
            filters={"object_key": object_key},
            include_deleted=include_deleted,
        )

    async def count_references(self, db, object_key: str) -> int:
        """统计业务表中引用该 object_key 的记录数（只读引用检查）。

        仅用于删除前的保护性判断：被引用则不允许删除。
        各业务表均带 tenant_id，ORM 事件会自动注入当前租户过滤，
        因此不会误判其他租户的引用。
        """
        statements = [
            select(User.id).where(User.avatar_url == object_key),
            select(CourseCategory.id).where(CourseCategory.icon_url == object_key),
            select(Classroom.id).where(Classroom.cover_image_url == object_key),
            select(Course.id).where(Course.cover_url == object_key),
        ]
        counted = select(func.count()).select_from(union_all(*statements).subquery())
        result = await db.execute(counted)
        return int(result.scalar() or 0)
