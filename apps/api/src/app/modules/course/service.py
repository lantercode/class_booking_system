"""
Course Service - 课程业务逻辑层

处理课程管理的核心业务逻辑，包括：
- 课程类型管理（CRUD）
- 课程创建/更新/删除（软删除）
- 课程列表查询（分页、筛选）
- 课程名称唯一性校验
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, NotFoundException, ValidationException
from app.modules.course.models import Course, CourseStatus, CourseType, CourseTypeStatus
from app.modules.course.repository import CourseRepository, CourseTypeRepository
from app.modules.course.schemas import (
    CourseCreate,
    CourseListResponse,
    CourseResponse,
    CourseTypeCreate,
    CourseTypeListResponse,
    CourseTypeResponse,
    CourseTypeUpdate,
    CourseUpdate,
)

logger = logging.getLogger(__name__)


class CourseTypeService:
    """课程类型管理服务"""

    def __init__(self):
        self.repo = CourseTypeRepository()
        self.course_repo = CourseRepository()

    async def create_type(
        self,
        db: AsyncSession,
        data: CourseTypeCreate,
        tenant_id: int,
    ) -> CourseType:
        """创建课程类型"""
        logger.info(f"[CourseTypeService] 创建课程类型: name={data.name}, code={data.code}")

        if await self.repo.exists_by_code(db, data.code):
            raise ValidationException("类型代码已存在")

        if await self.repo.exists_by_name(db, data.name):
            raise ValidationException("类型名称已存在")

        type_data: dict[str, Any] = {
            "name": data.name,
            "code": data.code,
            "sort_order": data.sort_order,
            "status": data.status,
        }

        if data.description is not None:
            type_data["description"] = data.description
        if data.required_card_types is not None:
            type_data["required_card_types"] = data.required_card_types

        course_type = await self.repo.create(db, type_data)
        await db.flush()

        logger.info(f"[CourseTypeService] ✅ 课程类型创建成功: id={course_type.id}")
        return course_type

    async def update_type(
        self,
        db: AsyncSession,
        type_id: int,
        data: CourseTypeUpdate,
        tenant_id: int,
    ) -> CourseType:
        """更新课程类型"""
        logger.info(f"[CourseTypeService] 更新课程类型: type_id={type_id}")

        course_type = await self.repo.get_by_id(db, type_id)
        if not course_type:
            raise NotFoundException("课程类型不存在")

        if course_type.tenant_id != tenant_id:
            raise ValidationException("无权操作此课程类型")

        update_data: dict[str, Any] = {}

        if data.name is not None and data.name != course_type.name:
            if await self.repo.exists_by_name(db, data.name, exclude_id=type_id):
                raise ValidationException("类型名称已存在")
            update_data["name"] = data.name

        if data.code is not None and data.code != course_type.code:
            if await self.repo.exists_by_code(db, data.code, exclude_id=type_id):
                raise ValidationException("类型代码已存在")
            update_data["code"] = data.code

        if data.description is not None:
            update_data["description"] = data.description
        if data.required_card_types is not None:
            update_data["required_card_types"] = data.required_card_types
        if data.sort_order is not None:
            update_data["sort_order"] = data.sort_order
        if data.status is not None:
            update_data["status"] = data.status

        if update_data:
            course_type = await self.repo.update(db, type_id, update_data)

        await db.flush()
        await db.refresh(course_type)

        logger.info(f"[CourseTypeService] ✅ 课程类型更新成功: id={type_id}")
        return course_type

    async def delete_type(
        self,
        db: AsyncSession,
        type_id: int,
        tenant_id: int,
    ) -> bool:
        """删除课程类型（检查是否有课程使用）"""
        logger.warning(f"[CourseTypeService] 删除课程类型: type_id={type_id}")

        course_type = await self.repo.get_by_id(db, type_id)
        if not course_type:
            raise NotFoundException("课程类型不存在")

        if course_type.tenant_id != tenant_id:
            raise ValidationException("无权操作此课程类型")

        course_count = await self.repo.count_courses_by_type(db, course_type.code)
        if course_count > 0:
            raise BusinessException(f"该课程类型正在被 {course_count} 个课程使用，无法删除")

        await self.repo.delete(db, type_id)
        await db.flush()

        logger.warning(f"[CourseTypeService] ✅ 课程类型删除成功: id={type_id}")
        return True

    async def get_type_by_id(
        self,
        db: AsyncSession,
        type_id: int,
        tenant_id: int,
    ) -> CourseType:
        """获取课程类型详情"""
        course_type = await self.repo.get_by_id(db, type_id)
        if not course_type:
            raise NotFoundException("课程类型不存在")

        if course_type.tenant_id != tenant_id:
            raise ValidationException("无权访问此课程类型")

        return course_type

    async def list_types(
        self,
        db: AsyncSession,
        tenant_id: int,
        *,
        status: int | None = None,
    ) -> CourseTypeListResponse:
        """获取课程类型列表"""
        items, total = await self.repo.list_types(db, status=status)

        # 为每个类型统计课程数量
        type_responses = []
        for t in items:
            course_count = await self.repo.count_courses_by_type(db, t.code)
            resp = self._to_response(t)
            resp.course_count = course_count
            type_responses.append(resp)

        return CourseTypeListResponse(
            total=total,
            items=type_responses,
        )

    def _to_response(self, course_type: CourseType) -> CourseTypeResponse:
        """将 ORM 模型转换为响应对象"""
        return CourseTypeResponse(
            id=course_type.id,
            public_id=str(course_type.public_id),
            tenant_id=course_type.tenant_id,
            name=course_type.name,
            code=course_type.code,
            description=course_type.description,
            required_card_types=course_type.required_card_types,
            sort_order=course_type.sort_order,
            status=course_type.status,
            course_count=0,
            created_at=course_type.created_at,
            updated_at=course_type.updated_at,
        )


class CourseService:
    """课程管理服务"""

    def __init__(self):
        self.repo = CourseRepository()
        self.type_repo = CourseTypeRepository()

    async def create_course(
        self,
        db: AsyncSession,
        data: CourseCreate,
        operator_id: int | None = None,
    ) -> CourseResponse:
        """创建课程"""
        logger.info(f"[CourseService] 创建课程: name={data.name}")

        if await self.repo.exists_by_name(db, data.name):
            raise ValidationException("课程名称已存在")

        course_type = await self.type_repo.get_by_code(db, data.course_type_code)
        if not course_type:
            raise ValidationException(f"课程类型不存在: {data.course_type_code}")

        if course_type.status != CourseTypeStatus.ACTIVE.value:
            raise ValidationException(f"课程类型已禁用: {course_type.name}")

        course_data: dict[str, Any] = {
            "name": data.name,
            "category": data.category,
            "course_type_code": data.course_type_code,
            "level": data.level,
            "duration_minutes": data.duration_minutes,
            "price": data.price,
            "required_credits": data.required_credits,
            "status": CourseStatus.ONLINE.value,
        }

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

        update_data: dict[str, Any] = {}

        if data.name is not None and data.name != course.name:
            if await self.repo.exists_by_name(db, data.name, exclude_id=course_id):
                raise ValidationException("课程名称已存在")
            update_data["name"] = data.name
        if data.category is not None:
            update_data["category"] = data.category
        if data.course_type_code is not None and data.course_type_code != course.course_type_code:
            course_type = await self.type_repo.get_by_code(db, data.course_type_code)
            if not course_type:
                raise ValidationException(f"课程类型不存在: {data.course_type_code}")
            if course_type.status != CourseTypeStatus.ACTIVE.value:
                raise ValidationException(f"课程类型已禁用: {course_type.name}")
            update_data["course_type_code"] = data.course_type_code
        if data.level is not None:
            update_data["level"] = data.level
        if data.cover_url is not None:
            update_data["cover_url"] = data.cover_url
        if data.description is not None:
            update_data["description"] = data.description
        if data.duration_minutes is not None:
            update_data["duration_minutes"] = data.duration_minutes
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
        keyword: str | None = None,
        category: str | None = None,
        level: str | None = None,
        status: int | None = None,
        course_type_code: str | None = None,
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
            course_type_code=course_type_code,
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
            course_type_code=course.course_type_code,
            level=course.level,
            cover_url=course.cover_url,
            description=course.description,
            duration_minutes=course.duration_minutes,
            price=float(course.price),
            required_credits=course.required_credits,
            status=course.status,
            created_at=course.created_at,
            updated_at=course.updated_at,
        )


course_type_service = CourseTypeService()