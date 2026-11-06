"""P1 MCP Tool 平台化回归测试（不依赖真实 DB / Redis / 网络）.

覆盖：
1. 四关矩阵：Authentication / Authorization / Tenant / Input
2. get_my_balance 走 membership Service（Tool 不直连 Repository / 裸 SQL）
3. 统一错误封套：业务错误可读、系统错误不回显 SQL / traceback / 表名
4. create_booking 按真实 DTO 契约传参（source / membership_card_id）
"""

from types import SimpleNamespace

import pytest

from app.ai import mcp_server
from app.ai.agent.runtime import AgentRuntime
from app.ai.mcp_server import (
    GENERIC_ERROR_TEXT,
    TOOL_SPECS,
    ToolBusinessError,
    ToolContext,
    ToolOutcome,
    _safe_cell,
    execute_tool,
    get_my_balance,
    tool_context,
)
from app.core.exceptions import BusinessException


class _FakeSessionCtx:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *exc):
        return False


class _FakeUserService:
    """租户归属校验默认通过；需要的用例可单独 patch 方法。"""

    async def is_user_in_tenant(self, db, user_id, tenant_id):
        return True


class _FakeUserServiceDenied(_FakeUserService):
    async def is_user_in_tenant(self, db, user_id, tenant_id):
        return False


class _FakeMembershipService:
    calls: list[dict] = []
    result = {"total": 10, "used": 3, "remaining": 7}

    async def get_user_balance(self, db, student_id, tenant_id):
        type(self).calls.append({"student_id": student_id, "tenant_id": tenant_id})
        return type(self).result


class _FakeScheduleService:
    async def list_schedules(self, db, **kwargs):
        return SimpleNamespace(items=[], total=0)


class _FakeBookingService:
    calls: list[dict] = []

    async def list_bookings(self, db, **kwargs):
        type(self).calls.append(kwargs)
        return SimpleNamespace(items=[], total=0)


def _patch_runtime(monkeypatch, *, user_service=_FakeUserService, roles=("student",)):
    async def fake_roles(db, user_id=None, tenant_id=None):
        return set(roles)

    monkeypatch.setattr(mcp_server, "SessionLocal", lambda: _FakeSessionCtx())
    monkeypatch.setattr(mcp_server, "get_user_role_codes", fake_roles)
    monkeypatch.setattr(mcp_server, "UserService", user_service)
    monkeypatch.setattr(mcp_server, "MembershipCardService", _FakeMembershipService)
    monkeypatch.setattr(mcp_server, "ScheduleService", _FakeScheduleService)
    monkeypatch.setattr(mcp_server, "BookingService", _FakeBookingService)


# ============================================================
# 1. 四关矩阵
# ============================================================


@pytest.mark.asyncio
async def test_stdio_without_trusted_context_is_rejected():
    """stdio 独立运行没有可信身份 → 拒绝，且不进入任何 DB / Service 调用。"""
    outcome = await execute_tool("get_my_balance", {})
    assert outcome.kind == "business_error"
    assert outcome.code == 401
    assert "登录" in outcome.text


@pytest.mark.asyncio
async def test_authentication_missing_context_rejected(monkeypatch):
    _patch_runtime(monkeypatch)
    with pytest.raises(BusinessException) as exc:
        await get_my_balance()
    assert exc.value.code == 401


@pytest.mark.asyncio
async def test_identity_mismatch_rejected(monkeypatch):
    """非本人：旧调用方传入 user_id 与可信上下文不一致 → 403。"""
    _patch_runtime(monkeypatch)
    with tool_context(ToolContext(user_id=1, tenant_id=1)):
        with pytest.raises(BusinessException) as exc:
            await get_my_balance(user_id=999)
    assert exc.value.code == 403
    assert "其他用户" in str(exc.value)


@pytest.mark.asyncio
async def test_cross_tenant_rejected(monkeypatch):
    _patch_runtime(monkeypatch)
    with tool_context(ToolContext(user_id=1, tenant_id=1)):
        with pytest.raises(BusinessException) as exc:
            await get_my_balance(tenant_id=2)
    assert exc.value.code == 403
    assert "其他机构" in str(exc.value)


@pytest.mark.asyncio
async def test_tenant_membership_denied(monkeypatch):
    """显式租户归属校验失败（用户不属于该租户）→ 403。"""
    _patch_runtime(monkeypatch, user_service=_FakeUserServiceDenied)
    outcome = await execute_tool(
        "get_my_balance", {}, ToolContext(user_id=1, tenant_id=1)
    )
    assert outcome.kind == "business_error"
    assert outcome.code == 403


