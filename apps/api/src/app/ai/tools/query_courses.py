"""
查询类 Tool：搜索课程
权限：student, teacher, admin
"""

from app.ai.context import ToolContext


async def query_courses(
    ctx: ToolContext,
    keyword: str = "",
    category: str = None,
    level: str = None
) -> dict:
    """
    搜索课程列表

    Args:
        ctx: 工具调用上下文（自动注入 user_id, tenant_id, role）
        keyword: 搜索关键词，如"瑜伽"、"街舞"
        category: 课程分类
        level: 难度等级

    Returns:
        课程列表
    """
    # TODO: 接入真实的 CourseService
    # from app.services.course_service import CourseService
    # service = CourseService()
    # courses = await service.search_courses(
    #     tenant_id=ctx.tenant_id,
    #     keyword=keyword,
    #     category=category,
    #     level=level
    # )

    # 临时返回假数据
    return {
        "courses": [
            {"id": 1, "name": "瑜伽基础班", "teacher": "张老师", "level": "beginner"},
            {"id": 2, "name": "瑜伽进阶班", "teacher": "李老师", "level": "intermediate"}
        ]
    }