"""
操作类 Tool：创建预约
权限：student
安全：不允许为他人预约，自动校验名额、时间冲突、重复预约
"""

from app.ai.context import ToolContext


async def create_booking(
    ctx: ToolContext,
    schedule_id: int
) -> dict:
    """
    为当前用户预约指定排期的课程

    Args:
        ctx: 工具调用上下文（user_id 自动注入）
        schedule_id: 排期 ID

    Returns:
        预约结果
    """
    # TODO: 接入真实的 BookingService
    # 安全校验：
    # 1. 排期是否存在且未取消
    # 2. 排期是否已过期
    # 3. 剩余名额 > 0
    # 4. 用户未重复预约
    # 5. 用户未被禁用

    return {
        "success": True,
        "booking_id": 1002,
        "message": "预约成功！"
    }
