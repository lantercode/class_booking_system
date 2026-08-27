"""
操作类 Tool：请假申请
权限：student
"""

from app.ai.context import ToolContext


async def request_leave(
    ctx: ToolContext,
    booking_id: int,
    reason: str = ""
) -> dict:
    """
    为指定预约申请请假

    Args:
        ctx: 工具调用上下文
        booking_id: 预约 ID
        reason: 请假原因

    Returns:
        申请结果
    """
    # TODO: 接入真实的服务
    return {
        "success": True,
        "message": "请假申请已提交，等待审核"
    }
