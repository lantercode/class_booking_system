"""
Teacher Router - 教师管理路由

提供教师相关的 REST API 接口，包含：
- 获取教师信息
- 更新教师信息
"""

from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.core.database import get_session
from app.deps.auth import get_current_user

from app.modules.teacher.service import TeacherService

router = APIRouter(prefix="/teachers", tags=["教师管理"])
teacher_service = TeacherService()


@router.get(
    "/me",
    response_model=dict,
    summary="获取当前教师信息",
    description="获取当前登录教师的详细信息",
)
async def get_current_teacher(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取当前教师信息"""
    result = await teacher_service.get_teacher_by_user_id(db, current_user.get("user_id"))
    return success(data=result)


@router.patch(
    "/me",
    response_model=dict,
    summary="更新教师信息",
    description="更新当前教师的个人信息",
)
async def update_current_teacher(
    data: dict = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """更新当前教师信息"""
    result = await teacher_service.update_teacher_by_user_id(
        db, 
        current_user.get("user_id"), 
        data,
        tenant_id=current_user.get("tenant_id"),
    )
    return success(data=result, msg="教师信息更新成功")