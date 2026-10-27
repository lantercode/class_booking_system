"""Home Config Router - 首页配置路由

前缀 /home-config（由 main.py include_router 时追加 /api/v1）。
"""

from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.rbac import require_roles
from app.core.response import success
from app.deps.auth import get_current_user, get_redis_client
from app.modules.home_config.schemas import HomeConfigDraftUpdate
from app.modules.home_config.service import HomeConfigService

router = APIRouter(prefix="/home-config", tags=["首页配置"])


# ------------------------------------------------------------
# 1. GET /home-config/draft — 管理端读 draft
# ------------------------------------------------------------


@router.get("/draft", response_model=dict, summary="读取首页配置 draft")
@require_roles("admin", "super_admin")
async def get_draft(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """管理端读取 draft；不存在则自动创建空 draft"""
    service = HomeConfigService(db)
    result = await service.get_draft()
    return success(data=result)


# ------------------------------------------------------------
# 2. PUT /home-config/draft — 更新 draft
# ------------------------------------------------------------


@router.put("/draft", response_model=dict, summary="整体覆盖首页配置 draft")
@require_roles("admin", "super_admin")
async def update_draft(
    data: HomeConfigDraftUpdate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """整体覆盖 draft payload（含 schema_version 与 modules type 校验）"""
    service = HomeConfigService(db)
    result = await service.update_draft(data)
    return success(data=result, msg="draft 更新成功")


# ------------------------------------------------------------
# 3. POST /home-config/publish —— 发布
# ------------------------------------------------------------


@router.post("/publish", response_model=dict, summary="把 draft 发布为新 version")
@require_roles("admin", "super_admin")
async def publish(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """原子发布：draft → 新 published 版本。并发唯一约束冲突返回 409。"""
    operator_id = current_user.get("user_id") if current_user else None
    service = HomeConfigService(db)
    result = await service.publish(operator_id=operator_id)
    return success(data=result, msg="发布成功")


# ------------------------------------------------------------
# 4. GET /home-config/published — 小程序/管理端读已发布配置
# ------------------------------------------------------------


@router.get("/published", response_model=dict, summary="读取最新已发布配置")
async def get_published(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """所有已登录角色均可访问（小程序 / 管理端共用）"""
    service = HomeConfigService(db)
    result = await service.get_published_for_miniapp()
    return success(data=result)


# ------------------------------------------------------------
# 5. GET /home-config/versions — 已发布版本列表
# ------------------------------------------------------------


@router.get("/versions", response_model=dict, summary="已发布版本列表")
@require_roles("admin", "super_admin")
async def list_versions(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """列出所有已发布版本（本次只列不回滚）"""
    service = HomeConfigService(db)
    items = await service.list_published_versions()
    return success(data={"items": items, "total": len(items)})
