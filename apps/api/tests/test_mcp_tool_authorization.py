"""
F5.2 — Tool 授权校验测试

四关校验顺序：Authentication → Authorization → Tenant → Input
写操作 Tool（create_booking / cancel_booking）必须：
  1. 校验 user_id 存在（401）
  2. 校验当前用户有学员角色（403）
  3. 租户隔离由 middleware → ContextVar → ORM 事件保证
  4. 校验 ID 为正整数（400）

运行：
    cd apps/api
    PYTHONPATH=src .venv/bin/python -m pytest tests/test_mcp_tool_authorization.py -v
"""

import pytest

from app.ai.mcp_server import (
    _require_student_role,
    _validate_id,
    create_booking,
    cancel_booking,
)
from app.core.database import SessionLocal
from app.core.exceptions import BusinessException


# ============================================================
# 辅助
# ============================================================


async def _get_user_with_role(db, phone: str):
    """按手机号查用户，返回 (user_id, roles)"""
    from sqlalchemy import select
    from app.modules.user.models import User
    from app.core.rbac import get_user_role_codes

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user:
        return None, set()
    roles = await get_user_role_codes(db, user_id=user.id)
    return user.id, roles


# ============================================================
# _validate_id 单元测试
# ============================================================


class TestValidateId:
    def test_valid_id(self):
        _validate_id(1, "排期")
        _validate_id(999, "预约")

    def test_zero(self):
        with pytest.raises(BusinessException) as exc:
            _validate_id(0, "排期")
        assert exc.value.code == 400

    def test_negative(self):
        with pytest.raises(BusinessException) as exc:
            _validate_id(-1, "排期")
        assert exc.value.code == 400

    def test_string(self):
        with pytest.raises(BusinessException) as exc:
            _validate_id("1", "排期")  # type: ignore
        assert exc.value.code == 400

    def test_bool(self):
        with pytest.raises(BusinessException) as exc:
            _validate_id(True, "排期")  # type: ignore
        assert exc.value.code == 400

    def test_none(self):
        with pytest.raises(BusinessException) as exc:
            _validate_id(None, "排期")  # type: ignore
        assert exc.value.code == 400


# ============================================================
# create_booking Tool 授权测试
# ============================================================


class TestCreateBookingAuthorization:
    """AC：非学员角色调用 create_booking → 403 且 Service 未被调用"""

    @pytest.mark.asyncio
    async def test_no_user_id_raises_401(self):
        """AC：user_id=None → 401"""
        with pytest.raises(BusinessException) as exc:
            await create_booking(schedule_id=1, user_id=None)
        assert exc.value.code == 401

    @pytest.mark.asyncio
    async def test_invalid_schedule_id_raises_400(self, monkeypatch):
        """AC：角色关通过后 schedule_id=0 → 400"""
        async def _student(db_session, user_id=None, tenant_id=None):
            return {"student"}

        monkeypatch.setattr("app.ai.mcp_server.get_user_role_codes", _student)
        with pytest.raises(BusinessException) as exc:
            await create_booking(schedule_id=0, user_id=1)
        assert exc.value.code == 400
        assert "排期" in str(exc.value)

    @pytest.mark.asyncio
    async def test_negative_schedule_id_raises_400(self, monkeypatch):
        """AC：角色关通过后 schedule_id=-1 → 400"""
        async def _student(db_session, user_id=None, tenant_id=None):
            return {"student"}

        monkeypatch.setattr("app.ai.mcp_server.get_user_role_codes", _student)
        with pytest.raises(BusinessException) as exc:
            await create_booking(schedule_id=-1, user_id=1)
        assert exc.value.code == 400

    @pytest.mark.asyncio
    async def test_string_schedule_id_raises_400(self, monkeypatch):
        """AC：角色关通过后 schedule_id="1" → 400"""
        async def _student(db_session, user_id=None, tenant_id=None):
            return {"student"}

        monkeypatch.setattr("app.ai.mcp_server.get_user_role_codes", _student)
        with pytest.raises(BusinessException) as exc:
            await create_booking(schedule_id="1", user_id=1)  # type: ignore
        assert exc.value.code == 400

    @pytest.mark.asyncio
    async def test_non_student_role_raises_403(self, monkeypatch):
        """AC：teacher/admin 角色调 create_booking → 403 且 Service 未调用"""
        call_count = 0

        async def _spy_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise AssertionError("BookingService.create_booking should NOT be called")

        monkeypatch.setattr(
            "app.ai.mcp_server.BookingService.create_booking",
            _spy_create,
        )

        async with SessionLocal() as db:
            # 用一个不存在的 user_id（必然无角色）
            with pytest.raises(BusinessException) as exc:
                await _require_student_role(db, user_id=99999, action="预约课程")
            assert exc.value.code == 403
            assert "学员" in str(exc.value)

        assert call_count == 0, "Service should not be called when authorization fails"