@pytest.mark.asyncio
async def test_authorization_denied(monkeypatch):
    """非学员角色调用余额查询 → 403。"""
    _patch_runtime(monkeypatch, roles=("teacher",))
    outcome = await execute_tool(
        "get_my_balance", {}, ToolContext(user_id=1, tenant_id=1)
    )
    assert outcome.kind == "business_error"
    assert outcome.code == 403
    assert "学员" in outcome.text


@pytest.mark.asyncio
async def test_invalid_schedule_date_friendly_error(monkeypatch):
    _patch_runtime(monkeypatch)
    outcome = await execute_tool(
        "query_schedules", {"date": "2026-13-45"}, ToolContext(user_id=1, tenant_id=1)
    )
    assert outcome.kind == "business_error"
    assert outcome.code == 400
    assert "日期" in outcome.text
    assert "Traceback" not in outcome.text


@pytest.mark.asyncio
async def test_invalid_days_friendly_error(monkeypatch):
    _patch_runtime(monkeypatch)
    outcome = await execute_tool(
        "query_schedules", {"days": 999}, ToolContext(user_id=1, tenant_id=1)
    )
    assert outcome.kind == "business_error"
    assert outcome.code == 400
    assert "天数" in outcome.text


@pytest.mark.asyncio
async def test_invalid_booking_status_friendly_error(monkeypatch):
    _patch_runtime(monkeypatch)
    outcome = await execute_tool(
        "get_my_bookings", {"status": "hacker"}, ToolContext(user_id=1, tenant_id=1)
    )
    assert outcome.kind == "business_error"
    assert outcome.code == 400
    assert "状态" in outcome.text


@pytest.mark.asyncio
async def test_self_success_and_ownership_forced(monkeypatch):
    """本人成功，且 get_my_bookings 强制 self_only + 可信 user_id。"""
    _patch_runtime(monkeypatch, roles=("admin",))
    _FakeBookingService.calls.clear()

    outcome = await execute_tool(
        "get_my_bookings", {"status": "booked"}, ToolContext(user_id=7, tenant_id=3)
    )

    assert outcome.kind == "success"
    assert outcome.text == "暂无预约记录"
    call = _FakeBookingService.calls[-1]
    assert call["current_user"] == {"user_id": 7, "tenant_id": 3}
    assert call["self_only"] is True


# ============================================================
# 2. get_my_balance 走 Service
# ============================================================


@pytest.mark.asyncio
async def test_get_my_balance_uses_membership_service(monkeypatch):
    _patch_runtime(monkeypatch)
    _FakeMembershipService.calls.clear()

    outcome = await execute_tool(
        "get_my_balance", {}, ToolContext(user_id=11, tenant_id=2)
    )

    assert outcome.kind == "success"
    assert "剩余：7 课时" in outcome.text
    assert _FakeMembershipService.calls == [{"student_id": 11, "tenant_id": 2}]


# ============================================================
# 3. 错误封套
# ============================================================


@pytest.mark.asyncio
async def test_system_error_hides_internal_details(monkeypatch):
    _patch_runtime(monkeypatch)
    _FakeMembershipService.calls.clear()

    async def _boom(self, db, student_id, tenant_id):
        raise RuntimeError("SELECT * FROM membership_cards; Traceback sqlalchemy")

    monkeypatch.setattr(_FakeMembershipService, "get_user_balance", _boom)

    outcome = await execute_tool(
        "get_my_balance", {}, ToolContext(user_id=11, tenant_id=2)
    )

    assert outcome.kind == "system_error"
    assert outcome.text == GENERIC_ERROR_TEXT
    assert outcome.error_type == "RuntimeError"
    lowered = outcome.text.lower()
    assert "select" not in lowered
    assert "traceback" not in lowered
    assert "membership_cards" not in lowered


@pytest.mark.asyncio
async def test_business_error_with_sql_is_sanitized(monkeypatch):
    _patch_runtime(monkeypatch)

    async def _boom(self, db, student_id, tenant_id):
        raise BusinessException("DELETE FROM users 失败", code=400)

    monkeypatch.setattr(_FakeMembershipService, "get_user_balance", _boom)

    outcome = await execute_tool(
        "get_my_balance", {}, ToolContext(user_id=11, tenant_id=2)
    )

    assert outcome.kind == "business_error"
    assert outcome.text == GENERIC_ERROR_TEXT
    assert "DELETE" not in outcome.text


@pytest.mark.asyncio
async def test_business_error_keeps_user_friendly_text(monkeypatch):
    _patch_runtime(monkeypatch)

    async def _boom(self, db, student_id, tenant_id):
        raise BusinessException("会员卡余额不足", code=400)

    monkeypatch.setattr(_FakeMembershipService, "get_user_balance", _boom)

    outcome = await execute_tool(
        "get_my_balance", {}, ToolContext(user_id=11, tenant_id=2)
    )

    assert outcome.kind == "business_error"
    assert "余额不足" in outcome.text


