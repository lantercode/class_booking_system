"""
查询类 Tool：教师今日课程
权限：teacher（仅自己）、admin
"""

from app.ai.context import ToolContext


async def get_teacher_today(ctx: ToolContext) -> dict:
    """
    查询教师当天的排课列表

    Args:
        ctx: 工具调用上下文

    Returns:
        今日课程列表
    """
    # TODO: 接入真实的 ScheduleService
    # 安全：teacher 只能查自己的课程
    return {
        "courses": [
            {"time": "14:00", "name": "瑜伽基础班", "room": "A教室", "students": 8},
            {"time": "16:00", "name": "街舞初级", "room": "B教室", "students": 12}
        ]
    }