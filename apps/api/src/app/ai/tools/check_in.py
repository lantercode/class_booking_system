"""
操作类 Tool：签到
权限：teacher（仅自己课程）、admin
"""

from app.ai.context import ToolContext


async def check_in(
    ctx: ToolContext,
    booking_id: int
) -> dict:
    """
    为指定预约签到

    Args:
        ctx: 工具调用上下文
        booking_id: 预约 ID

    Returns:
        签到结果
    """
    # TODO: 接入真实的服务
    # 安全：teacher 只能给自己的课程签到
    return {
        "success": True,
        "message": "签到成功！"
    }