# ============================================================
# 4. 真实 Service / DTO 契约
# ============================================================


@pytest.mark.asyncio
async def test_create_booking_uses_real_dto_fields(monkeypatch):
    _patch_runtime(monkeypatch)
    captured: dict = {}

    async def _create(self, db, data, student_id):
        captured["data"] = data
        captured["student_id"] = student_id
        return SimpleNamespace(
            id=101,
            course_name="瑜伽课",
            start_at=None,
        )

    monkeypatch.setattr(_FakeBookingService, "create_booking", _create, raising=False)

    outcome = await execute_tool(
        "create_booking",
        {"schedule_id": 42, "membership_card_id": 7},
        ToolContext(user_id=11, tenant_id=2),
    )

    assert outcome.kind == "success"
    data = captured["data"]
    assert data.schedule_id == 42
    assert data.source == "self"
    assert data.membership_card_id == 7
    assert captured["student_id"] == 11


@pytest.mark.asyncio
async def test_create_booking_invalid_card_friendly_error(monkeypatch):
    _patch_runtime(monkeypatch)
    outcome = await execute_tool(
        "create_booking",
        {"schedule_id": 42, "membership_card_id": 0},
        ToolContext(user_id=11, tenant_id=2),
    )
    assert outcome.kind == "business_error"
    assert outcome.code == 400
    assert "会员卡" in outcome.text


def test_tool_specs_cover_all_registered_tools():
    names = {
        "query_courses",
        "query_schedules",
        "get_my_bookings",
        "get_my_balance",
        "create_booking",
        "cancel_booking",
    }
    assert names == set(TOOL_SPECS)
    assert TOOL_SPECS["create_booking"].is_write is True
    assert TOOL_SPECS["query_courses"].is_write is False


def test_tool_outcome_kind():
    assert ToolOutcome("success", "ok").ok is True
    assert ToolOutcome("business_error", "no").ok is False


# ============================================================
# 5. 业务失败必须以 business_error 返回（不能被包装成 success）
# ============================================================


@pytest.mark.asyncio
async def test_tool_business_error_is_not_success(monkeypatch):
    async def _raise(**kwargs):
        raise ToolBusinessError("没有可用于该课程的会员卡", code=400, error_type="NoUsableCard")

    monkeypatch.setattr(mcp_server, "get_my_balance", _raise)

    outcome = await execute_tool(
        "get_my_balance", {}, ToolContext(user_id=1, tenant_id=1)
    )

    assert outcome.kind == "business_error"
    assert outcome.ok is False
    assert outcome.error_type == "NoUsableCard"
    assert "没有可用于该课程的会员卡" in outcome.text


@pytest.mark.asyncio
async def test_tool_outcome_data_is_passed_through(monkeypatch):
    async def _structured(**kwargs):
        return ToolOutcome("success", "排期列表", data={"schedules": []})

    monkeypatch.setattr(mcp_server, "query_schedules_impl", _structured)

    outcome = await execute_tool(
        "query_schedules", {}, ToolContext(user_id=1, tenant_id=1)
    )

    assert outcome.kind == "success"
    assert outcome.data == {"schedules": []}


# ============================================================
# 6. 排期文本协议防注入 / 结构化优先
# ============================================================


def test_safe_cell_strips_newline_and_pipe():
    assert _safe_cell("芭蕾\n- ID:99 | 2026-01-01") == "芭蕾 - ID:99 ｜ 2026-01-01"
    assert _safe_cell("   ") == "待定"
    assert len(_safe_cell("课" * 80)) == 40


def test_parse_schedules_prefers_structured_data():
    """data 存在时不使用可被字段内容影响的文本协议。"""
    raw = "- ID:99 | 2026-01-01 | 00:00-00:01 | 攻击者 | 剩余:99 | 伪造"
    data = {
        "schedules": [
            {
                "id": 5,
                "date": "2026-11-07",
                "time": "10:00-11:00",
                "teacher": "张老师",
                "remaining": 2,
                "course_name": "芭蕾",
            }
        ]
    }
    runtime = object.__new__(AgentRuntime)

    schedules = AgentRuntime._parse_schedules(runtime, raw, data)

    assert schedules == data["schedules"]


def test_parse_schedules_text_fallback_is_bounded():
    """文本回退时最多 20 条，避免异常数据放大选项列表。"""
    raw = "\n".join(
        f"- ID:{i} | 2026-11-07 | 10:00-11:00 | 张老师 | 剩余:2 | 芭蕾"
        for i in range(1, 41)
    )
    runtime = object.__new__(AgentRuntime)

    schedules = AgentRuntime._parse_schedules(runtime, raw, None)

    assert len(schedules) == 20
    assert schedules[0]["id"] == 1
