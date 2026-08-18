"""
MCP Server 入口
职责：注册所有 Tool，处理 LLM 的调用请求，启动 stdio/sse 服务

Tool 分类：
  查询类：query_courses, query_schedules, get_my_bookings, get_my_balance
  操作类：create_booking, cancel_booking

用户身份说明：
  操作类 Tool 需要 user_id，当前通过参数传入；后续通过 Context 从 MCP 会话注入
"""

from datetime import datetime, timedelta
from typing import Optional

from fastmcp import FastMCP
from sqlalchemy import select, func

from app.core.database import SessionLocal
from app.modules.course.service import CourseService
from app.modules.schedule.service import ScheduleService
from app.modules.booking.service import BookingService
from app.modules.booking.schemas import BookingCreate
from app.modules.booking.models import BookingStatus
from app.modules.order.models import MembershipCard, MembershipCardStatus

# 创建 MCP Server 实例
mcp = FastMCP("dance-saas-agent")

# ============================================================
# 查询类 Tool
# ============================================================

STATUS_LABELS = {
    BookingStatus.BOOKED.value: "已预约",
    BookingStatus.CANCELLED.value: "已取消",
    BookingStatus.CHECKED_IN.value: "已签到",
    BookingStatus.COMPLETED.value: "已完成",
    BookingStatus.NO_SHOW.value: "未到场",
}


@mcp.tool()
async def query_courses(
    keyword: str = "",
    category: str = None,
    level: str = None,
) -> str:
    """
    搜索课程列表，支持按关键词、分类、难度等级筛选

    Args:
        keyword: 搜索关键词，如'瑜伽'、'街舞'、'芭蕾'
        category: 课程分类，可选值：yoga, dance, fitness, kids, other
        level: 难度等级，可选值：beginner, intermediate, advanced
    """
    try:
        async with SessionLocal() as db:
            service = CourseService()
            result = await service.list_courses(
                db,
                keyword=keyword,
                category=category,
                level=level,
                status=1,
                page=1,
                page_size=10,
            )
            if not result.items:
                return "未找到匹配的课程"
            lines = [f"共 {result.total} 门课程："]
            for c in result.items:
                lines.append(
                    f"- {c.name}（{c.category}·{c.level}）"
                    f"{c.duration_minutes}分钟 ¥{c.price}"
                )
            return "\n".join(lines)
    except Exception as e:
        return f"查询课程失败：{str(e)}"


@mcp.tool()
async def query_schedules(
    date: str = None,
    keyword: str = "",
    days: int = 7,
) -> str:
    """
    查询指定日期范围内的排期列表

    Args:
        date: 起始日期，格式 YYYY-MM-DD，默认今天
        keyword: 课程名称关键词
        days: 查询未来 N 天，默认 7 天
    """
    try:
        async with SessionLocal() as db:
            service = ScheduleService()

            if date:
                start_from = datetime.strptime(date, "%Y-%m-%d")
            else:
                start_from = datetime.now()

            start_to = start_from + timedelta(days=days)

            result = await service.list_schedules(
                db,
                course_name=keyword or None,
                status=1,  # NORMAL
                start_from=start_from,
                start_to=start_to,
                page=1,
                page_size=20,
            )

            if not result.items:
                return f"{start_from.strftime('%Y-%m-%d')} 至 {start_to.strftime('%Y-%m-%d')} 暂无排期"

            lines = [
                f"{start_from.strftime('%Y-%m-%d')} 至 {start_to.strftime('%Y-%m-%d')} "
                f"共 {result.total} 个排期："
            ]
            for s in result.items:
                start_time = s.start_at.strftime("%m/%d %H:%M") if s.start_at else "待定"
                end_time = s.end_at.strftime("%H:%M") if s.end_at else "待定"
                teacher = s.teacher_name or "待定"
                classroom = s.classroom_name or "待定"
                availability = f"{s.booked_count}/{s.capacity}"
                lines.append(
                    f"- {start_time}-{end_time} {s.course_name} "
                    f"教师：{teacher} 教室：{classroom} "
                    f"已约：{availability}（排期ID: {s.id}）"
                )
            return "\n".join(lines)
    except Exception as e:
        return f"查询排期失败：{str(e)}"


