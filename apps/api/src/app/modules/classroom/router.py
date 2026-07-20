"""教室模块路由"""

from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.core.database import get_session
from app.deps.auth import get_current_user
from app.core.rbac import require_permissions

from app.modules.classroom.schemas import ClassroomCreate, ClassroomUpdate
from app.modules.classroom.service import ClassroomService

router = APIRouter(prefix="/classrooms", tags=["教室管理"])
classroom_service = ClassroomService()


@router.post(
    "",
    response_model=dict,
    status_code=201,
    summary="创建教室",
    description="创建新教室（需 classroom:create 权限）",
)
@require_permissions("classroom:create")
async def create_classroom(
    data: ClassroomCreate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    result = await classroom_service.create_classroom(
        db, data, operator_id=current_user.get("user_id"),
    )
    return success(data=result, msg="教室创建成功")


@router.get(
    "",
    response_model=dict,
    summary="获取教室列表",
    description="分页获取教室列表（支持关键词、状态筛选）",
)
async def list_classrooms(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str = Query(None, description="搜索关键词"),
    status: int = Query(None, ge=0, le=1, description="状态筛选"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    result = await classroom_service.list_classrooms(
        db,
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@router.get(
    "/{classroom_id}",
    response_model=dict,
    summary="获取教室详情",
)
async def get_classroom(
    classroom_id: int = Path(..., description="教室ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    result = await classroom_service.get_classroom_by_id(db, classroom_id)
    return success(data=result)


@router.patch(
    "/{classroom_id}",
    response_model=dict,
    summary="更新教室",
    description="更新教室信息（需 classroom:update 权限）",
)
@require_permissions("classroom:update")
async def update_classroom(
    classroom_id: int = Path(..., description="教室ID"),
    data: ClassroomUpdate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    result = await classroom_service.update_classroom(db, classroom_id, data)
    return success(data=result, msg="教室更新成功")


@router.delete(
    "/{classroom_id}",
    response_model=dict,
    summary="删除教室",
    description="删除教室（需 classroom:delete 权限）",
)
@require_permissions("classroom:delete")
async def delete_classroom(
    classroom_id: int = Path(..., description="教室ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    await classroom_service.delete_classroom(db, classroom_id)
    return success(msg="教室删除成功")