"""通用模块路由 - 健康检查等无业务依赖的接口."""
from fastapi import APIRouter

from app.core.response import success

router = APIRouter(prefix="/common", tags=["Common"])


@router.get("/health")
async def health() -> dict:
    """健康检查接口 - T01 验收依据."""
    return success(data={"status": "ok"})
