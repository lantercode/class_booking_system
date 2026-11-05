"""
Teacher Router - 教师管理路由

提供教师相关的 REST API 接口，包含：
- 获取教师信息
- 更新教师信息
"""

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.rbac import require_roles
from app.core.response import success
from app.core.tenant_context import get_tenant_id
from app.deps.auth import get_current_user, get_optional_user
from app.modules.teacher.service import TeacherService

router = APIRouter(prefix="/teachers", tags=["教师管理"])
teacher_service = TeacherService()


@router.get(
    "/",
    response_model=dict,
    summary="获取教师列表",
    description="获取当前租户下的所有活跃教师",
)
async def list_teachers(
    db: AsyncSession = Depends(get_session),
    current_user: dict | None = Depends(get_optional_user),
):
    """获取当前租户下的教师列表"""
    # 优先从 ContextVar 获取 tenant_id（由中间件设置）
    tenant_id = get_tenant_id()
    result = await teacher_service.get_teachers_by_tenant(db, tenant_id)
    return success(data=result)


@router.get(
    "/me",
    response_model=dict,
    summary="获取当前教师信息",
    description="获取当前登录教师的详细信息",
)
@require_roles("teacher")
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
@require_roles("teacher")
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


# 注意：/me 相关路由必须声明在 /{user_id} 之前，否则 "me" 会被当作 user_id 解析
@router.patch(
    "/{user_id}",
    response_model=dict,
    summary="更新指定教师信息（管理端）",
    description="管理端按用户ID更新教师资料（昵称、头像、简介等）",
)
@require_roles("admin", "super_admin")
async def update_teacher(
    user_id: int,
    data: dict = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """管理端更新指定教师信息"""
    # 管理端沿用用户列表的字段名 bio，教师档案内部字段为 intro
    payload = dict(data)
    if "bio" in payload and "intro" not in payload:
        payload["intro"] = payload.pop("bio")
    result = await teacher_service.update_teacher_by_user_id(
        db,
        user_id,
        payload,
        tenant_id=current_user.get("tenant_id"),
    )
    return success(data=result, msg="教师信息更新成功")
