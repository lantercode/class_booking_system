"""排期模块路由"""

from datetime import datetime

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.rbac import require_permissions
from app.core.response import success
from app.deps.auth import get_current_user
from app.modules.schedule.models import ScheduleStatus
from app.modules.schedule.schemas import ScheduleCancel, ScheduleCreate, ScheduleUpdate
from app.modules.schedule.service import ScheduleService

router = APIRouter(prefix="/schedules", tags=["排期管理"])
schedule_service = ScheduleService()

DATETIME_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",      # 2026-07-28T00:00:00 (ISO 8601)
    "%Y-%m-%d %H:%M:%S",      # 2026-07-28 00:00:00 (空格分隔)
    "%Y-%m-%d",                # 2026-07-28 (仅日期)
]


def parse_datetime(value: str | None) -> datetime | None:
    """解析日期时间字符串，支持多种格式"""
    if value is None:
        return None
    for fmt in DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    from app.core.exceptions import ValidationException
    raise ValidationException(
        f"日期格式错误，支持格式: {', '.join(DATETIME_FORMATS)}，"
        f"例如: 2026-07-01 00:00:00 或 2026-07-01T00:00:00"
    )


# ============================================================
# 排期 CRUD
# ============================================================

@router.post(
    "/",
    response_model=dict,
    status_code=201,
    summary="创建排期",
    description="创建新排期（需 schedule:create 权限），自动校验时间冲突",
)
@require_permissions("schedule:create")
async def create_schedule(
    data: ScheduleCreate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """创建排期"""
    result = await schedule_service.create_schedule(
        db, data, operator_id=current_user.get("user_id"),
    )
    return success(data=result, msg="排期创建成功")


@router.post(
    "/batch",
    response_model=dict,
    status_code=201,
    summary="批量创建排期",
    description="批量创建排期（需 schedule:create 权限），自动校验时间冲突",
)
@require_permissions("schedule:create")
async def batch_create_schedules(
    items: list[ScheduleCreate] = Body(..., description="排期列表"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """批量创建排期"""
    result = await schedule_service.batch_create_schedules(
        db, items, operator_id=current_user.get("user_id"),
    )
    return success(data=result, msg=f"成功创建 {len(result)} 个排期")


@router.get(
    "",
    response_model=dict,
    summary="获取排期列表",
    description="分页获取排期列表（支持多条件筛选）",
)
async def list_schedules(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页数量"),
    course_id: int | None = Query(None, description="课程ID"),
    course_name: str | None = Query(None, description="课程名称（模糊搜索）"),
    category: str | None = Query(None, description="课程分类筛选"),
    course_type_code: str | None = Query(None, description="课程类型筛选"),
    teacher_id: int | None = Query(None, description="教师ID"),
    classroom_id: int | None = Query(None, description="教室ID"),
    status: int | None = Query(None, ge=1, le=3, description="状态筛选（DB状态：1正常/2已取消/3已完成）"),
    display_status: int | None = Query(None, ge=1, le=4, description="显示状态筛选：1待上课/2上课中/3已取消/4已完成"),
    start_from: str | None = Query(None, description="开始时间范围-起"),
    start_to: str | None = Query(None, description="开始时间范围-止"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取排期列表"""
    result = await schedule_service.list_schedules(
        db,
        course_id=course_id,
        course_name=course_name,
        category=category,
        course_type_code=course_type_code,
        teacher_id=teacher_id,
        classroom_id=classroom_id,
        status=status,
        display_status=display_status,
        start_from=parse_datetime(start_from),
        start_to=parse_datetime(start_to),
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@router.get(
    "/{schedule_id}",
    response_model=dict,
    summary="获取排期详情",
)
async def get_schedule(
    schedule_id: int = Path(..., description="排期ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取排期详情"""
    result = await schedule_service.get_schedule_by_id(db, schedule_id)
    return success(data=result)


@router.patch(
    "/{schedule_id}",
    response_model=dict,
    summary="更新排期",
    description="更新排期信息（需 schedule:update 权限），自动校验时间冲突",
)
@require_permissions("schedule:update")
async def update_schedule(
    schedule_id: int = Path(..., description="排期ID"),
    data: ScheduleUpdate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """更新排期"""
    result = await schedule_service.update_schedule(db, schedule_id, data)
    return success(data=result, msg="排期更新成功")


@router.post(
    "/{schedule_id}/cancel",
    response_model=dict,
    summary="取消排期",
    description="取消指定排期（需 schedule:cancel 权限），自动处理学员预约和课时退还",
)
@require_permissions("schedule:cancel")
async def cancel_schedule(
    schedule_id: int = Path(..., description="排期ID"),
    data: ScheduleCancel = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """取消排期"""
    result = await schedule_service.cancel_schedule(
        db,
        schedule_id,
        cancel_reason=data.cancel_reason,
        operator_id=current_user.get("user_id"),
    )

    msg = "排期已取消"
    if result["total_bookings"] > 0:
        msg = f"排期已取消，已处理 {result['success_count']}/{result['total_bookings']} 个学员预约"

    return success(data=result, msg=msg)


@router.delete(
    "/{schedule_id}",
    response_model=dict,
    summary="删除排期",
    description="硬删除排期（需 schedule:delete 权限）",
)
@require_permissions("schedule:delete")
async def delete_schedule(
    schedule_id: int = Path(..., description="排期ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """删除排期"""
    schedule = await schedule_service.repo.get_by_id(db, schedule_id)
    if not schedule:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("排期不存在")

    # 仅对待上课状态的排期检查学员预约
    if schedule.status == ScheduleStatus.NORMAL.value and schedule.booked_count > 0:
        from app.core.exceptions import BusinessException
        raise BusinessException("该排期仍有学员预约，请先取消排期后再删除", code=400)

    # 删除关联的预约记录（避免外键约束冲突）
    from app.modules.booking.repository import BookingRepository
    booking_repo = BookingRepository()
    await booking_repo.delete_by_schedule_id(db, schedule_id)

    await schedule_service.repo.delete(db, schedule_id, hard_delete=True)
    return success(msg="排期删除成功")


@router.post(
    "/batch-delete",
    response_model=dict,
    summary="批量删除排期",
    description="批量删除排期（需 schedule:delete 权限），仅支持删除已取消或禁用的排期",
)
@require_permissions("schedule:delete")
async def batch_delete_schedules(
    data: dict = Body(..., description="排期ID列表", example={"schedule_ids": [1, 2, 3]}),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """批量删除排期"""
    schedule_ids = data.get("schedule_ids", [])
    if not schedule_ids:
        from app.core.exceptions import ValidationException
        raise ValidationException("请选择要删除的排期")

    tenant_id = current_user.get("tenant_id")
    result = await schedule_service.batch_delete_schedules(db, schedule_ids, tenant_id)
    await db.commit()
    return success(data=result, msg=f"批量删除完成：成功 {result['success_count']} 个，失败 {result['failed_count']} 个")