@mcp.tool()
async def get_my_bookings(
    user_id: int = None,
    status: str = None,
) -> str:
    """
    查询当前用户的预约记录

    Args:
        user_id: 用户 ID（后续从 MCP 会话自动注入）
        status: 状态筛选，可选值：booked, cancelled, checked_in, completed, no_show
    """
    if user_id is None:
        return "请提供 user_id 参数（后续版本将从登录会话自动获取）"

    try:
        status_map = {
            "booked": BookingStatus.BOOKED.value,
            "cancelled": BookingStatus.CANCELLED.value,
            "checked_in": BookingStatus.CHECKED_IN.value,
            "completed": BookingStatus.COMPLETED.value,
            "no_show": BookingStatus.NO_SHOW.value,
        }
        status_int = status_map.get(status) if status else None

        async with SessionLocal() as db:
            service = BookingService()
            result = await service.list_bookings(
                db,
                student_id=user_id,
                status=status_int,
                page=1,
                page_size=20,
            )

            if not result.items:
                return "暂无预约记录"

            lines = [f"共 {result.total} 条预约记录："]
            for b in result.items:
                status_label = STATUS_LABELS.get(b.status, f"状态{b.status}")
                course = b.course_name or "未知课程"
                time_str = ""
                if b.start_at:
                    time_str = b.start_at.strftime("%m/%d %H:%M")
                    if b.end_at:
                        time_str += f"-{b.end_at.strftime('%H:%M')}"
                teacher = f" 教师：{b.teacher_name}" if b.teacher_name else ""
                lines.append(
                    f"- [{status_label}] {time_str} {course}{teacher}（预约ID: {b.id}）"
                )
            return "\n".join(lines)
    except Exception as e:
        return f"查询预约失败：{str(e)}"


@mcp.tool()
async def get_my_balance(user_id: int = None) -> str:
    """
    查询当前用户的课时余额

    Args:
        user_id: 用户 ID（后续从 MCP 会话自动注入）
    """
    if user_id is None:
        return "请提供 user_id 参数（后续版本将从登录会话自动获取）"

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(
                    func.coalesce(func.sum(MembershipCard.total_credits), 0).label("total"),
                    func.coalesce(func.sum(MembershipCard.used_credits), 0).label("used"),
                ).where(
                    MembershipCard.student_id == user_id,
                    MembershipCard.status == MembershipCardStatus.ACTIVE.value,
                )
            )
            row = result.one()
            total = row.total
            used = row.used
            remaining = max(total - used, 0)

            return (
                f"您的课时余额：\n"
                f"总购买：{total} 课时\n"
                f"已消耗：{used} 课时\n"
                f"剩余：{remaining} 课时"
            )
    except Exception as e:
        return f"查询余额失败：{str(e)}"


# ============================================================
# 操作类 Tool
# ============================================================

@mcp.tool()
async def create_booking(
    schedule_id: int,
    user_id: int = None,
) -> str:
    """
    为当前用户预约指定排期的课程

    Args:
        schedule_id: 排期 ID
        user_id: 用户 ID（后续从 MCP 会话自动注入）
    """
    if user_id is None:
        return "请提供 user_id 参数（后续版本将从登录会话自动获取）"

    try:
        async with SessionLocal() as db:
            service = BookingService()
            booking_data = BookingCreate(schedule_id=schedule_id)
            result = await service.create_booking(
                db,
                data=booking_data,
                student_id=user_id,
            )
            time_str = ""
            if result.start_at:
                time_str = result.start_at.strftime("%m/%d %H:%M")
            return (
                f"预约成功！\n"
                f"课程：{result.course_name}\n"
                f"时间：{time_str}\n"
                f"预约ID：{result.id}"
            )
    except Exception as e:
        return f"预约失败：{str(e)}"


@mcp.tool()
async def cancel_booking(
    booking_id: int,
    user_id: int = None,
    reason: str = None,
) -> str:
    """
    取消当前用户的指定预约

    Args:
        booking_id: 预约 ID
        user_id: 用户 ID（后续从 MCP 会话自动注入）
        reason: 取消原因
    """
    if user_id is None:
        return "请提供 user_id 参数（后续版本将从登录会话自动获取）"

    try:
        async with SessionLocal() as db:
            service = BookingService()
            result = await service.cancel_booking(
                db,
                booking_id=booking_id,
                student_id=user_id,
                reason=reason,
            )
            return (
                f"取消成功！\n"
                f"课程：{result.course_name}\n"
                f"预约ID：{result.id}"
            )
    except Exception as e:
        return f"取消失败：{str(e)}"


if __name__ == "__main__":
    mcp.run(transport="stdio")