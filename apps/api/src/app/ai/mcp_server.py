"""
MCP Server 入口（P1：Tool 平台化）

职责：
  1. 统一注册全部 Tool（FastMCP stdio）
  2. 统一执行入口 ``execute_tool``：四关校验 + 错误封套
  3. Tool 只调用业务 Service，禁止直接访问 Repository / SQL / Redis

身份来源（不可违反）：
  - user_id / tenant_id 只能来自已认证的可信上下文（``ToolContext``，由
    ``AgentRuntime`` 从 ``get_current_user`` 注入），不接受 LLM 或用户消息。
  - 外部 MCP 客户端（stdio 独立运行）没有可信上下文，一律拒绝执行；
    绝不退化为主机全表/跨租户查询。

Tool 契约清单（name / 所需角色 / 写操作 / 入参 / 返回）：

  | Tool             | 角色                         | 写 | 入参                                   | 返回 |
  |------------------|------------------------------|----|----------------------------------------|------|
  | query_courses    | student/teacher/admin/super  | 否 | keyword, category, level               | 课程列表文本 |
  | query_schedules  | student/teacher/admin/super  | 否 | date(YYYY-MM-DD), keyword, days(1-30)  | 排期列表文本 |
  | get_my_bookings  | student/teacher/admin/super  | 否 | status(booked/cancelled/...)           | 本人预约列表文本 |
  | get_my_balance   | student                      | 否 | 无                                     | 课时余额文本 |
  | create_booking   | student                      | 是 | schedule_id, membership_card_id(可选)  | 预约结果文本 |
  | cancel_booking   | student                      | 是 | booking_id, reason(<=200)              | 取消结果文本 |

返回契约（对用户可见）：
  - 成功：业务文本（最小化字段，不含手机号等 PII）
  - 业务错误：可理解的中文提示（不含 SQL / 堆栈 / 表名 / 内部主机名）
  - 系统错误：统一兜底提示，内部细节只写日志

四关顺序（不可调换）：
  Authentication → Authorization → Tenant Validation → Input Validation
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from fastmcp import FastMCP

from app.core.database import SessionLocal
from app.core.exceptions import BusinessException, DanceSaasException
from app.core.rbac import get_user_role_codes
from app.core.tenant_context import get_tenant_id
from app.core.tenant_context import tenant_id as _tenant_id_var
from app.core.tenant_context import user_id as _user_id_var
from app.modules.booking.models import BookingStatus
from app.modules.booking.schemas import BookingCreate
from app.modules.booking.service import BookingService
from app.modules.course.service import CourseService
from app.modules.membership.service import MembershipCardService
from app.modules.schedule.service import ScheduleService
from app.modules.user.service import UserService

logger = logging.getLogger(__name__)

# 创建 MCP Server 实例
mcp = FastMCP("dance-saas-agent")

# ============================================================
# 统一返回 / 错误封套
# ============================================================

GENERIC_ERROR_TEXT = "操作失败，请稍后重试或联系客服"
LOGIN_REQUIRED_TEXT = "请先登录后再使用该功能"

ToolKind = Literal["success", "business_error", "system_error"]

# 出现以下内容一律视为内部细节，不得回显给用户
_INTERNAL_PATTERN = re.compile(
    r"(select\s|insert\s+into|update\s+\w+\s+set|delete\s+from"
    r"|traceback|sqlalchemy|asyncpg|psycopg|password|secret|token"
    r"|://|file \"|line \d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """Tool 统一执行结果：成功 / 业务错误 / 系统错误三类。"""

    kind: ToolKind
    text: str
    code: int = 0
    error_type: str | None = None

    @property
    def ok(self) -> bool:
        return self.kind == "success"


@dataclass(frozen=True, slots=True)
class ToolContext:
    """可信调用上下文：只允许由已认证的 Runtime / 宿主注入。"""

    user_id: int
    tenant_id: int
    role_id: int | None = None


_tool_ctx: ContextVar[ToolContext | None] = ContextVar("mcp_tool_context", default=None)


def current_tool_context() -> ToolContext | None:
    """返回当前可信上下文；stdio 独立运行时为 None。"""
    return _tool_ctx.get()


@contextmanager
def tool_context(context: ToolContext):
    """绑定可信上下文，并显式同步租户 / 用户 ContextVar（退出时复位）。

    FastMCP stdio 独立运行没有 HTTP 请求上下文，必须由宿主显式使用本上下文
    管理器注入身份；否则 Tool 会拒绝执行。
    """
    ctx_token: Token = _tool_ctx.set(context)
    tenant_token: Token = _tenant_id_var.set(context.tenant_id)
    user_token: Token = _user_id_var.set(context.user_id)
    try:
        yield context
    finally:
        _user_id_var.reset(user_token)
        _tenant_id_var.reset(tenant_token)
        _tool_ctx.reset(ctx_token)


# ============================================================
# Tool 注册元数据（单一事实源）
# ============================================================


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    handler_name: str
    required_roles: frozenset[str]
    is_write: bool
    input_fields: frozenset[str]


_READ_ROLES = frozenset({"student", "teacher", "admin", "super_admin"})
_STUDENT_ONLY = frozenset({"student"})

TOOL_SPECS: dict[str, ToolSpec] = {
    "query_courses": ToolSpec(
        "query_courses", "query_courses", _READ_ROLES, False, frozenset({"keyword", "category", "level"}),
    ),
    "query_schedules": ToolSpec(
        "query_schedules", "query_schedules", _READ_ROLES, False, frozenset({"date", "keyword", "days"}),
    ),
    "get_my_bookings": ToolSpec(
        "get_my_bookings", "get_my_bookings", _READ_ROLES, False, frozenset({"status"}),
    ),
    "get_my_balance": ToolSpec(
        "get_my_balance", "get_my_balance", _STUDENT_ONLY, False, frozenset(),
    ),
    "create_booking": ToolSpec(
        "create_booking", "create_booking", _STUDENT_ONLY, True, frozenset({"schedule_id", "membership_card_id"}),
    ),
    "cancel_booking": ToolSpec(
        "cancel_booking", "cancel_booking", _STUDENT_ONLY, True, frozenset({"booking_id", "reason"}),
    ),
}


def _sanitize_business_message(message: str) -> str:
    """业务异常转用户可见文本；命中内部细节特征时退化为统一兜底提示。"""
    cleaned = (message or "").strip()
    if not cleaned or len(cleaned) > 200 or _INTERNAL_PATTERN.search(cleaned):
        return GENERIC_ERROR_TEXT
    return cleaned


# ============================================================
# 四关校验辅助
# ============================================================


async def _authorize(db, ctx: ToolContext, spec: ToolSpec) -> None:
    """第二关 Authorization：基于角色的显式授权。

    Tool 层独立完成授权判断（mcp.md 第 2 关），不依赖 HTTP 装饰器；
    不使用 PERMISSION_CHECK_BYPASS，任何角色缺失都拒绝。
    """
    roles = await get_user_role_codes(db, user_id=ctx.user_id, tenant_id=ctx.tenant_id)
    if not roles & set(spec.required_roles):
        if "student" in spec.required_roles:
            raise BusinessException(
                "当前账号没有学员身份，无法执行该操作。请使用学员账号登录后再试。",
                code=403,
            )
        raise BusinessException("当前账号无权使用该功能，请联系管理员", code=403)


async def _gate(
    db,
    *,
    spec: ToolSpec,
    user_id: int | None = None,
    tenant_id: int | None = None,
) -> ToolContext:
    """四关校验统一入口（Authentication → Authorization → Tenant → Input）。

    注意：Input Validation 由各 Tool 在 ``_gate`` 之后继续执行。
    """
    # 第一关 Authentication：可信上下文必须存在
    ctx = _tool_ctx.get()
    if ctx is None:
        raise BusinessException(
            "当前工具调用缺少可信登录上下文，请通过已登录的 AI 助手使用。",
            code=401,
        )
    if _invalid_positive_int(ctx.user_id):
        raise BusinessException("登录状态无效，请重新登录", code=401)
    if _invalid_positive_int(ctx.tenant_id):
        raise BusinessException("当前登录未绑定有效机构，请联系管理员", code=403)

    # 兼容旧调用方的显式身份参数：只允许与可信上下文一致，绝不接受他人身份
    if user_id is not None and user_id != ctx.user_id:
        raise BusinessException("无权访问其他用户的业务数据", code=403)
    if tenant_id is not None and tenant_id != ctx.tenant_id:
        raise BusinessException("无权访问其他机构的业务数据", code=403)

    # 第二关 Authorization
    await _authorize(db, ctx, spec)

    # 第三关 Tenant Validation（显式比对 + 用户归属校验，不只依赖 ContextVar 隐式注入）
    if get_tenant_id() != ctx.tenant_id:
        raise BusinessException("租户上下文校验失败，请重新登录", code=403)
    if not await UserService().is_user_in_tenant(db, ctx.user_id, ctx.tenant_id):
        raise BusinessException("无权访问当前机构数据", code=403)

    return ctx


def _invalid_positive_int(value: Any) -> bool:
    return not isinstance(value, int) or isinstance(value, bool) or value <= 0


def _validate_id(value: Any, name: str) -> int:
    """第四关 Input Validation：ID 必须为正整数。"""
    if _invalid_positive_int(value):
        raise BusinessException(f"{name}无效，请重新选择", code=400)
    return value


def _validate_text(value: Any, name: str, max_length: int = 50, allow_empty: bool = True) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BusinessException(f"{name}格式无效，请重新输入", code=400)
    cleaned = value.strip()
    if len(cleaned) > max_length:
        raise BusinessException(f"{name}过长，请精简后重试", code=400)
    if not cleaned:
        return None if allow_empty else ""
    return cleaned


def _validate_enum(value: Any, name: str, allowed: set[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BusinessException(f"{name}无效，请重新选择", code=400)
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise BusinessException(f"{name}无效，请重新选择", code=400)
    return normalized


def _parse_date(value: Any) -> datetime | None:
    """解析 YYYY-MM-DD，并做范围校验（今天前 30 天 ~ 今天后 90 天）。"""
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        raise BusinessException("日期格式无效，请使用 YYYY-MM-DD 格式", code=400)
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError as exc:
        raise BusinessException("日期无效，请检查年月日是否正确", code=400) from exc

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if parsed < today - timedelta(days=30) or parsed > today + timedelta(days=90):
        raise BusinessException("日期超出可查询范围，请选择近 90 天内的日期", code=400)
    return parsed


def _validate_days(value: Any) -> int:
    if value is None:
        return 7
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 30:
        raise BusinessException("查询天数无效，请使用 1-30 之间的整数", code=400)
    return value


async def _require_student_role(
    db, user_id: int, action: str, tenant_id: int | None = None
) -> None:
    """第二关 Authorization（写操作专用）：仅学员角色可用。"""
    roles = await get_user_role_codes(db, user_id=user_id, tenant_id=tenant_id)
    if "student" not in roles:
        raise BusinessException(
            f"当前账号没有学员身份，无法{action}。请使用学员账号登录后再试。",
            code=403,
        )


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

_COURSE_CATEGORIES = {"yoga", "dance", "fitness", "kids", "other"}
_COURSE_LEVELS = {"beginner", "intermediate", "advanced"}
_BOOKING_STATUSES = {
    "booked": BookingStatus.BOOKED.value,
    "cancelled": BookingStatus.CANCELLED.value,
    "checked_in": BookingStatus.CHECKED_IN.value,
    "completed": BookingStatus.COMPLETED.value,
    "no_show": BookingStatus.NO_SHOW.value,
}


@mcp.tool(name="query_courses", exclude_args=["user_id", "tenant_id"])
async def query_courses(
    keyword: str = "",
    category: str | None = None,
    level: str | None = None,
    user_id: int | None = None,
    tenant_id: int | None = None,
) -> str:
    """
    搜索课程列表，支持按关键词、分类、难度等级筛选

    Args:
        keyword: 搜索关键词，如'瑜伽'、'街舞'、'芭蕾'
        category: 舞蹈分类，可选值：yoga, dance, fitness, kids, other
        level: 难度等级，可选值：beginner, intermediate, advanced
    """
    async with SessionLocal() as db:
        await _gate(db, spec=TOOL_SPECS["query_courses"], user_id=user_id, tenant_id=tenant_id)

        keyword = _validate_text(keyword, "关键词", 50) or ""
        category = _validate_enum(category, "分类", _COURSE_CATEGORIES)
        level = _validate_enum(level, "难度等级", _COURSE_LEVELS)

        service = CourseService()
        result = await service.list_courses(
            db,
            keyword=keyword or None,
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
                f"- {c.name}（{c.category}·{c.level}）{c.duration_minutes}分钟 ¥{c.price}"
            )
        return "\n".join(lines)


@mcp.tool(name="query_schedules", exclude_args=["user_id", "tenant_id"])
async def query_schedules(
    date: str | None = None,
    keyword: str = "",
    days: int = 7,
    user_id: int | None = None,
    tenant_id: int | None = None,
) -> str:
    """
    查询指定日期范围内的排期列表

    Args:
        date: 起始日期，格式 YYYY-MM-DD，默认今天
        keyword: 课程名称关键词
        days: 查询未来 N 天（1-30），默认 7 天
    """
    async with SessionLocal() as db:
        await _gate(db, spec=TOOL_SPECS["query_schedules"], user_id=user_id, tenant_id=tenant_id)

        parsed_date = _parse_date(date)
        keyword_text = _validate_text(keyword, "关键词", 50) or ""
        days_value = _validate_days(days)

        service = ScheduleService()
        start_from = parsed_date or datetime.now()
        start_to = start_from + timedelta(days=days_value)

        result = await service.list_schedules(
            db,
            course_name=keyword_text or None,
            status=1,  # NORMAL
            start_from=start_from,
            start_to=start_to,
            page=1,
            page_size=20,
        )

        if not result.items:
            return (
                f"{start_from.strftime('%Y-%m-%d')} 至 {start_to.strftime('%Y-%m-%d')} 暂无排期"
            )

        lines = [
            f"{start_from.strftime('%Y-%m-%d')} 至 {start_to.strftime('%Y-%m-%d')} "
            f"共 {result.total} 个排期："
        ]
        # 输出格式必须与 AgentRuntime._parse_schedules 保持一致（Tool 文本契约）
        for s in result.items:
            date_str = s.start_at.strftime("%Y-%m-%d") if s.start_at else "待定"
            start_time = s.start_at.strftime("%H:%M") if s.start_at else "待定"
            end_time = s.end_at.strftime("%H:%M") if s.end_at else "待定"
            teacher = s.teacher_name or "待定"
            remaining = max(int(s.capacity) - int(s.booked_count), 0)
            lines.append(
                f"- ID:{s.id} | {date_str} | {start_time}-{end_time} | "
                f"{teacher} | 剩余:{remaining} | {s.course_name}"
            )
        return "\n".join(lines)


@mcp.tool(name="get_my_bookings", exclude_args=["user_id", "tenant_id"])
async def get_my_bookings(
    status: str | None = None,
    user_id: int | None = None,
    tenant_id: int | None = None,
) -> str:
    """
    查询当前用户的预约记录

    Args:
        status: 状态筛选，可选值：booked, cancelled, checked_in, completed, no_show
    """
    async with SessionLocal() as db:
        ctx = await _gate(
            db, spec=TOOL_SPECS["get_my_bookings"], user_id=user_id, tenant_id=tenant_id
        )

        status_value = _validate_enum(status, "状态", set(_BOOKING_STATUSES))
        status_int = _BOOKING_STATUSES.get(status_value) if status_value else None

        service = BookingService()
        # self_only=True：即使 admin/teacher 调用，也只返回本人作为学员的预约
        result = await service.list_bookings(
            db,
            current_user={"user_id": ctx.user_id, "tenant_id": ctx.tenant_id},
            status=status_int,
            page=1,
            page_size=20,
            self_only=True,
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
            lines.append(f"- [{status_label}] {time_str} {course}{teacher}（预约ID: {b.id}）")
        return "\n".join(lines)


@mcp.tool(name="get_my_balance", exclude_args=["user_id", "tenant_id"])
async def get_my_balance(
    user_id: int | None = None,
    tenant_id: int | None = None,
) -> str:
    """查询当前用户的课时余额（数据由 membership Service 提供，Tool 不直连数据库）。"""
    async with SessionLocal() as db:
        ctx = await _gate(
            db, spec=TOOL_SPECS["get_my_balance"], user_id=user_id, tenant_id=tenant_id
        )

        balance = await MembershipCardService().get_user_balance(
            db,
            student_id=ctx.user_id,
            tenant_id=ctx.tenant_id,
        )
        return (
            f"您的课时余额：\n总购买：{balance['total']} 课时\n"
            f"已消耗：{balance['used']} 课时\n剩余：{balance['remaining']} 课时"
        )


# ============================================================
# 操作类 Tool（幂等依赖 Service 层事务 / 行锁，不在 Tool 层另造写法）
# ============================================================


@mcp.tool(name="create_booking", exclude_args=["user_id", "tenant_id"])
async def create_booking(
    schedule_id: int,
    membership_card_id: int | None = None,
    user_id: int | None = None,
    tenant_id: int | None = None,
) -> str:
    """
    为当前用户预约指定排期的课程

    Args:
        schedule_id: 排期 ID
        membership_card_id: 会员卡 ID（私教课必填，普通课可空）
    """
    async with SessionLocal() as db:
        ctx = await _gate(
            db, spec=TOOL_SPECS["create_booking"], user_id=user_id, tenant_id=tenant_id
        )

        schedule_id = _validate_id(schedule_id, "排期")
        if membership_card_id is not None:
            membership_card_id = _validate_id(membership_card_id, "会员卡")

        auto_card_note = ""
        if membership_card_id is None:
            # 私教课必须使用私教次卡：卡是否可用与排序由 Service 判定，这里只做转交
            schedule = await ScheduleService().get_schedule_by_id(db, schedule_id)
            if schedule.tenant_id != ctx.tenant_id:
                return "排期不存在"
            if schedule.course_type_code == "private":
                recommend = await MembershipCardService().recommend_card_for_schedule(
                    db, ctx.user_id, ctx.tenant_id, schedule_id
                )
                recommended_card_id = recommend.get("recommended_card_id")
                if not recommended_card_id:
                    return recommend.get("message") or "没有可用于该课程的会员卡"
                membership_card_id = recommended_card_id
                auto_card_note = "\n（已自动使用匹配的私教卡）"

        booking_data = BookingCreate(
            schedule_id=schedule_id,
            source="self",
            membership_card_id=membership_card_id,
        )
        result = await BookingService().create_booking(
            db,
            data=booking_data,
            student_id=ctx.user_id,
        )
        time_str = ""
        if result.start_at:
            time_str = result.start_at.strftime("%m/%d %H:%M")
        return (
            f"预约成功！\n课程：{result.course_name}\n时间：{time_str}\n"
            f"预约ID：{result.id}{auto_card_note}"
        )


@mcp.tool(name="cancel_booking", exclude_args=["user_id", "tenant_id"])
async def cancel_booking(
    booking_id: int,
    reason: str | None = None,
    user_id: int | None = None,
    tenant_id: int | None = None,
) -> str:
    """
    取消当前用户的指定预约

    Args:
        booking_id: 预约 ID
        reason: 取消原因（<=200 字）
    """
    async with SessionLocal() as db:
        ctx = await _gate(
            db, spec=TOOL_SPECS["cancel_booking"], user_id=user_id, tenant_id=tenant_id
        )

        booking_id = _validate_id(booking_id, "预约")
        reason = _validate_text(reason, "取消原因", 200)

        result = await BookingService().cancel_booking(
            db,
            booking_id=booking_id,
            student_id=ctx.user_id,
            reason=reason,
        )
        return f"取消成功！\n课程：{result.course_name}\n预约ID：{result.id}"


# ============================================================
# 统一执行入口（Runtime / MCP 客户端唯一调用路径）
# ============================================================


def _filter_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> dict[str, Any]:
    """只接受契约声明的业务入参，忽略身份字段等未声明参数。"""
    return {key: value for key, value in arguments.items() if key in spec.input_fields}


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    context: ToolContext | None = None,
) -> ToolOutcome:
    """统一执行入口：绑定可信上下文 → 调 Tool → 统一错误封套。

    失败不抛异常：业务错误 / 系统错误都转成对用户安全的文本，
    Runtime 据此记录 trace 状态。
    """
    spec = TOOL_SPECS.get(tool_name)
    if spec is None:
        return ToolOutcome("system_error", GENERIC_ERROR_TEXT, error_type="UnknownTool")

    ctx = context or _tool_ctx.get()
    if ctx is None:
        # stdio 独立运行且宿主未注入可信上下文：拒绝执行，绝不回退全表/跨租户
        return ToolOutcome(
            "business_error", LOGIN_REQUIRED_TEXT, code=401, error_type="AuthenticationError"
        )
    if _invalid_positive_int(ctx.user_id) or _invalid_positive_int(ctx.tenant_id):
        return ToolOutcome(
            "business_error", LOGIN_REQUIRED_TEXT, code=401, error_type="AuthenticationError"
        )

    args = _filter_arguments(spec, arguments or {})
    handler = globals()[spec.handler_name]

    with tool_context(ctx):
        try:
            text = await handler(**args, user_id=ctx.user_id, tenant_id=ctx.tenant_id)
            return ToolOutcome("success", text)
        except DanceSaasException as exc:
            # 业务异常（含 NotFound / Validation / Permission）→ 可读文本，不回显内部细节
            return ToolOutcome(
                "business_error",
                _sanitize_business_message(exc.msg),
                code=exc.code,
                error_type=type(exc).__name__,
            )
        except Exception as exc:
            # 系统错误：内部细节只进日志，用户侧只看到统一兜底提示
            logger.error(
                "[MCP] tool execution failed: tool=%s, error_type=%s",
                tool_name,
                type(exc).__name__,
            )
            return ToolOutcome(
                "system_error", GENERIC_ERROR_TEXT, error_type=type(exc).__name__
            )


if __name__ == "__main__":
    # stdio 独立运行：没有可信上下文，所有 Tool 会返回“请先登录”，不会退化为全表查询
    mcp.run(transport="stdio")
