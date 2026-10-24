"""
排期定时任务 - 自动标记过期排期为已完成、自动取消人数不足课程

租户隔离：
- 定时任务运行在 APScheduler 线程，ContextVar 为空，若不设置租户会触发全表扫描跨租户操作。
- 每个任务开头查询所有 ACTIVE 租户，循环内 set_tenant_id(tenant.id) 后执行业务，
  单租户异常被隔离不影响其他租户，全部处理完后清理上下文。
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.tenant_context import set_tenant_id
from app.modules.booking.service import BookingService
from app.modules.course.models import Course, CourseType
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.schedule.service import ScheduleService
from app.modules.tenant.models import Tenant, TenantStatus

logger = logging.getLogger(__name__)

settings = get_settings()
schedule_service = ScheduleService()
booking_service = BookingService()


async def _get_active_tenants():
    """
    查询所有状态为 ACTIVE 的租户列表。

    注意：Tenant 模型不含 tenant_id 字段，tenant_query 自动注入不会过滤此查询，
    因此无需担心被当前 ContextVar 的租户过滤误伤。
    """
    async with SessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE.value)
        )
        return result.scalars().all()


async def auto_finish_expired_schedules():
    """
    自动将已结束的排期标记为 FINISHED

    执行逻辑:
    1. 遍历所有 ACTIVE 租户，逐租户设置 ContextVar
    2. 找到 end_at + grace_period < now 且 status=NORMAL 的排期
    3. 将排期状态改为 FINISHED
    4. 关联预约状态流转:
       - CHECKED_IN(3) -> COMPLETED(4)   已签到的视为完成
       - BOOKED(1)     -> NO_SHOW(5)     约了没来的视为缺席

    单租户处理失败仅记录日志，不中断其他租户。
    """
    if not settings.AUTO_FINISH_ENABLED:
        return

    tenants = await _get_active_tenants()
    if not tenants:
        return

    for tenant in tenants:
        tenant_id = tenant.id
        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                now = datetime.now(UTC)
                grace = timedelta(minutes=settings.AUTO_FINISH_GRACE_MINUTES)

                result = await db.execute(
                    select(CourseSchedule).where(
                        CourseSchedule.end_at < now - grace,
                        CourseSchedule.status == ScheduleStatus.NORMAL.value,
                    )
                )
                schedules = result.scalars().all()

                if not schedules:
                    continue

                schedule_ids = [s.id for s in schedules]
                logger.info(
                    f"[定时任务][租户{tenant_id}] 发现 {len(schedule_ids)} 个已结束排期, "
                    f"grace={settings.AUTO_FINISH_GRACE_MINUTES}min, ids={schedule_ids}"
                )

                success_count = 0
                failed_count = 0

                # F6.3 T6.3.4：不再 bulk update 业务状态，逐排期调用 Service 收口，
                # 由 Service 统一处理 booking 终态 + 期卡首次激活 + 事务提交。
                # 基线选择“每排期一个 session”，避免单排期失败拖累其他排期。
                for schedule in schedules:
                    schedule_id = schedule.id
                    try:
                        async with SessionLocal() as item_db:
                            await booking_service.finalize_schedule_bookings(
                                item_db, schedule_id
                            )
                        success_count += 1
                        logger.info(
                            f"[定时任务][租户{tenant_id}] 排期 #{schedule_id} 收口完成"
                        )
                    except Exception as e:
                        failed_count += 1
                        logger.error(
                            f"[定时任务][租户{tenant_id}] 排期 #{schedule_id} 收口失败: {e}"
                        )

                logger.info(
                    f"[定时任务][租户{tenant_id}] 自动标记 {len(schedule_ids)} 个排期完成: "
                    f"成功 {success_count}, 失败 {failed_count}"
                )
        except Exception as e:
            logger.exception(
                f"[定时任务][租户{tenant_id}] 自动完成排期失败，已跳过该租户: {e}"
            )
            continue
        finally:
            set_tenant_id(None)


async def auto_cancel_underbooked_schedules():
    """
    自动取消人数不足的常规课

    执行逻辑:
    1. 遍历所有 ACTIVE 租户，逐租户设置 ContextVar
    2. 找到 start_at - cancel_before_minutes < now 且 status=NORMAL 的排期
    3. 关联 course_types 表，筛选 min_students 不为 NULL 的类型
    4. 检查 booked_count < min_students
    5. 取消排期（自动处理学员预约和课时退还）
    6. 记录取消原因："预约人数不足（X/Y），系统自动取消"

    单租户处理失败仅记录日志，不中断其他租户。
    """
    if not getattr(settings, "AUTO_CANCEL_UNDERBOOKED_ENABLED", True):
        return

    tenants = await _get_active_tenants()
    if not tenants:
        return

    for tenant in tenants:
        tenant_id = tenant.id
        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                now = datetime.now(UTC)

                # 查询需要检查的排期：
                # - 状态为 NORMAL
                # - 关联的课程类型设置了 min_students 和 cancel_before_minutes
                # - 当前时间已经到达或超过取消截止时间（start_at - cancel_before_minutes）
                # - 实际预约人数 < 最低人数
                query = (
                    select(
                        CourseSchedule.id,
                        CourseSchedule.booked_count,
                        CourseSchedule.start_at,
                        CourseType.min_students,
                        CourseType.cancel_before_minutes,
                        CourseType.name.label("type_name"),
                        Course.name.label("course_name"),
                    )
                    .join(Course, CourseSchedule.course_id == Course.id)
                    .join(CourseType, Course.course_type_code == CourseType.code)
                    .where(
                        CourseSchedule.status == ScheduleStatus.NORMAL.value,
                        CourseType.min_students.isnot(None),
                        CourseType.cancel_before_minutes.isnot(None),
                        CourseSchedule.start_at - timedelta(minutes=CourseType.cancel_before_minutes)
                        <= now,
                        CourseSchedule.booked_count < CourseType.min_students,
                    )
                )

                result = await db.execute(query)
                rows = result.all()

                if not rows:
                    continue

                logger.info(
                    f"[定时任务][租户{tenant_id}] 发现 {len(rows)} 个预约人数不足的排期，准备自动取消"
                )

                cancelled_count = 0
                failed_count = 0

                for row in rows:
                    schedule_id = row.id
                    booked = row.booked_count
                    min_req = row.min_students
                    cancel_minutes = row.cancel_before_minutes
                    type_name = row.type_name
                    course_name = row.course_name

                    try:
                        cancel_reason = f"预约人数不足（{booked}/{min_req}），系统自动取消"
                        # 复用现有的 cancel_schedule 逻辑处理学员预约和课时退还
                        await schedule_service.cancel_schedule(
                            db,
                            schedule_id=schedule_id,
                            cancel_reason=cancel_reason,
                            operator_id=0,  # 0 表示系统自动取消
                        )
                        cancelled_count += 1
                        logger.info(
                            f"[定时任务][租户{tenant_id}] 自动取消排期 #{schedule_id}: "
                            f"{course_name}({type_name}), 已约{booked}人/最低{min_req}人, "
                            f"开课前{cancel_minutes}分钟不能取消"
                        )
                    except Exception as e:
                        failed_count += 1
                        logger.error(
                            f"[定时任务][租户{tenant_id}] 自动取消排期 #{schedule_id} 失败: {e}"
                        )

                await db.commit()

                logger.info(
                    f"[定时任务][租户{tenant_id}] 自动取消人数不足课程完成: "
                    f"成功 {cancelled_count}, 失败 {failed_count}"
                )
        except Exception as e:
            logger.exception(
                f"[定时任务][租户{tenant_id}] 自动取消人数不足排期失败，已跳过该租户: {e}"
            )
            continue
        finally:
            set_tenant_id(None)
