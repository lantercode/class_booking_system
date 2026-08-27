"""
查询类 Tool：消费记录
权限：student（仅自己）
"""

from app.ai.context import ToolContext


async def get_consumption_history(
    ctx: ToolContext,
    page: int = 1,
    page_size: int = 10
) -> dict:
    """
    查询当前用户的消费记录

    Args:
        ctx: 工具调用上下文
        page: 页码
        page_size: 每页条数

    Returns:
        消费记录列表
    """
    # TODO: 接入真实的服务
    return {
        "records": [
            {"date": "2026-08-01", "course": "瑜伽基础班", "type": "消耗", "amount": 1},
            {"date": "2026-07-28", "course": "街舞初级", "type": "消耗", "amount": 1}
        ]
    }
