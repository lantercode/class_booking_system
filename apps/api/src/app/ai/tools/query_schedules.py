"""
查询类 Tool：查询排期
权限：student, teacher, admin
"""

from app.ai.context import ToolContext


async def query_schedules(
    ctx: ToolContext,
    date: str = None,
    keyword: str = "",
    teacher_name: str = None
) -> dict:
    """
    查询指定日期范围内的排期列表

    Args:
        ctx: 工具调用上下文
        date: 日期，格式 YYYY-MM-DD
        keyword: 课程名称关键词
        teacher_name: 教师姓名

    Returns:
        排期列表
    """
    # TODO: 接入真实的 ScheduleService
    return {
        "schedules": [
            {"id": 101, "course_name": "瑜伽基础班", "time": "14:00-15:30", "teacher": "张老师", "room": "A教室"},
            {"id": 102, "course_name": "街舞初级", "time": "16:00-17:30", "teacher": "王老师", "room": "B教室"}
        ]
    }
