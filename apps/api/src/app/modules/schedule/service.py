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

# F4.5：SERIALIZABLE 下并发创建的最大尝试次数（首次 + 重试）。
_CREATE_SERIALIZABLE_MAX_ATTEMPTS = 3


def _is_serialization_failure(exc: BaseException) -> bool:
    """判断异常是否为 PostgreSQL SerializationFailure（SQLSTATE 40001）。

    asyncpg 的 ``SerializationError`` 经 SQLAlchemy 包装为 ``DBAPIError``
    （``orig`` 携带原始驱动异常）；直连/测试场景也可能抛出原生异常，两者都识别。
    """
    orig = getattr(exc, "orig", exc)
    if getattr(orig, "sqlstate", None) == "40001":
        return True
    return "could not serialize access" in str(orig)


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
        """创建排期

        F4.5：冲突检查与插入在同一 SERIALIZABLE 事务内完成，避免并发下产生
        时间重叠排期。若因并发冲突导致 SerializationFailure，自动重试；
        重试耗尽后返回友好业务错误。
        """
        logger.info(
            f"[ScheduleService] 创建排期: course_id={data.course_id}, "
            f"teacher_id={data.teacher_id}, start={data.start_at}"
        )

        # ---------- 纯校验（无状态依赖，放在重试外） ----------
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

        # ---------- 事务内冲突检查 + 插入（SERIALIZABLE + 重试） ----------
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
        if data.preview_content is not None:
            schedule_data["preview_content"] = data.preview_content
            schedule_data["preview_updated_at"] = datetime.now(UTC)

        schedule: CourseSchedule | None = None
        for attempt in range(1, _CREATE_SERIALIZABLE_MAX_ATTEMPTS + 1):
            try:
                # 关闭上游（如 RBAC）可能已开启的只读事务，确保连接上不存在
                # 活动事务；随后通过 SQLAlchemy 官方入口把本次创建事务提升为
                # SERIALIZABLE（底层由 asyncpg 原生事务 API 发出
                # ``BEGIN ISOLATION LEVEL SERIALIZABLE``，相较裸发 ``BEGIN``
                # 不会触发 PostgreSQL "there is already a transaction in
                # progress" 告警，重试时 rollback 后可安全重复提升）。
                try:
                    await db.rollback()
                except Exception:
                    pass

                await db.connection(
                    execution_options={"isolation_level": "SERIALIZABLE"}
                )

                # SERIALIZABLE 下必须使用普通快照谓词读（use_lock=False）：
                # 1) SSI 会为该谓词读建立 predicate lock，并发事务插入重叠行
                #    时必有一方收到 40001，由本方法重试/失败兜底，无需显式行锁；
                # 2) 切忌 use_lock=True：其 FOR UPDATE SKIP LOCKED 会跳过
                #    "已存在、正被并发 READ COMMITTED 事务（预约/取消，
                #    increment/decrement_booked_count 持 schedule 行锁）锁住的
                #    真实冲突行"，而 RC 持锁方不产生 SIREAD 锁，SSI 依赖图缺边，
                #    40001 无法兜底，将静默插入重叠排期。
                conflicts = await self.repo.find_conflicts(
                    db,
                    classroom_id=data.classroom_id,
                    teacher_id=data.teacher_id,
                    start_at=data.start_at,
                    end_at=data.end_at,
                    use_lock=False,
                )
                if conflicts["has_conflict"]:
                    # 注意：必须在 rollback 之前构造错误消息——rollback 会使
                    # ORM 对象过期，事后再访问 c.start_at 会触发惰性加载
                    # （greenlet_spawn 错误）。
                    error_messages = []
                    if conflicts["classroom_conflicts"]:
                        classroom_names = [
                            f"{c.start_at.strftime('%Y-%m-%d %H:%M')}~{c.end_at.strftime('%H:%M')}"
                            for c in conflicts["classroom_conflicts"]
                        ]
                        error_messages.append(f"该教室已被占用：{', '.join(classroom_names)}")
                    if conflicts["teacher_conflicts"]:
                        teacher_names = [
                            f"{c.start_at.strftime('%Y-%m-%d %H:%M')}~{c.end_at.strftime('%H:%M')}"
                            for c in conflicts["teacher_conflicts"]
                        ]
                        error_messages.append(f"该教师时间冲突：{', '.join(teacher_names)}")
                    await db.rollback()
                    raise BusinessException("；".join(error_messages), code=400)

                schedule = await self.repo.create(db, schedule_data, auto_commit=False)
                await db.commit()
                await db.refresh(schedule)
                break  # 成功，跳出重试循环

            except BusinessException:
                raise
            except Exception as exc:
                try:
                    await db.rollback()
                except Exception:
                    pass
                if _is_serialization_failure(exc) and attempt < _CREATE_SERIALIZABLE_MAX_ATTEMPTS:
                    logger.warning(
                        f"[ScheduleService] 创建排期遭遇 SerializationFailure，"
                        f"第 {attempt} 次尝试失败，准备重试: {exc}"
                    )
                    continue
                logger.error(f"[ScheduleService] 创建排期失败（尝试 {attempt}）: {exc}")
                raise BusinessException(
                    "创建排期失败，请稍后重试。若持续失败，可能是并发冲突导致。",
                    code=500,
                )

        if schedule is None:
            raise BusinessException(
                "创建排期失败，请稍后重试。若持续失败，可能是并发冲突导致。",
                code=500,
            )

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
        if data.preview_content is not None:
            update_data["preview_content"] = data.preview_content
            update_data["preview_updated_at"] = datetime.now(UTC)

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
        if conflicts["has_conflict"]:
            error_messages = []
            if conflicts["classroom_conflicts"]:
                classroom_names = []
                for c in conflicts["classroom_conflicts"]:
                    time_range = (
                        f"{c.start_at.strftime('%Y-%m-%d %H:%M')}~{c.end_at.strftime('%H:%M')}"
                    )
                    classroom_names.append(time_range)
                error_messages.append(f"该教室已被占用：{', '.join(classroom_names)}")
            if conflicts["teacher_conflicts"]:
                teacher_names = []
                for c in conflicts["teacher_conflicts"]:
                    time_range = (
                        f"{c.start_at.strftime('%Y-%m-%d %H:%M')}~{c.end_at.strftime('%H:%M')}"
                    )
                    teacher_names.append(time_range)
                error_messages.append(f"该教师时间冲突：{', '.join(teacher_names)}")
            raise BusinessException("；".join(error_messages), code=400)

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
        """取消排期(含学员预约处理)

        事务边界：本方法持有整个事务。任一 booking 处理失败（含
        ``MembershipCardService.restore_credit`` 失败）都直接 raise，
        ``db.commit()`` 永不执行，AsyncSession 由 FastAPI 依赖清理时被动回滚，
        全部 booking 状态变更、``decrement_booked_count``、schedule 状态变更
        一并回滚，保证数据一致。与 ``BookingService._do_cancel_booking`` 同构。
        """
        logger.warning(
            f"[ScheduleService] 取消排期: schedule_id={schedule_id}, reason={cancel_reason}"
        )

        from app.modules.booking.models import BookingStatus
        from app.modules.booking.repository import BookingRepository
        from app.modules.membership.service import MembershipCardService

        booking_repo = BookingRepository()
        membership_card_service = MembershipCardService()

        # F6.5 T6.5.11 固定锁序：booking(id ASC) → schedule，
        # 与 cancel_booking / reschedule_booking / finalize_schedule_bookings 一致。
        # 1) 无锁读 id，再按 id ASC 批量 FOR UPDATE，避免多行锁序不一致导致死锁。
        booking_ids = await booking_repo.list_ids_by_schedule(
            db,
            schedule_id,
            (BookingStatus.BOOKED.value,),
        )
        bookings = await booking_repo.get_by_ids_for_update(db, booking_ids)

        # 2) 锁排期并重检状态（等锁期间可能已被并发取消/结束）。
        schedule = await self.get_schedule_for_update(db, schedule_id)
        if schedule.status == ScheduleStatus.CANCELLED.value:
            raise BusinessException("排期已取消", code=400)

        if schedule.status == ScheduleStatus.FINISHED.value:
            raise BusinessException("排期已完成，无法取消", code=400)

        # 3) 持有排期锁后重新收集 BOOKED 预约：首次读之后可能有改期新约落入本排期。
        #    排期已被锁定，后续不会再新增，故此处快照完整。
        latest_ids = await booking_repo.list_ids_by_schedule(
            db,
            schedule_id,
            (BookingStatus.BOOKED.value,),
        )
        locked_ids = {booking.id for booking in bookings}
        extra_ids = [bid for bid in latest_ids if bid not in locked_ids]
        if extra_ids:
            bookings.extend(await booking_repo.get_by_ids_for_update(db, extra_ids))

        # 4) 等锁期间预约可能被取消/改期，锁后按最新状态过滤。
        bookings = [
            booking
            for booking in bookings
            if booking.status == BookingStatus.BOOKED.value
        ]
        total_bookings = len(bookings)

        # 逐个处理预约取消 + 课时回补。
        # 任一失败 → raise → db.commit() 永不执行 → AsyncSession 被动回滚
        # → 已变更的 booking 状态、decrement_booked_count、schedule 状态全部回滚。
        for booking in bookings:
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
                    logger.error(
                        f"[ScheduleService] 取消排期时会员卡恢复次数失败 "
                        f"booking_id={booking.id} card_id={booking.membership_card_id}: {e}"
                    )
                    raise BusinessException(
                        f"会员卡恢复次数失败，取消排期操作已撤销: {e}",
                        code=500,
                    )

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
            f"total_bookings={total_bookings}, all_restored=True"
        )

        # 返回字段集合保持与既有契约一致（router 仅消费 total_bookings / success_count）。
        # 事务回滚路径不会执行到这里；正常路径下 success_count == total_bookings。
        return {
            "schedule_id": schedule_id,
            "total_bookings": total_bookings,
            "success_count": total_bookings,
            "failed_count": 0,
            "failed_bookings": [],
        }

    async def delete_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
    ) -> dict[str, Any]:
        """硬删除排期

        业务规则（原 router 逻辑原样下沉，行为零变化）：
        - 排期不存在 / 跨租户 → NotFoundException（404 "排期不存在"）。
        - 仅 NORMAL（待上课）状态且 booked_count > 0 时拒绝删除
          → BusinessException（400），需先取消排期。
        - 先删除该排期关联的 booking（避免外键约束冲突），再硬删 schedule；
          两步共享同一 AsyncSession，由 ``self.repo.delete(auto_commit=True)``
          统一 commit，异常时 Repository 内 rollback 并 raise。
        """
        schedule = await self.repo.get_by_id(db, schedule_id)
        if not schedule:
            raise NotFoundException("排期不存在")

        # 仅对待上课状态的排期检查学员预约
        if schedule.status == ScheduleStatus.NORMAL.value and schedule.booked_count > 0:
            raise BusinessException("该排期仍有学员预约，请先取消排期后再删除", code=400)

        # 删除关联的预约记录（避免外键约束冲突）
        from app.modules.booking.repository import BookingRepository

        booking_repo = BookingRepository()
        await booking_repo.delete_by_schedule_id(db, schedule_id)

        await self.repo.delete(db, schedule_id, hard_delete=True)

        logger.info(f"[ScheduleService] ✅ 排期删除成功: id={schedule_id}")
        return {"schedule_id": schedule_id}

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
                    errors.append(
                        f"排期 {schedule_id} 已有 {schedule.booked_count} 名学员预约，请先取消排期后再删除"
                    )
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

        logger.warning(
            f"[ScheduleService] ✅ 批量删除完成: 成功 {len(success_ids)}, 失败 {len(failed_ids)}"
        )
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
        classroom_map = await self._get_classroom_info_map(
            db, [schedule.classroom_id] if schedule.classroom_id else []
        )

        return self._to_response(
            schedule,
            course_map.get(schedule.course_id, {}).get("name"),
            course_map.get(schedule.course_id, {}).get("course_type_code"),
            teacher_map.get(schedule.teacher_id),
            classroom_map.get(schedule.classroom_id),
        )

    async def get_schedule_for_update(
        self,
        db: AsyncSession,
        schedule_id: int,
    ) -> CourseSchedule:
        """加悲观锁读取排期（SELECT ... FOR UPDATE，带租户约束）

        F6.3 T6.3.4：供 BookingService.finalize_schedule_bookings 使用，
        避免跨模块直接操作 ScheduleRepository 加锁。
        """
        from app.core.tenant_context import get_tenant_id

        query = select(CourseSchedule).where(CourseSchedule.id == schedule_id)
        tenant_id = get_tenant_id()
        if tenant_id:
            query = query.where(CourseSchedule.tenant_id == tenant_id)

        result = await db.execute(query.with_for_update())
        schedule = result.scalar_one_or_none()
        if not schedule:
            raise NotFoundException("排期不存在")
        return schedule

    async def get_schedules_for_update(
        self,
        db: AsyncSession,
        schedule_ids: list[int],
    ) -> dict[int, CourseSchedule]:
        """批量加悲观锁读取排期（去重 + id ASC，带租户约束）

        F6.5：供 BookingService.reschedule_booking 一次性锁定旧/目标排期，
        避免跨模块直接操作 ScheduleRepository；任一 id 缺失即抛 404。
        """
        unique_ids = sorted({int(schedule_id) for schedule_id in schedule_ids})
        if not unique_ids:
            return {}

        schedules = await self.repo.get_by_ids_for_update(db, unique_ids)
        if len(schedules) != len(unique_ids):
            raise NotFoundException("排期不存在")

        return {schedule.id: schedule for schedule in schedules}

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
            response_items = [
                item for item in response_items if item.display_status == display_status
            ]
            total = len(response_items)

        return ScheduleListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=response_items,
        )

    async def _get_course_info_map(
        self, db: AsyncSession, course_ids: list[int]
    ) -> dict[int, dict]:
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

    async def _get_teacher_info_map(
        self, db: AsyncSession, teacher_ids: list[int]
    ) -> dict[int, str]:
        """批量获取教师信息映射"""
        if not teacher_ids:
            return {}

        UserRepository()
        query = select(User).where(User.id.in_(teacher_ids))
        result = await db.execute(query)
        users = result.scalars().all()

        return {user.id: user.nickname or user.phone for user in users}

    async def _get_classroom_info_map(
        self, db: AsyncSession, classroom_ids: list[int]
    ) -> dict[int, str]:
        """批量获取教室信息映射"""
        if not classroom_ids:
            return {}

        ClassroomRepository()
        query = select(Classroom).where(Classroom.id.in_(classroom_ids))
        result = await db.execute(query)
        classrooms = result.scalars().all()

        return {classroom.id: classroom.name for classroom in classrooms}

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
                    raise ValidationException(
                        f"第 {idx + 1} 个排期: 预约截止时间不能早于预约开放时间"
                    )
            if data.cancel_deadline is not None and data.cancel_deadline > data.start_at:
                raise ValidationException(f"第 {idx + 1} 个排期: 取消截止时间不能晚于排期开始时间")
            time_ranges.append(
                {
                    "start_at": data.start_at,
                    "end_at": data.end_at,
                    "teacher_id": data.teacher_id,
                    "classroom_id": data.classroom_id,
                }
            )
            teacher_ids.add(data.teacher_id)
            if data.classroom_id:
                classroom_ids.add(data.classroom_id)

        # 【新增】检查批量列表内部的排期之间是否有冲突
        for i in range(len(time_ranges)):
            for j in range(i + 1, len(time_ranges)):
                item_i = time_ranges[i]
                item_j = time_ranges[j]

                # 检查时间是否重叠
                if item_i["start_at"] < item_j["end_at"] and item_i["end_at"] > item_j["start_at"]:
                    # 检查教师冲突
                    if item_i["teacher_id"] == item_j["teacher_id"]:
                        raise BusinessException(
                            f"第 {i + 1} 个排期与第 {j + 1} 个排期教师时间冲突 "
                            f"({item_i['start_at'].strftime('%Y-%m-%d %H:%M')}~"
                            f"{item_i['end_at'].strftime('%H:%M')})",
                            code=400,
                        )

                    # 检查教室冲突
                    if (
                        item_i["classroom_id"]
                        and item_j["classroom_id"]
                        and item_i["classroom_id"] == item_j["classroom_id"]
                    ):
                        raise BusinessException(
                            f"第 {i + 1} 个排期与第 {j + 1} 个排期教室时间冲突 "
                            f"({item_i['start_at'].strftime('%Y-%m-%d %H:%M')}~"
                            f"{item_i['end_at'].strftime('%H:%M')})",
                            code=400,
                        )

        # 检查与已有排期的冲突
        for idx, item in enumerate(time_ranges):
            conflicts = await self.repo.find_conflicts(
                db,
                classroom_id=item["classroom_id"],
                teacher_id=item["teacher_id"],
                start_at=item["start_at"],
                end_at=item["end_at"],
                use_lock=True,  # 使用行级锁防止并发冲突
            )
            if conflicts["has_conflict"]:
                error_messages = []
                if conflicts["classroom_conflicts"]:
                    classroom_names = []
                    for c in conflicts["classroom_conflicts"]:
                        time_range = (
                            f"{c.start_at.strftime('%Y-%m-%d %H:%M')}~{c.end_at.strftime('%H:%M')}"
                        )
                        classroom_names.append(time_range)
                    error_messages.append(f"该教室已被占用：{', '.join(classroom_names)}")
                if conflicts["teacher_conflicts"]:
                    teacher_names = []
                    for c in conflicts["teacher_conflicts"]:
                        time_range = (
                            f"{c.start_at.strftime('%Y-%m-%d %H:%M')}~{c.end_at.strftime('%H:%M')}"
                        )
                        teacher_names.append(time_range)
                    error_messages.append(f"该教师时间冲突：{', '.join(teacher_names)}")
                raise BusinessException(
                    f"第 {idx + 1} 个排期：{'；'.join(error_messages)}", code=400
                )

        # 批量创建
        results = []
        for data in items:
            schedule = await self.repo.create(db, data)
            results.append(self._to_response(schedule))

        await db.commit()

        logger.info(f"[ScheduleService] ✅ 批量创建排期成功: count={len(results)}")
        return results
