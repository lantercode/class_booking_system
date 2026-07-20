"""课程模块路由"""

from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.core.database import get_session
from app.deps.auth import get_current_user
from app.core.rbac import require_permissions

from app.modules.course.schemas import CourseCreate, CourseUpdate
from app.modules.course.service import CourseService

router = APIRouter(prefix="/courses", tags=["课程管理"])
course_service = CourseService()


@router.post(
    "",
    response_model=dict,
    status_code=201,
    summary="创建课程",
    description="创建新课程（需 course:create 权限）",
)
@require_permissions("course:create")
async def create_course(
    data: CourseCreate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    result = await course_service.create_course(
        db, data, operator_id=current_user.get("user_id"),
    )
    return success(data=result, msg="课程创建成功")


@router.get(
    "",
    response_model=dict,
    summary="获取课程列表",
    description="分页获取课程列表（支持关键词、分类、等级、状态筛选）",
)
async def list_courses(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str = Query(None, description="搜索关键词"),
    category: str = Query(None, description="分类筛选"),
    level: str = Query(None, description="等级筛选"),
    status: int = Query(None, ge=0, le=1, description="状态筛选"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    result = await course_service.list_courses(
        db,
        keyword=keyword,
        category=category,
        level=level,
        status=status,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@router.get(
    "/{course_id}",
    response_model=dict,
    summary="获取课程详情",
)
async def get_course(
    course_id: int = Path(..., description="课程ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    result = await course_service.get_course_by_id(db, course_id)
    return success(data=result)


@router.patch(
    "/{course_id}",
    response_model=dict,
    summary="更新课程",
    description="更新课程信息（需 course:update 权限）",
)
@require_permissions("course:update")
async def update_course(
    course_id: int = Path(..., description="课程ID"),
    data: CourseUpdate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    result = await course_service.update_course(db, course_id, data)
    return success(data=result, msg="课程更新成功")


@router.delete(
    "/{course_id}",
    response_model=dict,
    summary="删除课程",
    description="软删除课程（需 course:delete 权限）",
)
@require_permissions("course:delete")
async def delete_course(
    course_id: int = Path(..., description="课程ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    await course_service.delete_course(db, course_id)
    return success(msg="课程删除成功")