"""
Classroom Service - 教室业务逻辑层

处理教室管理的核心业务逻辑。
"""

import logging
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.classroom.repository import ClassroomRepository
from app.modules.course.models import Classroom, ClassroomStatus
from app.modules.classroom.schemas import (
    ClassroomCreate,
    ClassroomUpdate,
    ClassroomResponse,
    ClassroomListResponse,
)
from app.core.exceptions import ValidationException, NotFoundException

logger = logging.getLogger(__name__)


class ClassroomService:
    """教室管理服务"""

    def __init__(self):
        self.repo = ClassroomRepository()

    async def create_classroom(
        self,
        db: AsyncSession,
        data: ClassroomCreate,
        operator_id: Optional[int] = None,
    ) -> ClassroomResponse:
        """创建教室"""
        logger.info(f"[ClassroomService] 创建教室: name={data.name}")

        if await self.repo.exists_by_name(db, data.name):
            raise ValidationException("教室名称已存在")

        classroom_data: Dict[str, Any] = {
            "name": data.name,
            "capacity": data.capacity,
            "status": ClassroomStatus.ACTIVE.value,
        }
        if data.equipment:
            classroom_data["equipment"] = data.equipment

        classroom = await self.repo.create(db, classroom_data)
        await db.commit()
        await db.refresh(classroom)

        logger.info(f"[ClassroomService] ✅ 教室创建成功: id={classroom.id}")
        return self._to_response(classroom)

    async def update_classroom(
        self,
        db: AsyncSession,
        classroom_id: int,
        data: ClassroomUpdate,
    ) -> ClassroomResponse:
        """更新教室"""
        logger.info(f"[ClassroomService] 更新教室: classroom_id={classroom_id}")

        classroom = await self.repo.get_by_id(db, classroom_id)
        if not classroom:
            raise NotFoundException("教室不存在")

        update_data: Dict[str, Any] = {}

        if data.name is not None and data.name != classroom.name:
            if await self.repo.exists_by_name(db, data.name, exclude_id=classroom_id):
                raise ValidationException("教室名称已存在")
            update_data["name"] = data.name
        if data.capacity is not None:
            update_data["capacity"] = data.capacity
        if data.equipment is not None:
            update_data["equipment"] = data.equipment
        if data.status is not None:
            update_data["status"] = data.status

        if update_data:
            classroom = await self.repo.update(db, classroom_id, update_data)

        await db.commit()
        await db.refresh(classroom)

        logger.info(f"[ClassroomService] ✅ 教室更新成功: id={classroom_id}")
        return self._to_response(classroom)

    async def delete_classroom(
        self,
        db: AsyncSession,
        classroom_id: int,
    ) -> bool:
        """删除教室"""
        logger.warning(f"[ClassroomService] 删除教室: classroom_id={classroom_id}")

        classroom = await self.repo.get_by_id(db, classroom_id)
        if not classroom:
            raise NotFoundException("教室不存在")

        from app.modules.schedule.models import CourseSchedule, ScheduleStatus
        from datetime import datetime, timezone
        from sqlalchemy import select
        from app.core.tenant_context import get_tenant_id as _get_tenant_id

        tenant_id = _get_tenant_id()
        active_schedule_query = select(CourseSchedule).where(
            CourseSchedule.classroom_id == classroom_id,
            CourseSchedule.status == ScheduleStatus.NORMAL.value,
            CourseSchedule.start_at > datetime.now(timezone.utc),
        )
        if tenant_id:
            active_schedule_query = active_schedule_query.where(
                CourseSchedule.tenant_id == tenant_id,
            )

        result = await db.execute(active_schedule_query.limit(1))
        if result.scalar_one_or_none():
            raise ValidationException("该教室有未完成的排课，请先取消或完成排课后再删除")

        success = await self.repo.delete(db, classroom_id)
        if not success:
            raise NotFoundException("教室不存在")

        logger.warning(f"[ClassroomService] ✅ 教室删除成功: id={classroom_id}")
        return True

    async def get_classroom_by_id(
        self,
        db: AsyncSession,
        classroom_id: int,
    ) -> ClassroomResponse:
        """获取教室详情"""
        classroom = await self.repo.get_by_id(db, classroom_id)
        if not classroom:
            raise NotFoundException("教室不存在")
        return self._to_response(classroom)

    async def list_classrooms(
        self,
        db: AsyncSession,
        *,
        keyword: Optional[str] = None,
        status: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ClassroomListResponse:
        """获取教室列表（分页）"""
        items, total = await self.repo.search(
            db,
            keyword=keyword,
            status=status,
            page=page,
            page_size=page_size,
        )

        return ClassroomListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[self._to_response(c) for c in items],
        )

    def _to_response(self, classroom: Classroom) -> ClassroomResponse:
        """将 ORM 模型转换为响应对象"""
        return ClassroomResponse(
            id=classroom.id,
            tenant_id=classroom.tenant_id,
            name=classroom.name,
            capacity=classroom.capacity,
            equipment=classroom.equipment,
            status=classroom.status,
            created_at=classroom.created_at,
            updated_at=classroom.updated_at,
        )