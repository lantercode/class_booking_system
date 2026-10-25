"""预约模块路由"""

from fastapi import APIRouter, Body, Depends, Header, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.rbac import require_permissions, require_roles
from app.core.response import success
from app.deps.auth import get_current_user
from app.modules.booking.schemas import BookingCreate, BookingRescheduleRequest
from app.modules.booking.service import BookingService

router = APIRouter(prefix="/bookings", tags=["预约管理"])
booking_service = BookingService()


# ============================================================
# 预约操作
# ============================================================


@router.post(
    "/",
    response_model=dict,
    status_code=201,
    summary="创建预约",
    description="学员预约课程排期（自动校验容量、重复预约、时间窗口）",
)
@require_roles("student")
async def create_booking(
    data: BookingCreate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """创建预约"""
    student_id = current_user.get("user_id")
    result = await booking_service.create_booking(
        db,
        data,
        student_id=student_id,
    )
    return success(data=result, msg="预约成功")


@router.get(
    "",
    response_model=dict,
    summary="获取预约列表",
    description="分页获取预约列表（支持多条件筛选，status 支持逗号分隔多个状态）",
)
async def list_bookings(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    schedule_id: int | None = Query(None, description="排期ID"),
    status: str | None = Query(
        None, description="状态筛选，支持逗号分隔多个状态，如 3,4,5 或 completed,cancelled,no_show"
    ),
    display_status: int | None = Query(
        None, ge=1, le=4, description="显示状态筛选：1待上课/2已取消/3上课中/4已完成"
    ),
    upcoming: bool = Query(False, description="是否只查询待上课（未开始）的预约"),
    exclude_cancelled: bool = Query(False, description="是否排除已取消的记录（小程序端使用）"),
    keyword: str | None = Query(None, description="关键词模糊检索（学员昵称/手机号、课程名、排期ID）"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取预约列表

    归属分流在 Service 层完成（按 current_user 的角色：student 只看自己、teacher
    只看自己排期下的、admin/super_admin 全量）。Router 不做角色判断，仅透传 current_user。
    """
    # 解析 status 参数：支持逗号分隔多个状态
    statuses = None
    if status:
        status_map = {
            "booked": 1,
            "pending": 1,
            "待确认": 1,
            "cancelled": 2,
            "已取消": 2,
            "canceled": 2,
            "checked_in": 3,
            "已签到": 3,
            "checkedin": 3,
            "completed": 4,
            "已完成": 4,
            "complete": 4,
            "no_show": 5,
            "缺课": 5,
            "noshow": 5,
            "no-show": 5,
        }
        parts = [s.strip().lower() for s in status.split(",") if s.strip()]
        statuses = []
        for part in parts:
            if part.isdigit():
                statuses.append(int(part))
            elif part in status_map:
                statuses.append(status_map[part])
        if not statuses:
            statuses = None

    # upcoming 仅由调用方显式声明（学员端"待上课"场景）；管理端 status=1 表示全量「已预约」，
    # 不再隐式附加"仅未来排期"过滤，避免过去排期未收口的 BOOKED 在筛选中消失
    is_upcoming = upcoming

    result = await booking_service.list_bookings(
        db,
        current_user=current_user,
        schedule_id=schedule_id,
        statuses=statuses,
        display_status=display_status,
        upcoming=is_upcoming,
        exclude_cancelled=exclude_cancelled,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@router.get(
    "/{booking_id}",
    response_model=dict,
    summary="获取预约详情",
)
async def get_booking(
    booking_id: int = Path(..., description="预约ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取预约详情（归属校验在 Service 层：owner / 教师本人 / admin 放行）"""
    result = await booking_service.get_booking_by_id(
        db, booking_id, current_user=current_user
    )
    return success(data=result)


@router.post(
    "/{booking_id}/cancel",
    response_model=dict,
    summary="取消预约",
    description="取消指定预约（自动释放名额）",
)
@require_roles("student")
async def cancel_booking(
    booking_id: int = Path(..., description="预约ID"),
    reason: str = Query("", description="取消原因"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """取消预约"""
    student_id = current_user.get("user_id")
    result = await booking_service.cancel_booking(
        db,
        booking_id,
        student_id=student_id,
        reason=reason or None,
    )
    return success(data=result, msg="预约已取消")


@router.post(
    "/cancel",
    response_model=dict,
    summary="取消预约（学员端）",
    description="学员通过排期ID取消自己的预约",
)
@require_roles("student")
async def cancel_booking_by_schedule(
    schedule_id: int = Body(..., description="排期ID"),
    reason: str | None = Body(None, description="取消原因"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """学员端取消预约"""
    student_id = current_user.get("user_id")
    result = await booking_service.cancel_booking_by_schedule(
        db,
        schedule_id,
        student_id=student_id,
        reason=reason,
    )
    return success(data=result, msg="预约已取消")


@router.post(
    "/{booking_id}/reschedule",
    response_model=dict,
    summary="原子改期 / 原子改派",
    description="学员将本人预约改期到其他排期，或同排期更换会员卡（同一事务内完成）",
)
@require_roles("student")
async def reschedule_booking(
    booking_id: int = Path(..., description="预约ID"),
    data: BookingRescheduleRequest = Body(...),
    idempotency_key: str | None = Header(
        None, alias="Idempotency-Key", max_length=64, description="幂等键（可选）"
    ),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """原子改期 / 改派"""
    result = await booking_service.reschedule_booking(
        db,
        booking_id=booking_id,
        data=data,
        current_user=current_user,
        idempotency_key=idempotency_key,
    )
    return success(
        data=result,
        msg="改期成功" if result.mode == "reschedule" else "改派成功",
    )


# ============================================================
# 签到与完成（管理端）
# ============================================================


@router.post(
    "/{booking_id}/check-in",
    response_model=dict,
    summary="签到",
    description="学员签到确认（需 booking:manage 权限）",
)
@require_permissions("booking:manage")
async def check_in_booking(
    booking_id: int = Path(..., description="预约ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """签到"""
    result = await booking_service.check_in_booking(db, booking_id)
    return success(data=result, msg="签到成功")


@router.post(
    "/{booking_id}/complete",
    response_model=dict,
    summary="完成课程",
    description="标记课程完成（需 booking:manage 权限）",
)
@require_permissions("booking:manage")
async def complete_booking(
    booking_id: int = Path(..., description="预约ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """完成课程"""
    result = await booking_service.complete_booking(db, booking_id)
    return success(data=result, msg="课程已完成")


@router.post(
    "/{booking_id}/admin-cancel",
    response_model=dict,
    summary="管理员代取消预约",
    description="管理员取消任意预约（需 booking:manage 权限），自动恢复课时与名额",
)
@require_permissions("booking:manage")
async def admin_cancel_booking(
    booking_id: int = Path(..., description="预约ID"),
    reason: str = Query("", description="取消原因"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """管理员代取消预约"""
    operator_id = current_user.get("user_id")
    result = await booking_service.admin_cancel_booking(
        db,
        booking_id,
        operator_id=operator_id,
        reason=reason or None,
    )
    return success(data=result, msg="预约已取消")
