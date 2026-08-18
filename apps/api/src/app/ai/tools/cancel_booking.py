"""
操作类 Tool：取消预约
权限：student
安全：只能取消自己的预约，校验是否在允许取消的时间窗口内
"""

from app.ai.context import ToolContext


async def cancel_booking(
    ctx: ToolContext,
    booking_id: int
) -> dict:
    """
    取消当前用户的指定预约

    Args:
        ctx: 工具调用上下文
        booking_id: 预约 ID

    Returns:
        取消结果
    """
    # TODO: 接入真实的 BookingService
    # 安全校验：
    # 1. 只能取消自己的预约
    # 2. 是否已签到/已完成（不可取消）
    # 3. 是否在取消截止时间前

    return {
        "success": True,
        "message": "取消成功！课时已退回"
    }