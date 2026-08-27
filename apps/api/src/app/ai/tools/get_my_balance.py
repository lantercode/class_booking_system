"""
查询类 Tool：我的课时余额
权限：student（仅自己）
"""

from app.ai.context import ToolContext


async def get_my_balance(ctx: ToolContext) -> dict:
    """
    查询当前用户的课时余额

    Args:
        ctx: 工具调用上下文

    Returns:
        余额信息
    """
    # TODO: 接入真实的 BalanceService
    return {
        "total": 30,
        "consumed": 12,
        "remaining": 18
    }
