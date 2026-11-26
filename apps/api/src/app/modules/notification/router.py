"""站内消息路由（前缀 /notifications，main.py 追加 /api/v1）。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import NotFoundException
from app.core.response import success
from app.deps.auth import get_current_user
from app.modules.notification.service import notification_service

router = APIRouter(prefix="/notifications", tags=["站内消息"])


@router.get("", response_model=dict, summary="我的站内消息列表")
async def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    data = await notification_service.list_for_user(
        db,
        tenant_id=current_user["tenant_id"],
        user_id=current_user["user_id"],
        page=page,
        page_size=page_size,
    )
    return success(data=data)


@router.post("/{notification_id}/read", response_model=dict, summary="标记站内消息已读")
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    ok = await notification_service.mark_read(
        db,
        tenant_id=current_user["tenant_id"],
        user_id=current_user["user_id"],
        notification_id=notification_id,
    )
    if not ok:
        raise NotFoundException("消息不存在或已读")
    await db.commit()
    return success(msg="已读")
