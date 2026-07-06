"""课程模块路由 - 占位实现（T05 学员端骨架阶段）"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import success
from app.core.database import get_session
from app.deps.auth import get_current_user

router = APIRouter(prefix="/courses", tags=["课程管理"])


@router.get(
    "",
    summary="获取课程列表",
    description="获取当前租户下的课程列表（T05 占位，返回空列表）",
)
async def list_courses(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
) -> dict:
    return success(data={"items": [], "total": 0, "page": 1, "page_size": 20})