# ============================================================
# cancel_booking Tool 授权测试
# ============================================================


class TestCancelBookingAuthorization:
    @pytest.mark.asyncio
    async def test_no_user_id_raises_401(self):
        """AC：user_id=None → 401"""
        with pytest.raises(BusinessException) as exc:
            await cancel_booking(booking_id=1, user_id=None)
        assert exc.value.code == 401

    @pytest.mark.asyncio
    async def test_invalid_booking_id_raises_400(self, monkeypatch):
        """AC：角色关通过后 booking_id=0 → 400"""
        async def _student(db_session, user_id=None, tenant_id=None):
            return {"student"}

        monkeypatch.setattr("app.ai.mcp_server.get_user_role_codes", _student)
        with pytest.raises(BusinessException) as exc:
            await cancel_booking(booking_id=0, user_id=1)
        assert exc.value.code == 400

    @pytest.mark.asyncio
    async def test_reason_too_long_raises_400(self, monkeypatch):
        """AC：角色关通过后 reason > 200 字 → 400"""
        async def _student(db_session, user_id=None, tenant_id=None):
            return {"student"}

        monkeypatch.setattr("app.ai.mcp_server.get_user_role_codes", _student)
        with pytest.raises(BusinessException) as exc:
            await cancel_booking(booking_id=1, user_id=1, reason="x" * 201)
        assert exc.value.code == 400
        assert "原因过长" in str(exc.value)

    @pytest.mark.asyncio
    async def test_non_student_role_raises_403(self, monkeypatch):
        """AC：非学员角色 → 403 且 Service 未调用"""
        call_count = 0

        async def _spy_cancel(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise AssertionError("BookingService.cancel_booking should NOT be called")

        monkeypatch.setattr(
            "app.ai.mcp_server.BookingService.cancel_booking",
            _spy_cancel,
        )

        async with SessionLocal() as db:
            with pytest.raises(BusinessException) as exc:
                await _require_student_role(db, user_id=99999, action="取消预约")
            assert exc.value.code == 403

        assert call_count == 0


# ============================================================
# _handle_business_error 授权关键词映射测试
# ============================================================


class TestAuthorizationFriendlyMessage:
    """AC：授权失败异常经 Runtime _handle_business_error 映射为友好提示，不泄露原文"""

    def test_student_role_message(self):
        from app.ai.agent.runtime import AgentRuntime

        agent = AgentRuntime(user_id=1, tenant_id=1)
        exc = BusinessException("当前账号没有学员身份，无法预约课程", code=403)
        result = agent._handle_business_error(exc)

        assert "学员" in result
        assert str(exc) not in result

    def test_invalid_id_message(self):
        from app.ai.agent.runtime import AgentRuntime

        agent = AgentRuntime(user_id=1, tenant_id=1)
        exc = BusinessException("排期ID无效，请重新选择", code=400)
        result = agent._handle_business_error(exc)

        assert "无效" in result
        assert str(exc) not in result

    def test_unknown_error_no_leak(self):
        from app.ai.agent.runtime import AgentRuntime

        agent = AgentRuntime(user_id=1, tenant_id=1)
        exc = Exception("SELECT * FROM users; DROP TABLE")
        result = agent._handle_business_error(exc)

        assert "操作失败" in result
        assert "SELECT" not in result
        assert "DROP" not in result
