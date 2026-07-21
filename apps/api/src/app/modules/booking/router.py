"""预约模块路由"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.core.database import get_session
from app.deps.auth import get_current_user
from app.core.rbac import require_permissions

from app.modules.booking.schemas import BookingCreate
from app.modules.booking.service import BookingService

router = APIRouter(prefix="/bookings", tags=["预约管理"])
booking_service = BookingService()


@router.post(
    "",
    response_model=dict,
    status_code=201,
    summary="创建预约",
    description="学员预约课程排期（自动校验容量、重复预约、时间窗口）",
)
async def create_booking(
    data: BookingCreate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    student_id = current_user.get("user_id")
    result = await booking_service.create_booking(
        db, data, student_id=student_id,
    )
    return success(data=result, msg="预约成功")


@router.get(
    "",
    response_model=dict,
    summary="获取预约列表",
    description="分页获取预约列表（支持多条件筛选）",
)
async def list_bookings(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    schedule_id: Optional[int] = Query(None, description="排期ID"),
    status: Optional[int] = Query(None, ge=1, le=5, description="状态筛选"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    # 根据查询条件决定查询范围
    # 1. 如果指定了schedule_id（教师查看排期学员列表），不过滤学员
    # 2. 如果没有指定schedule_id（学员查看自己的预约），只返回当前用户的预约
    student_id = current_user.get("user_id") if not schedule_id else None
    
    result = await booking_service.list_bookings(
        db,
        schedule_id=schedule_id,
        student_id=student_id,
        status=status,
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
    result = await booking_service.get_booking_by_id(db, booking_id)
    return success(data=result)


@router.post(
    "/{booking_id}/cancel",
    response_model=dict,
    summary="取消预约",
    description="取消指定预约（自动释放名额）",
)
async def cancel_booking(
    booking_id: int = Path(..., description="预约ID"),
    reason: str = Query("", description="取消原因"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    student_id = current_user.get("user_id")
    result = await booking_service.cancel_booking(
        db, booking_id, student_id=student_id, reason=reason or None,
    )
    return success(data=result, msg="预约已取消")


@router.post(
    "/cancel",
    response_model=dict,
    summary="取消预约（学员端）",
    description="学员通过排期ID取消自己的预约",
)
async def cancel_booking_by_schedule(
    schedule_id: int = Body(..., description="排期ID"),
    reason: Optional[str] = Body(None, description="取消原因"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    student_id = current_user.get("user_id")
    result = await booking_service.cancel_booking_by_schedule(
        db, schedule_id, student_id=student_id, reason=reason,
    )
    return success(data=result, msg="预约已取消")


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
    result = await booking_service.complete_booking(db, booking_id)
    return success(data=result, msg="课程已完成")