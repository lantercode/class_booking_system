"""
查询类 Tool：我的预约
权限：student（仅自己）、teacher（仅自己学生）、admin
"""

from app.ai.context import ToolContext


async def get_my_bookings(
    ctx: ToolContext,
    status: str = None
) -> dict:
    """
    查询当前用户的预约记录

    Args:
        ctx: 工具调用上下文（user_id 自动注入，不允许查他人）
        status: 状态筛选

    Returns:
        预约列表
    """
    # TODO: 接入真实的 BookingService
    # 安全：只能查自己的预约
    return {
        "bookings": [
            {"id": 1001, "course_name": "瑜伽基础班", "date": "2026-08-06", "time": "14:00", "status": "confirmed"}
        ]
    }