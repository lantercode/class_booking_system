"""
Booking Service - 预约业务逻辑层

处理预约管理的核心业务逻辑，包括：
- 容量校验
- 重复预约检测
- 预约人数原子更新
- 取消预约
- 签到/完成
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BusinessException,
    NotFoundException,
    PermissionException,
    ValidationException,
)
from app.core.rbac import get_user_role_codes
from app.core.rbac.checker import check_roles
from app.modules.booking.models import (
    Booking,
    BookingReschedule,
    BookingSource,
    BookingStatus,
)
from app.modules.booking.repository import BookingRepository, BookingRescheduleRepository
from app.modules.booking.schemas import (
    AffectedBookingItem,
    AffectedBookingsResponse,
    BookingCreate,
    BookingListResponse,
    BookingRescheduleRequest,
    BookingRescheduleResponse,
    BookingResponse,
)
from app.modules.course.service import CourseService
from app.modules.membership.models import CardStatus, CardType, MembershipCard
from app.modules.membership.service import membership_card_service
from app.modules.schedule.models import CourseSchedule, ScheduleStatus
from app.modules.schedule.repository import ScheduleRepository
from app.modules.schedule.service import ScheduleService
from app.modules.user.models import User
from app.modules.user.repository import UserRepository

logger = logging.getLogger(__name__)

# F6.4：冲突提示中的时间段按部署区域时区展示（库内为 UTC）。
# 已知限制：多区域部署时需改为租户级配置。
_DISPLAY_TZ = ZoneInfo("Asia/Shanghai")


class BookingService:
    """预约管理服务"""

    def __init__(self):
        self.repo = BookingRepository()
        self.reschedule_repo = BookingRescheduleRepository()
        self.schedule_repo = ScheduleRepository()
        self.schedule_service = ScheduleService()
        self.course_service = CourseService()

    async def create_booking(
        self,
        db: AsyncSession,
        data: BookingCreate,
        student_id: int,
        operator_id: int | None = None,
    ) -> BookingResponse:
        """创建预约"""
        logger.info(
            f"[BookingService] 创建预约: schedule_id={data.schedule_id}, student_id={student_id}"
        )

        schedule = await self.schedule_repo.get_by_id(db, data.schedule_id)
        if not schedule:
            raise NotFoundException("排期不存在")

        if schedule.status != ScheduleStatus.NORMAL.value:
            raise BusinessException("该排期已取消或已完成，无法预约", code=400)

        if schedule.booked_count >= schedule.capacity:
            raise BusinessException("该排期已约满", code=400)

        now = datetime.now(UTC)

        if schedule.start_at and now > schedule.start_at:
            raise BusinessException("该课程已开始，无法预约", code=400)

        max_booking_date = now + timedelta(days=14)
        if schedule.start_at and schedule.start_at > max_booking_date:
            raise BusinessException("只能预约未来两周内的课程", code=400)

        if schedule.booking_opens_at and now < schedule.booking_opens_at:
            raise BusinessException("预约尚未开放", code=400)
        if schedule.booking_closes_at and now > schedule.booking_closes_at:
            raise BusinessException("预约已截止", code=400)

        existing = await self.repo.find_active_booking(db, data.schedule_id, student_id)
        if existing:
            raise BusinessException("您已预约该排期，请勿重复预约", code=400)

        # F6.3 T6.3.2：预约前的会员卡基础校验（无锁快路径，此阶段无任何写入）
        card_validation: dict[str, Any] | None = None
        if data.membership_card_id is not None:
            course = await self.course_service.get_course_by_id(db, schedule.course_id)
            try:
                card_validation = await membership_card_service.validate_card_for_booking(
                    db,
                    card_id=data.membership_card_id,
                    tenant_id=schedule.tenant_id,
                    student_id=student_id,
                    schedule_id=data.schedule_id,
                    schedule_start_at=schedule.start_at,
                    course_id=schedule.course_id,
                    course_type_code=course.course_type_code,
                )
            except HTTPException as e:
                logger.warning(
                    f"[BookingService] 会员卡预约校验失败: card_id={data.membership_card_id}, "
                    f"detail={e.detail}"
                )
                raise BusinessException(str(e.detail), code=e.status_code)

        # F6.4 T6.4.3：同一学员跨排期时间段重叠校验（D10）。
        # 置于卡校验之后、占名额之前：保持"卡冲突优先提示"，命中时不占名额、不扣次。
        await self.repo.lock_student_booking_scope(
            db, tenant_id=schedule.tenant_id, student_id=student_id
        )
        conflict = await self.repo.find_overlapping_active_booking(
            db,
            student_id=student_id,
            start_at=schedule.start_at,
            end_at=schedule.end_at,
        )
        if conflict:
            conflict_info = (
                await self._get_schedule_info_map(db, [conflict.schedule_id])
            ).get(conflict.schedule_id, {})
            raise BusinessException(
                self._format_time_conflict_message(conflict_info), code=400
            )

        success = await self.schedule_repo.increment_booked_count(db, data.schedule_id)
        if not success:
            raise BusinessException("预约失败，排期可能已满或已取消", code=400)

        source = data.source or BookingSource.SELF.value
        if source not in [s.value for s in BookingSource]:
            raise ValidationException(f"无效的预约来源: {source}")

        booking_data: dict[str, Any] = {
            "schedule_id": data.schedule_id,
            "student_id": student_id,
            "status": BookingStatus.BOOKED.value,
            "source": source,
        }
        if data.membership_card_id is not None:
            booking_data["membership_card_id"] = data.membership_card_id

        # auto_commit=False：与后续 deduct_credit 放入同一事务，保证原子性
        try:
            booking = await self.repo.create(db, booking_data, auto_commit=False)
            # create(auto_commit=False) 只 add 不 flush；后续需要 booking.id 与
            # 期卡锚点查询（autoflush 前必须确保主键已生成）。
            await db.flush()
        except IntegrityError as e:
            await db.rollback()
            err_msg = str(e).lower()
            # Partial UNIQUE 约束：同一学员重复约同一排期
            if "uq_bookings_schedule_student_active" in err_msg or "duplicate key" in err_msg:
                logger.warning(
                    f"[BookingService] 重复预约约束冲突: schedule_id={data.schedule_id}, student_id={student_id}"
                )
                raise BusinessException("您已预约该排期，请勿重复预约", code=400)
            # CHECK 约束：booked_count > capacity
            if "chk_schedule_capacity" in err_msg:
                logger.warning(
                    f"[BookingService] 容量约束冲突: schedule_id={data.schedule_id}"
                )
                raise BusinessException("该排期已约满", code=400)
            # 其他约束冲突
            logger.error(f"[BookingService] 创建预约约束冲突: {e}")
            raise BusinessException("预约失败，请稍后重试", code=400)

        if data.membership_card_id and card_validation:
            tenant_id = booking.tenant_id
            idempotency_key = f"booking_{booking.id}_deduct"
            try:
                if card_validation["deduct"]:
                    # 次卡：以排期日作为有效期判断基准（T6.3.2）
                    await membership_card_service.deduct_credit(
                        db,
                        card_id=data.membership_card_id,
                        tenant_id=tenant_id,
                        booking_id=booking.id,
                        idempotency_key=idempotency_key,
                        check_at=schedule.start_at,
                    )
                elif (
                    card_validation["card_type"] == CardType.PERIOD.value
                    and card_validation["status"] == CardStatus.PENDING.value
                    and card_validation["valid_from"] is None
                ):
                    # 期卡 PENDING（D9）：预期有效期窗口 + 冲突预校验。
                    # 锚点 = 该卡最早非取消预约的排期日；booking 已 flush，包含本笔。
                    anchor_start_at = await self.repo.get_earliest_card_booking_start(
                        db, data.membership_card_id, tenant_id
                    )
                    await membership_card_service.validate_period_card_booking(
                        db,
                        card_id=data.membership_card_id,
                        tenant_id=tenant_id,
                        student_id=student_id,
                        schedule_start_at=schedule.start_at,
                        anchor_start_at=anchor_start_at,
                    )
                # unlimited：不预扣次数、不写流水（T6.3.2 / C-21）
            except HTTPException as e:
                # membership_service 通过 HTTPException 提供准确的业务错误（卡过期、余额不足等）
                await db.rollback()
                logger.error(f"[BookingService] 会员卡校验/扣次失败: {e.detail}")
                raise BusinessException(str(e.detail), code=e.status_code)
            except BusinessException:
                # membership_service 抛出的 BusinessException 直接上抛，不包装
                await db.rollback()
                raise
            except Exception as e:
                # 兜底：未预期的异常（DB 连接、未知错误等）
                await db.rollback()
                logger.exception(f"[BookingService] 会员卡校验/扣次意外异常: {e}")
                raise BusinessException("会员卡校验失败，预约已撤销", code=400)

        await db.commit()
        await db.refresh(booking)

        logger.info(f"[BookingService] ✅ 预约创建成功: id={booking.id}")
        return self._to_response(booking)

    async def cancel_booking(
        self,
        db: AsyncSession,
        booking_id: int,
        student_id: int,
        reason: str | None = None,
    ) -> BookingResponse:
        """取消预约"""
        logger.warning(f"[BookingService] 取消预约: booking_id={booking_id}")

        booking = await self.repo.get_by_id(db, booking_id)
        if not booking:
            raise NotFoundException("预约不存在")

        if booking.student_id != student_id:
            raise PermissionException("只能取消自己的预约")

        return await self._do_cancel_booking(db, booking, reason)

    async def cancel_booking_by_schedule(
        self,
        db: AsyncSession,
        schedule_id: int,
        student_id: int,
        reason: str | None = None,
    ) -> BookingResponse:
        """通过排期ID取消预约（学员端）"""
        logger.warning(
            f"[BookingService] 通过排期ID取消预约: schedule_id={schedule_id}, student_id={student_id}"
        )

        booking = await self.repo.find_by_schedule_and_student(db, schedule_id, student_id)
        if not booking:
            raise NotFoundException("预约不存在")

        return await self._do_cancel_booking(db, booking, reason)

    async def admin_cancel_booking(
        self,
        db: AsyncSession,
        booking_id: int,
        operator_id: int | None = None,
        reason: str | None = None,
    ) -> BookingResponse:
        """管理员代取消预约（不校验学员归属，需 booking:manage 权限）"""
        logger.warning(
            f"[BookingService] 管理员代取消预约: booking_id={booking_id}, operator_id={operator_id}"
        )

        booking = await self.repo.get_by_id(db, booking_id)
        if not booking:
            raise NotFoundException("预约不存在")

        return await self._do_cancel_booking(db, booking, reason)

    async def _do_cancel_booking(
        self,
        db: AsyncSession,
        booking: Booking,
        reason: str | None = None,
    ) -> BookingResponse:
        """执行取消预约操作

        并发安全：
          1. 开头立刻对 booking 行加 FOR UPDATE 锁（替换调用方传入的 stale 对象）
          2. 拿到锁后重新检查 status — 等待锁期间另一并发取消可能已完成
          3. 后续全部操作使用锁定后的 locked_booking 对象
          4. 锁生命周期由同一 AsyncSession 管理，COMMIT 后自动释放
        """
        # 🔑 立即锁定 booking 行 — 用稳定主键命中，不会 miss-lock
        locked_booking = await self.repo.get_by_id_for_update(db, booking.id)
        if not locked_booking:
            raise NotFoundException("预约不存在")

        # 🔑 拿到锁后必须重新检查 status（等待锁期间另一并发取消可能已完成）
        if locked_booking.status == BookingStatus.CANCELLED.value:
            raise BusinessException("预约已取消", code=400)

        if locked_booking.status in [BookingStatus.CHECKED_IN.value, BookingStatus.COMPLETED.value]:
            raise BusinessException("已签到/已完成的预约无法取消", code=400)

        schedule = await self.schedule_repo.get_by_id(db, locked_booking.schedule_id)
        if schedule:
            await self._assert_cancel_window(db, schedule)

        # 🔑 所有后续修改都作用在 locked_booking（FOR UPDATE 锁保护）
        locked_booking.status = BookingStatus.CANCELLED.value
        locked_booking.cancelled_at = datetime.now(UTC)
        if reason:
            locked_booking.cancelled_reason = reason

        await self.schedule_repo.decrement_booked_count(db, locked_booking.schedule_id)

        if locked_booking.membership_card_id:
            tenant_id = locked_booking.tenant_id
            idempotency_key = f"booking_{locked_booking.id}_restore"
            try:
                await membership_card_service.restore_credit(
                    db,
                    card_id=locked_booking.membership_card_id,
                    tenant_id=tenant_id,
                    booking_id=locked_booking.id,
                    idempotency_key=idempotency_key,
                )
            except Exception as e:
                logger.error(f"[BookingService] 会员卡恢复次数失败: {e}")
                raise BusinessException(
                    f"会员卡恢复次数失败，取消预约操作已撤销: {e}", code=500
                )

        await db.commit()
        await db.refresh(locked_booking)

        logger.warning(f"[BookingService] ✅ 预约已取消: id={locked_booking.id}")
        return self._to_response(locked_booking)

    async def reschedule_booking(
        self,
        db: AsyncSession,
        *,
        booking_id: int,
        data: BookingRescheduleRequest,
        current_user: dict,
        idempotency_key: str | None = None,
    ) -> BookingRescheduleResponse:
        """原子改期 / 同排期改派（F6.5）

        锁顺序（不可调换）：
          advisory(tenant, student) → 旧 booking FOR UPDATE → 排期 id ASC
          → 学员卡集 id ASC → 回补旧卡 → 扣目标卡。

        两种模式：
          - 改期（不同排期）：旧约 CANCELLED + 新约 BOOKED，名额 -1/+1；
          - 改派（同排期换卡）：原地更新 membership_card_id，名额不变。

        事务边界：全程共享调用方注入的 AsyncSession，仅在末尾 commit 一次。
        """
        user_id = current_user["user_id"]
        tenant_id = current_user["tenant_id"]
        logger.info(
            f"[BookingService] 改期/改派: booking_id={booking_id}, "
            f"target_schedule_id={data.new_schedule_id}, student_id={user_id}"
        )

        # 1. 同一学员串行化（与 create_booking 共用 advisory lock）
        await self.repo.lock_student_booking_scope(
            db, tenant_id=tenant_id, student_id=user_id
        )

        # 2. 锁旧 booking，拿到锁后重检归属
        booking = await self.repo.get_by_id_for_update(db, booking_id)
        if not booking:
            raise NotFoundException("预约不存在")
        if booking.student_id != user_id:
            raise PermissionException("只能改期自己的预约")

        # 未传目标卡 = 沿用原卡
        target_card_id = (
            data.new_membership_card_id
            if data.new_membership_card_id is not None
            else booking.membership_card_id
        )

        # 3. 幂等重放判定
        replay = await self._find_reschedule_replay(
            db,
            booking,
            target_schedule_id=data.new_schedule_id,
            target_card_id=target_card_id,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            return await self._build_reschedule_response(db, replay, booking)

        # 4. 状态 / 旧排期 / 时间窗口
        if booking.status != BookingStatus.BOOKED.value:
            raise BusinessException("当前预约状态无法改期", code=400)

        old_schedule = await self.schedule_repo.get_by_id(db, booking.schedule_id)
        if not old_schedule:
            raise NotFoundException("原排期不存在")
        if old_schedule.start_at <= datetime.now(UTC):
            raise BusinessException("课程已开始，无法改期", code=400)

        same_schedule = data.new_schedule_id == booking.schedule_id

        if same_schedule and target_card_id == booking.membership_card_id:
            raise BusinessException("未发生改期或改派", code=400)
        if booking.membership_card_id is None and target_card_id is not None:
            raise BusinessException("原预约未使用会员卡，暂不支持改派", code=400)

        # 仅改期释放名额，受取消窗口限制；纯改派不受限
        if not same_schedule:
            await self._assert_cancel_window(db, old_schedule)

        # 5. 目标排期存在性 + 批量加锁（id ASC，旧/目标一次性锁定）
        target_schedule = await self.schedule_repo.get_by_id(db, data.new_schedule_id)
        if not target_schedule:
            raise NotFoundException("目标排期不存在")

        locked = await self.schedule_service.get_schedules_for_update(
            db, [old_schedule.id, target_schedule.id]
        )
        old_schedule = locked[old_schedule.id]
        target_schedule = locked[target_schedule.id]

        if not same_schedule:
            # 锁后重新校验目标排期（状态/容量/时间窗口）
            self._validate_target_schedule(target_schedule)

            duplicate = await self.repo.find_active_booking(
                db,
                target_schedule.id,
                user_id,
                exclude_booking_id=booking.id,
            )
            if duplicate:
                raise BusinessException("您已预约该排期，请勿重复预约", code=400)

            conflict = await self.repo.find_overlapping_active_booking(
                db,
                student_id=user_id,
                start_at=target_schedule.start_at,
                end_at=target_schedule.end_at,
                exclude_booking_id=booking.id,
            )
            if conflict:
                conflict_info = (
                    await self._get_schedule_info_map(db, [conflict.schedule_id])
                ).get(conflict.schedule_id, {})
                raise BusinessException(
                    self._format_time_conflict_message(conflict_info), code=400
                )

        # 6. 目标卡快路径校验（无锁；后续扣次会加锁重检）
        card_validation = await self._validate_target_card(
            db, target_card_id, user_id, tenant_id, target_schedule
        )

        # 7. 锁定学员卡集（id ASC，覆盖 ACTIVE/PENDING/EXPIRED/FROZEN/CANCELLED）
        await membership_card_service.lock_student_cards_for_booking_change(
            db, student_id=user_id, tenant_id=tenant_id
        )

        old_card_id = booking.membership_card_id
        operation_type = "card_swap" if same_schedule else "reschedule"

        try:
            # 8. 审计/幂等记录（new_booking_id 改期时先填旧 id 占位）
            reschedule = await self.reschedule_repo.create(
                db,
                {
                    "old_booking_id": booking.id,
                    "new_booking_id": booking.id,
                    "old_schedule_id": booking.schedule_id,
                    "new_schedule_id": target_schedule.id,
                    "old_membership_card_id": old_card_id,
                    "new_membership_card_id": target_card_id,
                    "operation_type": operation_type,
                    "request_key": idempotency_key,
                    "operator_id": user_id,
                    "remark": data.reason,
                },
                auto_commit=False,
            )
            await db.flush()
            rid = reschedule.id

            if same_schedule:
                # 模式 B：原地改派
                booking.membership_card_id = target_card_id
                await db.flush()

                # booking 已改卡并 flush，锚点查询包含本笔
                await self._validate_period_anchor_if_needed(
                    db,
                    card_validation,
                    target_card_id,
                    user_id,
                    tenant_id,
                    booking,
                    target_schedule,
                )
                await self._restore_old_card(
                    db,
                    old_card_id=old_card_id,
                    reschedule_id=rid,
                    old_booking_id=booking.id,
                    tenant_id=tenant_id,
                )
                await self._deduct_target_card(
                    db,
                    card_validation=card_validation,
                    target_card_id=target_card_id,
                    tenant_id=tenant_id,
                    booking_id=booking.id,
                    idempotency_key=f"reschedule_{rid}_deduct",
                    schedule=target_schedule,
                )
                result_booking = booking
            else:
                # 模式 A：改期（旧约 CANCELLED + 新约 BOOKED）
                booking.status = BookingStatus.CANCELLED.value
                booking.cancelled_at = datetime.now(UTC)
                booking.cancelled_reason = f"改期至排期 {target_schedule.id}"[:255]

                if old_schedule.booked_count > 0:
                    old_schedule.booked_count -= 1
                target_schedule.booked_count += 1
                # flush 释放 uq_bookings_schedule_student_active 占用的旧行
                await db.flush()

                new_booking_data: dict[str, Any] = {
                    "schedule_id": target_schedule.id,
                    "student_id": user_id,
                    "status": BookingStatus.BOOKED.value,
                    "source": BookingSource.SELF.value,
                }
                if target_card_id is not None:
                    new_booking_data["membership_card_id"] = target_card_id

                new_booking = await self.repo.create(
                    db, new_booking_data, auto_commit=False
                )
                await db.flush()
                reschedule.new_booking_id = new_booking.id
                await db.flush()

                # 新约已 flush，锚点查询包含本笔
                await self._validate_period_anchor_if_needed(
                    db,
                    card_validation,
                    target_card_id,
                    user_id,
                    tenant_id,
                    new_booking,
                    target_schedule,
                )
                await self._restore_old_card(
                    db,
                    old_card_id=old_card_id,
                    reschedule_id=rid,
                    old_booking_id=booking.id,
                    tenant_id=tenant_id,
                )
                await self._deduct_target_card(
                    db,
                    card_validation=card_validation,
                    target_card_id=target_card_id,
                    tenant_id=tenant_id,
                    booking_id=new_booking.id,
                    # 保持「每笔次卡 booking 都有 booking_{id}_deduct」不变量
                    idempotency_key=f"booking_{new_booking.id}_deduct",
                    schedule=target_schedule,
                )
                result_booking = new_booking

            await db.commit()
            await db.refresh(result_booking)
        except HTTPException as e:
            await db.rollback()
            raise BusinessException(str(e.detail), code=e.status_code)
        except BusinessException:
            await db.rollback()
            raise
        except IntegrityError as e:
            await db.rollback()
            err_msg = str(e).lower()
            if "uq_booking_reschedules_old_reschedule" in err_msg:
                logger.warning(
                    f"[BookingService] 改期唯一约束冲突: booking_id={booking_id}"
                )
                raise BusinessException("该预约已改期", code=409)
            if "uq_booking_reschedules_request_key" in err_msg:
                logger.warning(
                    f"[BookingService] 幂等键唯一约束冲突: booking_id={booking_id}"
                )
                raise BusinessException("幂等键冲突", code=409)
            if (
                "uq_bookings_schedule_student_active" in err_msg
                or "duplicate key" in err_msg
            ):
                raise BusinessException("您已预约该排期，请勿重复预约", code=400)
            if "chk_schedule_capacity" in err_msg:
                raise BusinessException("该排期已约满", code=400)
            logger.error(f"[BookingService] 改期约束冲突: {e}")
            raise BusinessException("改期失败，请稍后重试", code=400)
        except Exception as e:
            await db.rollback()
            logger.exception(
                f"[BookingService] 改期失败: booking_id={booking_id}, err={e}"
            )
            raise BusinessException("改期失败，请稍后重试", code=500)

        logger.info(
            f"[BookingService] ✅ 改期/改派成功: booking_id={booking_id}, "
            f"mode={operation_type}, result_booking_id={result_booking.id}"
        )
        return await self._build_reschedule_response(db, reschedule, result_booking)

    async def _find_reschedule_replay(
        self,
        db: AsyncSession,
        booking: Booking,
        *,
        target_schedule_id: int,
        target_card_id: int | None,
        idempotency_key: str | None,
    ) -> BookingReschedule | None:
        """幂等重放判定（§7.4）；参数不一致时抛 409。"""
        if idempotency_key:
            existing = await self.reschedule_repo.get_by_request_key(
                db, idempotency_key
            )
            if existing:
                # 请求键重放只比对「请求可决定的目标参数」：
                # 改派成功后 booking.membership_card_id 已被改写为旧记录的
                # new_membership_card_id，若再比对 old_membership_card_id
                # 会导致合法重试被误判为参数不一致。
                same_schedule = target_schedule_id == booking.schedule_id
                expected_operation = "card_swap" if same_schedule else "reschedule"
                if (
                    existing.old_booking_id == booking.id
                    and existing.new_schedule_id == target_schedule_id
                    and existing.new_membership_card_id == target_card_id
                    and existing.operation_type == expected_operation
                ):
                    return existing
                raise BusinessException("幂等键已被其他请求使用", code=409)

        if booking.status == BookingStatus.CANCELLED.value:
            existing = await self.reschedule_repo.get_reschedule_by_old_booking(
                db, booking.id
            )
            if existing:
                if (
                    existing.old_schedule_id == booking.schedule_id
                    and existing.new_schedule_id == target_schedule_id
                    and existing.old_membership_card_id == booking.membership_card_id
                    and existing.new_membership_card_id == target_card_id
                ):
                    return existing
                raise BusinessException("预约已改期，请基于最新预约操作", code=409)

        if booking.status == BookingStatus.BOOKED.value:
            latest = await self.reschedule_repo.get_latest_by_old_booking(
                db, booking.id
            )
            if (
                latest is not None
                and latest.operation_type == "card_swap"
                and latest.new_schedule_id == target_schedule_id
                and latest.new_membership_card_id == target_card_id
            ):
                return latest

        return None

    async def _assert_cancel_window(
        self,
        db: AsyncSession,
        schedule: CourseSchedule,
    ) -> None:
        """取消窗口校验（取消与改期共用）。

        从 ``_do_cancel_booking`` 抽出，行为与文案保持一致：
        先看排期 ``cancel_deadline``，再按租户 ``booking_cancel_minutes``
        （默认 90 分钟）判断是否已进入开课前不可取消窗口。
        """
        if schedule.cancel_deadline and datetime.now(UTC) > schedule.cancel_deadline:
            raise BusinessException("已超过取消截止时间", code=400)

        cancel_minutes = 90
        try:
            from app.modules.tenant.service import TenantService

            tenant_service = TenantService()
            settings = await tenant_service.get_settings(db, schedule.tenant_id)
            cancel_minutes = settings.get("booking_cancel_minutes", 90)
        except Exception as e:
            logger.warning(f"[BookingService] 获取租户配置失败，使用默认值90分钟: {e}")

        time_diff = schedule.start_at - datetime.now(UTC)
        if time_diff.total_seconds() < cancel_minutes * 60:
            raise BusinessException(f"开课前{cancel_minutes}分钟内不可取消预约", code=400)

    def _validate_target_schedule(self, schedule: CourseSchedule) -> None:
        """锁后目标排期校验（对齐 create_booking 的排期规则）。"""
        now = datetime.now(UTC)

        if schedule.status != ScheduleStatus.NORMAL.value:
            raise BusinessException("该排期已取消或已完成，无法预约", code=400)

        if schedule.booked_count >= schedule.capacity:
            raise BusinessException("该排期已约满", code=400)

        if schedule.start_at and now > schedule.start_at:
            raise BusinessException("该课程已开始，无法预约", code=400)

        max_booking_date = now + timedelta(days=14)
        if schedule.start_at and schedule.start_at > max_booking_date:
            raise BusinessException("只能预约未来两周内的课程", code=400)

        if schedule.booking_opens_at and now < schedule.booking_opens_at:
            raise BusinessException("预约尚未开放", code=400)
        if schedule.booking_closes_at and now > schedule.booking_closes_at:
            raise BusinessException("预约已截止", code=400)

    async def _validate_target_card(
        self,
        db: AsyncSession,
        target_card_id: int | None,
        student_id: int,
        tenant_id: int,
        schedule: CourseSchedule,
    ) -> dict[str, Any] | None:
        """目标卡快路径校验；未使用卡时返回 None。"""
        if target_card_id is None:
            return None

        course = await self.course_service.get_course_by_id(db, schedule.course_id)
        try:
            return await membership_card_service.validate_card_for_booking(
                db,
                card_id=target_card_id,
                tenant_id=tenant_id,
                student_id=student_id,
                schedule_id=schedule.id,
                schedule_start_at=schedule.start_at,
                course_id=schedule.course_id,
                course_type_code=course.course_type_code,
            )
        except HTTPException as e:
            logger.warning(
                f"[BookingService] 改期目标卡校验失败: card_id={target_card_id}, "
                f"detail={e.detail}"
            )
            raise BusinessException(str(e.detail), code=e.status_code)

    async def _validate_period_anchor_if_needed(
        self,
        db: AsyncSession,
        card_validation: dict[str, Any] | None,
        card_id: int | None,
        student_id: int,
        tenant_id: int,
        booking: Booking,
        schedule: CourseSchedule,
    ) -> None:
        """期卡 PENDING（valid_from 为空）的锚点/窗口校验。

        ACTIVE 期卡不调用；旧 PENDING 期卡失去锚点保持 PENDING（不额外处理）。
        booking 参数仅用于语义说明（调用前必须已 flush 到当前卡）。
        """
        if card_validation is None or card_id is None:
            return
        if card_validation.get("card_type") != CardType.PERIOD.value:
            return
        if card_validation.get("status") != CardStatus.PENDING.value:
            return
        if card_validation.get("valid_from") is not None:
            return

        anchor_start_at = await self.repo.get_earliest_card_booking_start(
            db, card_id, tenant_id
        )
        await membership_card_service.validate_period_card_booking(
            db,
            card_id=card_id,
            tenant_id=tenant_id,
            student_id=student_id,
            schedule_start_at=schedule.start_at,
            anchor_start_at=anchor_start_at,
        )

    async def _restore_old_card(
        self,
        db: AsyncSession,
        *,
        old_card_id: int | None,
        reschedule_id: int,
        old_booking_id: int,
        tenant_id: int,
    ) -> None:
        """回补旧卡（旧卡为空时跳过；失败上抛，fail-closed）。"""
        if old_card_id is None:
            return

        await membership_card_service.restore_credit(
            db,
            card_id=old_card_id,
            tenant_id=tenant_id,
            booking_id=old_booking_id,
            idempotency_key=f"reschedule_{reschedule_id}_restore",
        )

    async def _deduct_target_card(
        self,
        db: AsyncSession,
        *,
        card_validation: dict[str, Any] | None,
        target_card_id: int | None,
        tenant_id: int,
        booking_id: int,
        idempotency_key: str,
        schedule: CourseSchedule,
    ) -> None:
        """扣目标卡（次卡才扣；期卡/无限卡 no-op）。"""
        if card_validation is None or target_card_id is None:
            return
        if not card_validation.get("deduct"):
            return

        await membership_card_service.deduct_credit(
            db,
            card_id=target_card_id,
            tenant_id=tenant_id,
            booking_id=booking_id,
            idempotency_key=idempotency_key,
            # 次卡：以排期日作为有效期判断基准（与 create_booking 一致）
            check_at=schedule.start_at,
        )

    async def _build_reschedule_response(
        self,
        db: AsyncSession,
        reschedule: BookingReschedule,
        current_booking: Booking,
    ) -> BookingRescheduleResponse:
        """构建改期/改派响应（改期返回新约，改派返回当前约）。"""
        if reschedule.operation_type == "reschedule":
            booking = await self.repo.get_by_id(db, reschedule.new_booking_id)
            if not booking:
                raise BusinessException("改期记录对应的新预约不存在", code=409)
        else:
            booking = current_booking

        schedule_info = (
            await self._get_schedule_info_map(db, [booking.schedule_id])
        ).get(booking.schedule_id, {})

        return BookingRescheduleResponse(
            mode=reschedule.operation_type,
            previous_booking_id=reschedule.old_booking_id,
            previous_status=BookingStatus.BOOKED.value,
            booking=self._to_response(booking, schedule_info=schedule_info),
        )

    async def check_in_booking(
        self,
        db: AsyncSession,
        booking_id: int,
    ) -> BookingResponse:
        """签到

        并发安全：FOR UPDATE 行锁序列化并发签到请求，拿到锁后重新检查 status
        （等待锁期间另一并发签到可能已完成），与 _do_cancel_booking 同构。
        """
        logger.info(f"[BookingService] 签到: booking_id={booking_id}")

        # 🔑 FOR UPDATE 锁住 booking 行，序列化并发签到
        locked_booking = await self.repo.get_by_id_for_update(db, booking_id)
        if not locked_booking:
            raise NotFoundException("预约不存在")

        # 🔑 拿到锁后重新检查 status（等待锁期间另一并发签到可能已完成）
        if locked_booking.status != BookingStatus.BOOKED.value:
            raise BusinessException("当前预约状态无法签到", code=400)

        locked_booking.status = BookingStatus.CHECKED_IN.value
        locked_booking.checked_in_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(locked_booking)

        logger.info(f"[BookingService] ✅ 签到成功: id={booking_id}")
        return self._to_response(locked_booking)

    async def complete_booking(
        self,
        db: AsyncSession,
        booking_id: int,
    ) -> BookingResponse:
        """完成课程

        并发安全：FOR UPDATE 行锁序列化并发完成请求，拿到锁后重新检查 status
        （等待锁期间另一并发完成可能已完成），与 _do_cancel_booking 同构。
        """
        logger.info(f"[BookingService] 完成课程: booking_id={booking_id}")

        # 🔑 FOR UPDATE 锁住 booking 行，序列化并发完成
        locked_booking = await self.repo.get_by_id_for_update(db, booking_id)
        if not locked_booking:
            raise NotFoundException("预约不存在")

        # 🔑 拿到锁后重新检查 status（等待锁期间另一并发完成可能已完成）
        if locked_booking.status not in [BookingStatus.BOOKED.value, BookingStatus.CHECKED_IN.value]:
            raise BusinessException("当前预约状态无法完成", code=400)

        # F6.3 T6.3.3：期卡首次完成激活（同事务；异常上抛触发回滚）
        schedule_info = None
        if locked_booking.membership_card_id:
            schedule_info = await self.schedule_service.get_schedule_by_id(
                db, locked_booking.schedule_id
            )

        locked_booking.status = BookingStatus.COMPLETED.value

        if locked_booking.membership_card_id and schedule_info is not None:
            try:
                # F6.3：激活锚点取该卡最早的非取消预约排期日，避免并发完成时
                # 以“先到达的完成请求”作为生效日导致有效期漂移。
                activation_anchor = (
                    await self.repo.get_earliest_card_booking_start(
                        db,
                        locked_booking.membership_card_id,
                        locked_booking.tenant_id,
                    )
                    or schedule_info.start_at
                )
                await membership_card_service.activate_period_card_on_completion(
                    db,
                    card_id=locked_booking.membership_card_id,
                    booking_id=locked_booking.id,
                    tenant_id=locked_booking.tenant_id,
                    schedule_start_at=activation_anchor,
                )
            except HTTPException as e:
                await db.rollback()
                logger.error(
                    f"[BookingService] 期卡激活失败: booking_id={booking_id}, detail={e.detail}"
                )
                raise BusinessException(str(e.detail), code=e.status_code)
            except BusinessException:
                await db.rollback()
                raise
            except Exception as e:
                await db.rollback()
                logger.exception(f"[BookingService] 期卡激活意外异常: {e}")
                raise BusinessException("会员卡激活失败，完成操作已撤销", code=500)

        await db.commit()
        await db.refresh(locked_booking)

        logger.info(f"[BookingService] ✅ 课程完成: id={booking_id}")
        return self._to_response(locked_booking)

    async def finalize_schedule_bookings(
        self,
        db: AsyncSession,
        schedule_id: int,
        operator_id: int | None = None,
    ) -> dict[str, Any]:
        """排期自动结束时统一收口 booking 终态与期卡激活（F6.3 T6.3.4）

        锁顺序：booking（id ASC）→ schedule → membership card（id ASC）。
        同一事务内完成 schedule FINISHED、booking 终态、期卡激活与 ISSUE 流水；
        任一步异常不 commit（回滚后由 Scheduler 下一轮重试）。

        返回：``{"schedule_id", "completed_count", "no_show_count",
        "skipped_count", "activated_count", "skipped"}``
        """
        result = {
            "schedule_id": schedule_id,
            "completed_count": 0,
            "no_show_count": 0,
            "skipped_count": 0,
            "activated_count": 0,
            "skipped": False,
        }

        booking_ids = await self.repo.list_ids_by_schedule(
            db,
            schedule_id,
            (BookingStatus.BOOKED.value, BookingStatus.CHECKED_IN.value),
        )

        if not booking_ids:
            # 无预约排期同样结束（保持现状）
            schedule = await self.schedule_service.get_schedule_for_update(db, schedule_id)
            if schedule.status != ScheduleStatus.NORMAL.value:
                await db.rollback()
                result["skipped"] = True
                return result
            schedule.status = ScheduleStatus.FINISHED.value
            await db.commit()
            return result

        bookings = await self.repo.get_by_ids_for_update(db, booking_ids)
        schedule = await self.schedule_service.get_schedule_for_update(db, schedule_id)

        if schedule.status != ScheduleStatus.NORMAL.value:
            # 已 FINISHED / CANCELLED → no-op
            await db.rollback()
            result["skipped"] = True
            result["skipped_count"] = len(bookings)
            return result

        schedule.status = ScheduleStatus.FINISHED.value

        try:
            for booking in bookings:
                if booking.status == BookingStatus.CHECKED_IN.value:
                    booking.status = BookingStatus.COMPLETED.value
                    result["completed_count"] += 1
                elif booking.status == BookingStatus.BOOKED.value:
                    booking.status = BookingStatus.NO_SHOW.value
                    result["no_show_count"] += 1
                else:
                    result["skipped_count"] += 1
                    continue

                if not booking.membership_card_id:
                    continue

                card_before = await membership_card_service.get_card(
                    db, booking.membership_card_id, booking.tenant_id
                )
                was_pending_period = (
                    card_before.card_type == CardType.PERIOD.value
                    and card_before.status == CardStatus.PENDING.value
                )
                activation_anchor = (
                    await self.repo.get_earliest_card_booking_start(
                        db,
                        booking.membership_card_id,
                        booking.tenant_id,
                    )
                    or schedule.start_at
                )
                card_after = await membership_card_service.activate_period_card_on_completion(
                    db,
                    card_id=booking.membership_card_id,
                    booking_id=booking.id,
                    tenant_id=booking.tenant_id,
                    schedule_start_at=activation_anchor,
                    operator_id=operator_id,
                )
                if was_pending_period and card_after.status == CardStatus.ACTIVE.value:
                    result["activated_count"] += 1

            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception(
                f"[BookingService] finalize 失败: schedule_id={schedule_id}"
            )
            raise

        logger.info(
            f"[BookingService] ✅ 排期收口: schedule_id={schedule_id}, "
            f"completed={result['completed_count']}, no_show={result['no_show_count']}, "
            f"activated={result['activated_count']}"
        )
        return result

    async def has_completed_or_no_show_booking_for_card(
        self,
        db: AsyncSession,
        card_id: int,
        tenant_id: int,
    ) -> bool:
        """该会员卡是否已有 COMPLETED / NO_SHOW 的预约

        F6.3 T6.3.6：90 天 PENDING 期卡作废前置判断（走 Service 边界，
        避免 membership Scheduler 直接读取 booking 表）。
        """
        return await self.repo.exists_card_booking_with_statuses(
            db,
            card_id,
            tenant_id,
            (BookingStatus.COMPLETED.value, BookingStatus.NO_SHOW.value),
        )

    async def get_booking_by_id(
        self,
        db: AsyncSession,
        booking_id: int,
        *,
        current_user: dict,
    ) -> BookingResponse:
        """获取预约详情（含归属校验）

        归属规则（Service 层强制，非授权决策）：
          - admin / super_admin：放行（全量可查）
          - owner（booking.student_id == current_user.user_id）：放行
          - teacher 且为该预约排期的授课教师：放行
          - 其余：403

        不存在的 booking_id → 404（不泄露存在性）；跨租户由 TenantAwareRepository
        自动过滤为 None → 404。
        """
        booking = await self.repo.get_by_id(db, booking_id)
        if not booking:
            raise NotFoundException("预约不存在")
        schedule_map = await self._get_schedule_info_map(db, [booking.schedule_id])
        schedule_info = schedule_map.get(booking.schedule_id) or {}

        user_id = current_user.get("user_id")
        tenant_id = current_user.get("tenant_id")
        role_codes = await get_user_role_codes(db, user_id, tenant_id)
        is_admin = bool(role_codes & {"admin", "super_admin"})

        if not is_admin:
            is_owner = booking.student_id == user_id
            is_teacher_of_schedule = (
                "teacher" in role_codes
                and schedule_info.get("teacher_id") == user_id
            )
            if not is_owner and not is_teacher_of_schedule:
                raise PermissionException("无权查看该预约")

        return self._to_response(booking, schedule_info=schedule_info)

    async def list_bookings(
        self,
        db: AsyncSession,
        *,
        current_user: dict,
        schedule_id: int | None = None,
        status: int | None = None,
        statuses: list[int] | None = None,
        display_status: int | None = None,
        upcoming: bool = False,
        exclude_cancelled: bool = False,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> BookingListResponse:
        """获取预约列表（分页，含角色归属分流）

        归属规则（Service 层强制，优先级 admin > student > teacher）：
          - admin / super_admin：全量（保留 schedule_id 等既有筛选）
          - student：强制 student_id = current_user.user_id（忽略外部 student_id；
            本端点也不暴露 student_id 查询参数；与 schedule_id 同时生效 → 只看自己在该排期的预约）
          - teacher：强制 teacher_id = current_user.user_id（只看排在自己名下排期的预约）
          - 其余（无 admin/student/teacher 角色）：按最小权限默认，强制 student_id = user_id

        `current_user` 必须由调用方（Router 已认证依赖 / MCP Runtime 受信上下文）注入，
        不得来自请求体或 LLM 输出。
        """
        user_id = current_user.get("user_id")
        tenant_id = current_user.get("tenant_id")
        role_codes = await get_user_role_codes(db, user_id, tenant_id)
        is_admin = bool(role_codes & {"admin", "super_admin"})

        forced_student_id: int | None = None
        forced_teacher_id: int | None = None
        if is_admin:
            # admin/super_admin：不加归属强制，保留既有筛选（schedule_id 等）
            pass
        elif "student" in role_codes:
            forced_student_id = user_id
        elif "teacher" in role_codes:
            forced_teacher_id = user_id
        else:
            # 无已知角色 → 最小权限默认（仅自己作为学员的预约）
            forced_student_id = user_id

        items, db_total = await self.repo.search(
            db,
            schedule_id=schedule_id,
            student_id=forced_student_id,
            teacher_id=forced_teacher_id,
            status=status,
            statuses=statuses,
            upcoming=upcoming,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )

        # 获取所有学员ID并批量查询学员信息
        student_ids = list({b.student_id for b in items})
        student_map = await self._get_student_info_map(db, student_ids)

        # 获取所有排期ID并批量查询排期关联信息（课程名、教室名、教师名、时间）
        schedule_ids = list({b.schedule_id for b in items})
        schedule_map = await self._get_schedule_info_map(db, schedule_ids)

        # 获取所有会员卡ID并批量查询卡信息（卡号、状态、类型、剩余课时）
        card_ids = list({b.membership_card_id for b in items if b.membership_card_id})
        card_map = await self._get_card_info_map(db, card_ids)

        # 构建响应对象列表
        response_items = [
            self._to_response(
                b,
                student_map.get(b.student_id),
                schedule_map.get(b.schedule_id),
                card_map.get(b.membership_card_id),
            )
            for b in items
        ]

        # 小程序端：自动过滤掉已取消的记录（display_status=2）
        if exclude_cancelled:
            response_items = [item for item in response_items if item.display_status != 2]

        # 根据 display_status 过滤（display_status 是计算字段，不在 DB 中）
        if display_status is not None:
            response_items = [
                item for item in response_items if item.display_status == display_status
            ]

        # 分页总数：默认用 DB 层真实 count（与 page_size 无关）。
        # 仅当发生内存过滤（display_status 为计算字段 / exclude_cancelled）时，
        # DB count 与过滤结果不一致，退化为当前页计数（历史行为，小程序端单页场景不受影响）。
        if display_status is not None or exclude_cancelled:
            total = len(response_items)
        else:
            total = db_total

        return BookingListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=response_items,
        )

    async def get_affected_bookings_by_card(
        self,
        db: AsyncSession,
        *,
        card_id: int,
        tenant_id: int,
        requester_user_id: int,
        redis_client=None,
        page: int = 1,
        page_size: int = 20,
    ) -> AffectedBookingsResponse:
        """查询会员卡失效时的「受影响预约」明细与计数（F6.7，只读，R-8）

        归属校验（K2 / R-5，Service 层强制，端点不挂角色装饰器）：
          - admin / super_admin（check_roles 判定）：可查本租户任意卡
          - 其余角色：仅本人卡（card.student_id == requester_user_id），否则 403
        卡不存在 / 跨租户：复用 ``membership_card_service.get_card`` → 404
        （跨租户经 TenantAwareRepository 自动注入屏蔽为 None）。

        口径（K1 / R-1）：status ∈ {BOOKED, CHECKED_IN} 且排期 start_at > now。
        排序（R-10）：start_at ASC, booking.id ASC。
        """
        card = await membership_card_service.get_card(db, card_id, tenant_id)

        is_admin = await check_roles(
            db,
            ["admin", "super_admin"],
            redis_client=redis_client,
            user_id=requester_user_id,
            tenant_id=tenant_id,
        )
        if not is_admin and card.student_id != requester_user_id:
            raise PermissionException("无权查看该卡的受影响预约")

        total, items = await self.repo.list_affected_by_card(
            db,
            card_id,
            tenant_id,
            now=datetime.now(UTC),
            page=page,
            page_size=page_size,
        )

        schedule_map = await self._get_schedule_info_map(
            db, list({b.schedule_id for b in items})
        )

        response_items = []
        for b in items:
            info = schedule_map.get(b.schedule_id) or {}
            response_items.append(
                AffectedBookingItem(
                    booking_id=b.id,
                    schedule_id=b.schedule_id,
                    status=b.status,
                    start_at=info.get("start_at"),
                    end_at=info.get("end_at"),
                    course_name=info.get("course_name"),
                    classroom_name=info.get("classroom_name"),
                    teacher_name=info.get("teacher_name"),
                )
            )

        return AffectedBookingsResponse(
            card_id=card.id,
            card_status=card.status,
            total=total,
            page=page,
            page_size=page_size,
            items=response_items,
        )

    async def _get_student_info_map(
        self, db: AsyncSession, student_ids: list[int]
    ) -> dict[int, tuple[str, str]]:
        """批量获取学员信息映射"""
        if not student_ids:
            return {}

        UserRepository()
        query = select(User).where(User.id.in_(student_ids))
        result = await db.execute(query)
        users = result.scalars().all()

        return {user.id: (user.nickname, user.phone) for user in users}

    def _format_time_conflict_message(self, schedule_info: dict[str, Any]) -> str:
        """F6.4：生成带课程名与时间段的冲突提示（时间按部署区域时区展示）。"""
        course_name = schedule_info.get("course_name")
        start_at = schedule_info.get("start_at")
        end_at = schedule_info.get("end_at")
        if course_name and start_at and end_at:
            local_start = start_at.astimezone(_DISPLAY_TZ)
            local_end = end_at.astimezone(_DISPLAY_TZ)
            window = f"{local_start:%m-%d %H:%M}-{local_end:%H:%M}"
            return (
                f"该时间段与您已约课程《{course_name}》（{window}）冲突，无法预约"
            )
        if course_name:
            return f"该时间段与您已约课程《{course_name}》冲突，无法预约"
        return "该时间段与您已约课程冲突，无法预约"

    async def _get_schedule_info_map(
        self, db: AsyncSession, schedule_ids: list[int]
    ) -> dict[int, dict[str, Any]]:
        """批量获取排期关联信息（课程名、教室名、教师名、时间）"""
        if not schedule_ids:
            return {}

        from app.modules.course.models import Classroom, Course
        from app.modules.user.models import User

        query = (
            select(
                CourseSchedule.id,
                CourseSchedule.start_at,
                CourseSchedule.end_at,
                CourseSchedule.teacher_id,
                CourseSchedule.classroom_id,
                Course.name.label("course_name"),
                Classroom.name.label("classroom_name"),
            )
            .outerjoin(Course, CourseSchedule.course_id == Course.id)
            .outerjoin(Classroom, CourseSchedule.classroom_id == Classroom.id)
            .where(CourseSchedule.id.in_(schedule_ids))
        )
        result = await db.execute(query)
        rows = result.all()

        teacher_ids = [row.teacher_id for row in rows if row.teacher_id]
        teacher_map = {}
        if teacher_ids:
            teacher_query = select(User.id, User.nickname).where(User.id.in_(teacher_ids))
            teacher_result = await db.execute(teacher_query)
            teacher_map = {row.id: row.nickname for row in teacher_result.all()}

        return {
            row.id: {
                "start_at": row.start_at,
                "end_at": row.end_at,
                "teacher_id": row.teacher_id,
                "course_name": row.course_name,
                "classroom_name": row.classroom_name,
                "teacher_name": teacher_map.get(row.teacher_id),
            }
            for row in rows
        }

    async def _get_card_info_map(
        self, db: AsyncSession, card_ids: list[int]
    ) -> dict[int, dict[str, Any]]:
        """批量获取会员卡关联信息（卡号、状态、类型、剩余课时）"""
        if not card_ids:
            return {}

        query = select(
            MembershipCard.id,
            MembershipCard.card_no,
            MembershipCard.status,
            MembershipCard.card_type,
            MembershipCard.total_credits,
            MembershipCard.used_credits,
        ).where(MembershipCard.id.in_(card_ids))
        result = await db.execute(query)
        rows = result.all()

        return {
            row.id: {
                "card_no": row.card_no,
                "status": row.status,
                "card_type": row.card_type,
                "remaining_credits": (
                    (row.total_credits - row.used_credits)
                    if row.total_credits is not None
                    else None
                ),
            }
            for row in rows
        }

    def _to_response(
        self,
        booking: Booking,
        student_info: tuple[str, str] | None = None,
        schedule_info: dict[str, Any] | None = None,
        card_info: dict[str, Any] | None = None,
    ) -> BookingResponse:
        """将 ORM 模型转换为响应对象"""
        nickname, phone = student_info if student_info else (None, None)
        schedule_info = schedule_info or {}
        card_info = card_info or {}

        # 计算显示状态：1待上课/2已取消/3上课中/4已完成
        now = datetime.now(UTC)
        start_at = schedule_info.get("start_at")
        end_at = schedule_info.get("end_at")

        if booking.status == BookingStatus.CANCELLED.value:
            display_status = 2  # 已取消
        elif booking.status == BookingStatus.CHECKED_IN.value:
            display_status = 3  # 上课中
        elif booking.status in (BookingStatus.COMPLETED.value, BookingStatus.NO_SHOW.value):
            display_status = 4  # 已完成
        elif booking.status == BookingStatus.BOOKED.value:
            # 已预约状态，根据时间判断
            if start_at and end_at:
                if start_at > now:
                    display_status = 1  # 待上课
                elif start_at <= now <= end_at:
                    display_status = 3  # 上课中
                else:
                    display_status = 4  # 已完成（时间已过）
            else:
                display_status = 1  # 没有时间信息，默认待上课
        else:
            display_status = booking.status

        return BookingResponse(
            id=booking.id,
            public_id=str(booking.public_id),
            tenant_id=booking.tenant_id,
            schedule_id=booking.schedule_id,
            student_id=booking.student_id,
            status=booking.status,
            display_status=display_status,
            source=booking.source,
            membership_card_id=booking.membership_card_id,
            booked_at=booking.booked_at,
            cancelled_at=booking.cancelled_at,
            cancelled_reason=booking.cancelled_reason,
            checked_in_at=booking.checked_in_at,
            created_at=booking.created_at,
            updated_at=booking.updated_at,
            student_nickname=nickname,
            student_phone=phone,
            course_name=schedule_info.get("course_name"),
            start_at=schedule_info.get("start_at"),
            end_at=schedule_info.get("end_at"),
            classroom_name=schedule_info.get("classroom_name"),
            teacher_name=schedule_info.get("teacher_name"),
            card_no=card_info.get("card_no"),
            card_status=card_info.get("status"),
            card_type=card_info.get("card_type"),
            remaining_credits=card_info.get("remaining_credits"),
        )
