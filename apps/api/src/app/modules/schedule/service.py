"""
Schedule Service - 排期业务逻辑层

处理排期管理的核心业务逻辑，包括时间冲突校验。
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, NotFoundException, ValidationException
from app.modules.classroom.repository import ClassroomRepository
from app.modules.course.models import Classroom, Course
from app.modules.course.repository import CourseRepository
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.schedule.repository import ScheduleRepository
from app.modules.schedule.schemas import (
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
)
from app.modules.user.models import User
from app.modules.user.repository import UserRepository

logger = logging.getLogger(__name__)


class ScheduleService:
    """排期管理服务"""

    def __init__(self):
        self.repo = ScheduleRepository()

    async def create_schedule(
        self,
        db: AsyncSession,
        data: ScheduleCreate,
        operator_id: int | None = None,
    ) -> ScheduleResponse:
        """创建排期"""
        logger.info(
            f"[ScheduleService] 创建排期: course_id={data.course_id}, "
            f"teacher_id={data.teacher_id}, start={data.start_at}"
        )

        if data.end_at <= data.start_at:
            raise ValidationException("结束时间必须晚于开始时间")

        if data.booking_opens_at is not None and data.booking_opens_at > data.start_at:
            raise ValidationException("预约开放时间不能晚于排期开始时间")
        if data.booking_closes_at is not None and data.booking_closes_at > data.start_at:
            raise ValidationException("预约截止时间不能晚于排期开始时间")
        if data.booking_opens_at is not None and data.booking_closes_at is not None:
            if data.booking_closes_at < data.booking_opens_at:
                raise ValidationException("预约截止时间不能早于预约开放时间")

        if data.cancel_deadline is not None and data.cancel_deadline > data.start_at:
            raise ValidationException("取消截止时间不能晚于排期开始时间")

        if data.classroom_id is not None:
            classroom_repo = ClassroomRepository()
            classroom = await classroom_repo.get_by_id(db, data.classroom_id)
            if not classroom:
                raise NotFoundException("教室不存在")
            if classroom.status != 1:
                raise ValidationException("该教室正在维护中，暂不可用")

        conflicts = await self.repo.find_conflicts(
            db,
            classroom_id=data.classroom_id,
            teacher_id=data.teacher_id,
            start_at=data.start_at,
            end_at=data.end_at,
        )
        if conflicts:
            conflict_info = ", ".join(
                f"排期#{c.id}({c.start_at}~{c.end_at})" for c in conflicts
            )
            raise BusinessException(f"存在时间冲突: {conflict_info}", code=400)

        schedule_data: dict[str, Any] = {
            "course_id": data.course_id,
            "teacher_id": data.teacher_id,
            "start_at": data.start_at,
            "end_at": data.end_at,
            "capacity": data.capacity,
            "status": ScheduleStatus.NORMAL.value,
        }
        if data.classroom_id is not None:
            schedule_data["classroom_id"] = data.classroom_id
        if data.booking_opens_at is not None:
            schedule_data["booking_opens_at"] = data.booking_opens_at
        if data.booking_closes_at is not None:
            schedule_data["booking_closes_at"] = data.booking_closes_at
        if data.cancel_deadline is not None:
            schedule_data["cancel_deadline"] = data.cancel_deadline
        if data.notes is not None:
            schedule_data["notes"] = data.notes

        schedule = await self.repo.create(db, schedule_data)
        await db.commit()
        await db.refresh(schedule)

        logger.info(f"[ScheduleService] ✅ 排期创建成功: id={schedule.id}")
        return self._to_response(schedule)

    async def update_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
        data: ScheduleUpdate,
    ) -> ScheduleResponse:
        """更新排期"""
        logger.info(f"[ScheduleService] 更新排期: schedule_id={schedule_id}")

        schedule = await self.repo.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException("排期不存在")

        if schedule.status == ScheduleStatus.FINISHED.value:
            raise BusinessException("排期已完成，无法修改", code=400)

        if schedule.status == ScheduleStatus.CANCELLED.value:
            raise BusinessException("排期已取消，无法修改", code=400)

        now = datetime.now(UTC)
        if schedule.start_at < now:
            raise BusinessException("排期已开始，仅允许查看，无法修改", code=400)

        update_data: dict[str, Any] = {}

        if data.course_id is not None:
            update_data["course_id"] = data.course_id
        if data.teacher_id is not None:
            update_data["teacher_id"] = data.teacher_id
        if data.classroom_id is not None:
            update_data["classroom_id"] = data.classroom_id
        if data.capacity is not None:
            if data.capacity < schedule.booked_count:
                raise ValidationException(f"容量不能小于已预约人数({schedule.booked_count})")
            update_data["capacity"] = data.capacity
        if data.status is not None:
            update_data["status"] = data.status
        if data.notes is not None:
            update_data["notes"] = data.notes

        start_at = data.start_at if data.start_at is not None else schedule.start_at
        end_at = data.end_at if data.end_at is not None else schedule.end_at

        if data.start_at is not None:
            update_data["start_at"] = data.start_at
        if data.end_at is not None:
            update_data["end_at"] = data.end_at

        if end_at <= start_at:
            raise ValidationException("结束时间必须晚于开始时间")

        classroom_id = data.classroom_id if data.classroom_id is not None else schedule.classroom_id
        teacher_id = data.teacher_id if data.teacher_id is not None else schedule.teacher_id

        if classroom_id is not None and data.classroom_id is not None:
            classroom_repo = ClassroomRepository()
            classroom = await classroom_repo.get_by_id(db, classroom_id)
            if not classroom:
                raise NotFoundException("教室不存在")
            if classroom.status != 1:
                raise ValidationException("该教室正在维护中，暂不可用")

        conflicts = await self.repo.find_conflicts(
            db,
            classroom_id=classroom_id,
            teacher_id=teacher_id,
            start_at=start_at,
            end_at=end_at,
            exclude_id=schedule_id,
        )
        if conflicts:
            conflict_info = ", ".join(
                f"排期#{c.id}({c.start_at}~{c.end_at})" for c in conflicts
            )
            raise BusinessException(f"存在时间冲突: {conflict_info}", code=400)

        if update_data:
            schedule = await self.repo.update(db, schedule_id, update_data)

        await db.commit()
        await db.refresh(schedule)

        logger.info(f"[ScheduleService] ✅ 排期更新成功: id={schedule_id}")
        return self._to_response(schedule)

    async def cancel_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
        cancel_reason: str,
        operator_id: int,
    ) -> dict[str, Any]:
        """取消排期(含学员预约处理)"""
        logger.warning(f"[ScheduleService] 取消排期: schedule_id={schedule_id}, reason={cancel_reason}")

        schedule = await self.repo.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException("排期不存在")

        if schedule.status == ScheduleStatus.CANCELLED.value:
            raise BusinessException("排期已取消", code=400)

        if schedule.status == ScheduleStatus.FINISHED.value:
            raise BusinessException("排期已完成，无法取消", code=400)

        from app.modules.booking.models import BookingStatus
        from app.modules.booking.repository import BookingRepository
        from app.modules.membership.service import MembershipCardService

        booking_repo = BookingRepository()
        membership_card_service = MembershipCardService()

        bookings = await booking_repo.search(
            db,
            schedule_id=schedule_id,
            status=BookingStatus.BOOKED.value,
            page=1,
            page_size=1000,
        )
        booking_list = bookings[0]

        success_count = 0
        failed_bookings = []

        for booking in booking_list:
            try:
                booking.status = BookingStatus.CANCELLED.value
                booking.cancelled_at = datetime.now(UTC)
                booking.cancelled_reason = f"老师取消课程: {cancel_reason}"

                await self.repo.decrement_booked_count(db, schedule_id)

                if booking.membership_card_id:
                    tenant_id = booking.tenant_id
                    idempotency_key = f"schedule_cancel_{booking.id}_{schedule_id}"
                    try:
                        await membership_card_service.restore_credit(
                            db,
                            card_id=booking.membership_card_id,
                            tenant_id=tenant_id,
                            booking_id=booking.id,
                            idempotency_key=idempotency_key,
                        )
                    except Exception as e:
                        logger.error(f"[ScheduleService] 会员卡恢复次数失败: {e}")
                        raise

                success_count += 1
            except Exception as e:
                failed_bookings.append({
                    "booking_id": booking.id,
                    "student_id": booking.student_id,
                    "error": str(e)
                })

        update_data = {
            "status": ScheduleStatus.CANCELLED.value,
            "cancel_reason": cancel_reason,
            "cancelled_by": operator_id,
            "cancelled_at": datetime.now(UTC),
        }
        schedule = await self.repo.update(db, schedule_id, update_data)
        await db.commit()
        await db.refresh(schedule)

        logger.warning(
            f"[ScheduleService] ✅ 排期已取消: id={schedule_id}, "
            f"total_bookings={len(booking_list)}, success={success_count}, failed={len(failed_bookings)}"
        )

        return {
            "schedule_id": schedule_id,
            "total_bookings": len(booking_list),
            "success_count": success_count,
            "failed_count": len(failed_bookings),
            "failed_bookings": failed_bookings,
        }

    async def batch_delete_schedules(
        self,
        db: AsyncSession,
        schedule_ids: list[int],
        tenant_id: int,
    ) -> dict[str, Any]:
        """批量删除排期"""
        logger.warning(f"[ScheduleService] 批量删除排期: ids={schedule_ids}")

        if not schedule_ids:
            raise ValidationException("请选择要删除的排期")

        success_ids = []
        failed_ids = []
        errors = []

        for schedule_id in schedule_ids:
            try:
                schedule = await self.repo.get_by_id(db, schedule_id)
                if not schedule:
                    failed_ids.append(schedule_id)
                    errors.append(f"排期 {schedule_id} 不存在")
                    continue

                if schedule.tenant_id != tenant_id:
                    failed_ids.append(schedule_id)
                    errors.append(f"排期 {schedule_id} 无权操作")
                    continue

                # 仅对待上课状态的排期检查学员预约
                if schedule.status == ScheduleStatus.NORMAL.value and schedule.booked_count > 0:
                    failed_ids.append(schedule_id)
                    errors.append(f"排期 {schedule_id} 已有 {schedule.booked_count} 名学员预约，请先取消排期后再删除")
                    continue

                # 删除关联的预约记录（避免外键约束冲突）
                from app.modules.booking.repository import BookingRepository
                booking_repo = BookingRepository()
                await booking_repo.delete_by_schedule_id(db, schedule_id)

                await self.repo.delete(db, schedule_id, hard_delete=True)
                success_ids.append(schedule_id)
            except Exception as e:
                failed_ids.append(schedule_id)
                errors.append(f"排期 {schedule_id} 删除失败: {str(e)}")

        await db.flush()

        result = {
            "success_count": len(success_ids),
            "failed_count": len(failed_ids),
            "success_ids": success_ids,
            "failed_ids": failed_ids,
            "errors": errors,
        }

        logger.warning(f"[ScheduleService] ✅ 批量删除完成: 成功 {len(success_ids)}, 失败 {len(failed_ids)}")
        return result

    async def get_schedule_by_id(
        self,
        db: AsyncSession,
        schedule_id: int,
    ) -> ScheduleResponse:
        """获取排期详情"""
        schedule = await self.repo.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException("排期不存在")

        # 获取课程、教师和教室名称
        course_map = await self._get_course_info_map(db, [schedule.course_id])
        teacher_map = await self._get_teacher_info_map(db, [schedule.teacher_id])
        classroom_map = await self._get_classroom_info_map(db, [schedule.classroom_id] if schedule.classroom_id else [])

        return self._to_response(
            schedule,
            course_map.get(schedule.course_id, {}).get("name"),
            course_map.get(schedule.course_id, {}).get("course_type_code"),
            teacher_map.get(schedule.teacher_id),
            classroom_map.get(schedule.classroom_id),
        )

    async def list_schedules(
        self,
        db: AsyncSession,
        *,
        course_id: int | None = None,
        course_name: str | None = None,
        category: str | None = None,
        course_type_code: str | None = None,
        teacher_id: int | None = None,
        classroom_id: int | None = None,
        status: int | None = None,
        display_status: int | None = None,
        start_from: datetime | None = None,
        start_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ScheduleListResponse:
        """获取排期列表（分页）"""
        items, total = await self.repo.search(
            db,
            course_id=course_id,
            course_name=course_name,
            category=category,
            course_type_code=course_type_code,
            teacher_id=teacher_id,
            classroom_id=classroom_id,
            status=status,
            start_from=start_from,
            start_to=start_to,
            page=page,
            page_size=page_size,
        )

        # 获取课程、教师和教室信息
        course_ids = list({s.course_id for s in items})
        teacher_ids = list({s.teacher_id for s in items})
        classroom_ids = list({s.classroom_id for s in items if s.classroom_id})

        course_map = await self._get_course_info_map(db, course_ids)
        teacher_map = await self._get_teacher_info_map(db, teacher_ids)
        classroom_map = await self._get_classroom_info_map(db, classroom_ids)

        # 构建响应对象列表
        response_items = [
            self._to_response(
                s,
                course_map.get(s.course_id, {}).get("name"),
                course_map.get(s.course_id, {}).get("course_type_code"),
                teacher_map.get(s.teacher_id),
                classroom_map.get(s.classroom_id),
            )
            for s in items
        ]

        # 根据 display_status 过滤（display_status 是计算字段，不在 DB 中）
        if display_status is not None:
            response_items = [item for item in response_items if item.display_status == display_status]
            total = len(response_items)

        return ScheduleListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=response_items,
        )

    async def _get_course_info_map(self, db: AsyncSession, course_ids: list[int]) -> dict[int, dict]:
        """批量获取课程信息映射（包含名称和类型代码）"""
        if not course_ids:
            return {}

        CourseRepository()
        query = select(Course).where(Course.id.in_(course_ids))
        result = await db.execute(query)
        courses = result.scalars().all()

        return {
            course.id: {"name": course.name, "course_type_code": course.course_type_code}
            for course in courses
        }

    async def _get_teacher_info_map(self, db: AsyncSession, teacher_ids: list[int]) -> dict[int, str]:
        """批量获取教师信息映射"""
        if not teacher_ids:
            return {}

        UserRepository()
        query = select(User).where(User.id.in_(teacher_ids))
        result = await db.execute(query)
        users = result.scalars().all()

        return {
            user.id: user.nickname or user.phone
            for user in users
        }

    async def _get_classroom_info_map(self, db: AsyncSession, classroom_ids: list[int]) -> dict[int, str]:
        """批量获取教室信息映射"""
        if not classroom_ids:
            return {}

        ClassroomRepository()
        query = select(Classroom).where(Classroom.id.in_(classroom_ids))
        result = await db.execute(query)
        classrooms = result.scalars().all()

        return {
            classroom.id: classroom.name
            for classroom in classrooms
        }

    def _to_response(
        self,
        schedule: CourseSchedule,
        course_name: str | None = None,
        course_type_code: str | None = None,
        teacher_name: str | None = None,
        classroom_name: str | None = None,
    ) -> ScheduleResponse:
        """将 ORM 模型转换为响应对象"""
        # 计算显示状态：1待上课/2上课中/3已取消/4已完成
        now = datetime.now(UTC)
        if schedule.status == ScheduleStatus.CANCELLED.value:
            display_status = 3  # 已取消
        elif schedule.status == ScheduleStatus.FINISHED.value:
            display_status = 4  # 已完成
        elif schedule.status == ScheduleStatus.NORMAL.value:
            if schedule.end_at < now:
                display_status = 4  # 已完成（时间已过但未标记）
            elif schedule.start_at <= now <= schedule.end_at:
                display_status = 2  # 上课中
            else:
                display_status = 1  # 待上课
        else:
            display_status = schedule.status

        return ScheduleResponse(
            id=schedule.id,
            public_id=str(schedule.public_id),
            tenant_id=schedule.tenant_id,
            course_id=schedule.course_id,
            teacher_id=schedule.teacher_id,
            classroom_id=schedule.classroom_id,
            start_at=schedule.start_at,
            end_at=schedule.end_at,
            capacity=schedule.capacity,
            booked_count=schedule.booked_count,
            booking_opens_at=schedule.booking_opens_at,
            booking_closes_at=schedule.booking_closes_at,
            cancel_deadline=schedule.cancel_deadline,
            status=schedule.status,
            display_status=display_status,
            notes=schedule.notes,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            course_name=course_name,
            course_type_code=course_type_code,
            teacher_name=teacher_name,
            classroom_name=classroom_name,
        )

    async def batch_create_schedules(
        self,
        db: AsyncSession,
        items: list[ScheduleCreate],
        operator_id: int | None = None,
    ) -> list[ScheduleResponse]:
        """批量创建排期"""
        logger.info(f"[ScheduleService] 批量创建排期: count={len(items)}")

        if not items:
            raise ValidationException("排期列表不能为空")

        # 收集所有需要检查的时间范围
        time_ranges = []
        teacher_ids = set()
        classroom_ids = set()

        for idx, data in enumerate(items):
            if data.end_at <= data.start_at:
                raise ValidationException(f"第 {idx + 1} 个排期: 结束时间必须晚于开始时间")
            if data.booking_opens_at is not None and data.booking_opens_at > data.start_at:
                raise ValidationException(f"第 {idx + 1} 个排期: 预约开放时间不能晚于排期开始时间")
            if data.booking_closes_at is not None and data.booking_closes_at > data.start_at:
                raise ValidationException(f"第 {idx + 1} 个排期: 预约截止时间不能晚于排期开始时间")
            if data.booking_opens_at is not None and data.booking_closes_at is not None:
                if data.booking_closes_at < data.booking_opens_at:
                    raise ValidationException(f"第 {idx + 1} 个排期: 预约截止时间不能早于预约开放时间")
            if data.cancel_deadline is not None and data.cancel_deadline > data.start_at:
                raise ValidationException(f"第 {idx + 1} 个排期: 取消截止时间不能晚于排期开始时间")
            time_ranges.append({
                'start_at': data.start_at,
                'end_at': data.end_at,
                'teacher_id': data.teacher_id,
                'classroom_id': data.classroom_id,
            })
            teacher_ids.add(data.teacher_id)
            if data.classroom_id:
                classroom_ids.add(data.classroom_id)

        # 检查时间冲突
        for item in time_ranges:
            conflicts = await self.repo.find_conflicts(
                db,
                classroom_id=item['classroom_id'],
                teacher_id=item['teacher_id'],
                start_at=item['start_at'],
                end_at=item['end_at'],
            )
            if conflicts:
                conflict_info = f"{item['start_at']}~{item['end_at']}"
                raise BusinessException(f"存在时间冲突: {conflict_info}", code=400)

        # 批量创建
        results = []
        for data in items:
            schedule = await self.repo.create(db, data)
            results.append(self._to_response(schedule))

        await db.commit()

        logger.info(f"[ScheduleService] ✅ 批量创建排期成功: count={len(results)}")
        return results
