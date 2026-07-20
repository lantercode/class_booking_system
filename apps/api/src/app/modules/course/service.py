"""
Course Service - 课程业务逻辑层

处理课程管理的核心业务逻辑，包括：
- 课程创建/更新/删除（软删除）
- 课程列表查询（分页、筛选）
- 课程名称唯一性校验
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.course.repository import CourseRepository
from app.modules.course.models import Course, CourseStatus
from app.modules.course.schemas import (
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    CourseListResponse,
)
from app.core.exceptions import ValidationException, NotFoundException

logger = logging.getLogger(__name__)


class CourseService:
    """课程管理服务"""

    def __init__(self):
        self.repo = CourseRepository()

    async def create_course(
        self,
        db: AsyncSession,
        data: CourseCreate,
        operator_id: Optional[int] = None,
    ) -> CourseResponse:
        """创建课程"""
        logger.info(f"[CourseService] 创建课程: name={data.name}")

        if await self.repo.exists_by_name(db, data.name):
            raise ValidationException("课程名称已存在")

        course_data: Dict[str, Any] = {
            "name": data.name,
            "duration_minutes": data.duration_minutes,
            "max_capacity": data.max_capacity,
            "price": data.price,
            "required_credits": data.required_credits,
            "status": CourseStatus.ONLINE.value,
        }

        if data.category is not None:
            course_data["category"] = data.category
        if data.level is not None:
            course_data["level"] = data.level
        if data.cover_url is not None:
            course_data["cover_url"] = data.cover_url
        if data.description is not None:
            course_data["description"] = data.description

        course = await self.repo.create(db, course_data)
        await db.commit()
        await db.refresh(course)

        logger.info(f"[CourseService] ✅ 课程创建成功: id={course.id}")
        return self._to_response(course)

    async def update_course(
        self,
        db: AsyncSession,
        course_id: int,
        data: CourseUpdate,
    ) -> CourseResponse:
        """更新课程"""
        logger.info(f"[CourseService] 更新课程: course_id={course_id}")

        course = await self.repo.get_by_id(db, course_id)
        if not course:
            raise NotFoundException("课程不存在")

        update_data: Dict[str, Any] = {}

        if data.name is not None and data.name != course.name:
            if await self.repo.exists_by_name(db, data.name, exclude_id=course_id):
                raise ValidationException("课程名称已存在")
            update_data["name"] = data.name
        if data.category is not None:
            update_data["category"] = data.category
        if data.level is not None:
            update_data["level"] = data.level
        if data.cover_url is not None:
            update_data["cover_url"] = data.cover_url
        if data.description is not None:
            update_data["description"] = data.description
        if data.duration_minutes is not None:
            update_data["duration_minutes"] = data.duration_minutes
        if data.max_capacity is not None:
            update_data["max_capacity"] = data.max_capacity
        if data.price is not None:
            update_data["price"] = data.price
        if data.required_credits is not None:
            update_data["required_credits"] = data.required_credits
        if data.status is not None:
            update_data["status"] = data.status

        if update_data:
            course = await self.repo.update(db, course_id, update_data)

        await db.commit()
        await db.refresh(course)

        logger.info(f"[CourseService] ✅ 课程更新成功: id={course_id}")
        return self._to_response(course)

    async def delete_course(
        self,
        db: AsyncSession,
        course_id: int,
    ) -> bool:
        """删除课程（软删除）"""
        logger.warning(f"[CourseService] 删除课程: course_id={course_id}")

        success = await self.repo.delete(db, course_id)
        if not success:
            raise NotFoundException("课程不存在或已删除")

        logger.warning(f"[CourseService] ✅ 课程删除成功: id={course_id}")
        return True

    async def get_course_by_id(
        self,
        db: AsyncSession,
        course_id: int,
    ) -> CourseResponse:
        """获取课程详情"""
        course = await self.repo.get_by_id(db, course_id)
        if not course:
            raise NotFoundException("课程不存在")
        return self._to_response(course)

    async def list_courses(
        self,
        db: AsyncSession,
        *,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        level: Optional[str] = None,
        status: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> CourseListResponse:
        """获取课程列表（分页）"""
        items, total = await self.repo.search(
            db,
            keyword=keyword,
            category=category,
            level=level,
            status=status,
            page=page,
            page_size=page_size,
        )

        return CourseListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[self._to_response(c) for c in items],
        )

    def _to_response(self, course: Course) -> CourseResponse:
        """将 ORM 模型转换为响应对象"""
        return CourseResponse(
            id=course.id,
            public_id=str(course.public_id),
            tenant_id=course.tenant_id,
            name=course.name,
            category=course.category,
            level=course.level,
            cover_url=course.cover_url,
            description=course.description,
            duration_minutes=course.duration_minutes,
            max_capacity=course.max_capacity,
            price=float(course.price),
            required_credits=course.required_credits,
            status=course.status,
            created_at=course.created_at,
            updated_at=course.updated_at,
        )