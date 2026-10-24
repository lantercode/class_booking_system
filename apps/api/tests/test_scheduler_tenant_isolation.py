"""
F1.5 定时任务租户隔离单元测试

测试内容：
- scheduler 函数对每个 ACTIVE 租户调用 set_tenant_id(tenant.id)
- 单个租户处理抛出异常时，循环继续处理后续租户（异常隔离）
- 每个租户处理完毕后调用 set_tenant_id(None) 清理上下文
- 无 ACTIVE 租户时函数直接返回，不调用 set_tenant_id

运行方式：
    cd apps/api
    uv run pytest tests/test_scheduler_tenant_isolation.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


class FakeTenant:
    """模拟 Tenant 模型，仅需 id 字段。"""

    def __init__(self, tenant_id: int):
        self.id = tenant_id


def _make_mock_session(empty_result: bool = True) -> AsyncMock:
    """构造一个支持 async with 的 mock 数据库会话。"""
    session = AsyncMock()
    # db.execute(...).scalars().all() -> []  (无业务数据)
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.all.return_value = []
    session.execute.return_value = result
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


# ---------------------------------------------------------------------------
# schedule/scheduler.py
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_finish_sets_tenant_id_for_each_tenant():
    """auto_finish_expired_schedules 对每个租户调用 set_tenant_id。"""
    from app.modules.schedule.scheduler import auto_finish_expired_schedules

    tenants = [FakeTenant(1), FakeTenant(2), FakeTenant(3)]
    mock_session = _make_mock_session()

    with patch(
        "app.modules.schedule.scheduler._get_active_tenants",
        new=AsyncMock(return_value=tenants),
    ), patch("app.modules.schedule.scheduler.set_tenant_id") as mock_set, patch(
        "app.modules.schedule.scheduler.SessionLocal", return_value=mock_session
    ), patch(
        "app.modules.schedule.scheduler.settings"
    ) as mock_settings:
        mock_settings.AUTO_FINISH_ENABLED = True
        mock_settings.AUTO_FINISH_GRACE_MINUTES = 30
        await auto_finish_expired_schedules()

    # 每个租户: set_tenant_id(id) -> 业务 -> set_tenant_id(None)
    expected = [call(1), call(None), call(2), call(None), call(3), call(None)]
    mock_set.assert_has_calls(expected, any_order=False)


@pytest.mark.asyncio
async def test_auto_finish_exception_isolation():
    """单租户抛异常时，后续租户仍被处理（异常隔离）。"""
    from app.modules.schedule.scheduler import auto_finish_expired_schedules

    tenants = [FakeTenant(11), FakeTenant(22)]
    # 第一个租户的 session.execute 抛异常，第二个租户正常
    bad_session = AsyncMock()
    bad_session.execute.side_effect = RuntimeError("boom tenant 11")
    bad_session.rollback = AsyncMock()

    good_session = _make_mock_session()

    # SessionLocal() 第一次返回 bad，第二次返回 good
    session_local = MagicMock(side_effect=[bad_session, good_session])

    with patch(
        "app.modules.schedule.scheduler._get_active_tenants",
        new=AsyncMock(return_value=tenants),
    ), patch("app.modules.schedule.scheduler.set_tenant_id") as mock_set, patch(
        "app.modules.schedule.scheduler.SessionLocal", session_local
    ), patch(
        "app.modules.schedule.scheduler.settings"
    ) as mock_settings:
        mock_settings.AUTO_FINISH_ENABLED = True
        mock_settings.AUTO_FINISH_GRACE_MINUTES = 30
        # 不应抛出异常
        await auto_finish_expired_schedules()

    # 两个租户都被处理（set_tenant_id 被调用了 11 和 22）
    called_ids = [c.args[0] for c in mock_set.call_args_list if c.args[0] is not None]
    assert called_ids == [11, 22], f"期望两个租户都被处理，实际: {called_ids}"


@pytest.mark.asyncio
async def test_auto_finish_no_active_tenants_skips():
    """无 ACTIVE 租户时直接返回，不调用 set_tenant_id。"""
    from app.modules.schedule.scheduler import auto_finish_expired_schedules

    with patch(
        "app.modules.schedule.scheduler._get_active_tenants",
        new=AsyncMock(return_value=[]),
    ), patch("app.modules.schedule.scheduler.set_tenant_id") as mock_set, patch(
        "app.modules.schedule.scheduler.settings"
    ) as mock_settings:
        mock_settings.AUTO_FINISH_ENABLED = True
        await auto_finish_expired_schedules()

    mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_auto_cancel_underbooked_sets_tenant_id():
    """auto_cancel_underbooked_schedules 对每个租户调用 set_tenant_id。"""
    from app.modules.schedule.scheduler import auto_cancel_underbooked_schedules

    tenants = [FakeTenant(5), FakeTenant(6)]
    mock_session = _make_mock_session()

    with patch(
        "app.modules.schedule.scheduler._get_active_tenants",
        new=AsyncMock(return_value=tenants),
    ), patch("app.modules.schedule.scheduler.set_tenant_id") as mock_set, patch(
        "app.modules.schedule.scheduler.SessionLocal", return_value=mock_session
    ), patch(
        "app.modules.schedule.scheduler.settings"
    ) as mock_settings:
        mock_settings.AUTO_CANCEL_UNDERBOOKED_ENABLED = True
        await auto_cancel_underbooked_schedules()

    called_ids = [c.args[0] for c in mock_set.call_args_list if c.args[0] is not None]
    assert called_ids == [5, 6]


# ---------------------------------------------------------------------------
# membership/scheduler.py
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_expire_membership_sets_tenant_id():
    """auto_expire_membership_cards 对每个租户调用 set_tenant_id。"""
    from app.modules.membership.scheduler import auto_expire_membership_cards

    tenants = [FakeTenant(101), FakeTenant(102)]
    mock_session = _make_mock_session()

    with patch(
        "app.modules.membership.scheduler._get_active_tenants",
        new=AsyncMock(return_value=tenants),
    ), patch("app.modules.membership.scheduler.set_tenant_id") as mock_set, patch(
        "app.modules.membership.scheduler.SessionLocal", return_value=mock_session
    ):
        await auto_expire_membership_cards()

    called_ids = [c.args[0] for c in mock_set.call_args_list if c.args[0] is not None]
    assert called_ids == [101, 102]


@pytest.mark.asyncio
async def test_notify_expiring_exception_isolation():
    """notify_expiring_membership_cards 单租户异常不影响后续租户。"""
    from app.modules.membership.scheduler import notify_expiring_membership_cards

    tenants = [FakeTenant(201), FakeTenant(202)]
    bad_session = AsyncMock()
    bad_session.execute.side_effect = RuntimeError("boom tenant 201")
    bad_session.rollback = AsyncMock()

    good_session = _make_mock_session()
    session_local = MagicMock(side_effect=[bad_session, good_session])

    with patch(
        "app.modules.membership.scheduler._get_active_tenants",
        new=AsyncMock(return_value=tenants),
    ), patch("app.modules.membership.scheduler.set_tenant_id") as mock_set, patch(
        "app.modules.membership.scheduler.SessionLocal", session_local
    ):
        await notify_expiring_membership_cards()

    called_ids = [c.args[0] for c in mock_set.call_args_list if c.args[0] is not None]
    assert called_ids == [201, 202], f"期望两个租户都被处理，实际: {called_ids}"


@pytest.mark.asyncio
async def test_auto_activate_membership_sets_tenant_id():
    """auto_activate_membership_cards 对每个租户调用 set_tenant_id。"""
    from app.modules.membership.scheduler import auto_activate_membership_cards

    tenants = [FakeTenant(301)]
    mock_session = _make_mock_session()

    with patch(
        "app.modules.membership.scheduler._get_active_tenants",
        new=AsyncMock(return_value=tenants),
    ), patch("app.modules.membership.scheduler.set_tenant_id") as mock_set, patch(
        "app.modules.membership.scheduler.SessionLocal", return_value=mock_session
    ):
        await auto_activate_membership_cards()

    called_ids = [c.args[0] for c in mock_set.call_args_list if c.args[0] is not None]
    assert called_ids == [301]


@pytest.mark.asyncio
async def test_auto_unfreeze_membership_sets_tenant_id():
    """auto_unfreeze_membership_cards 对每个租户调用 set_tenant_id。"""
    from app.modules.membership.scheduler import auto_unfreeze_membership_cards

    tenants = [FakeTenant(401), FakeTenant(402)]
    mock_session = _make_mock_session()

    with patch(
        "app.modules.membership.scheduler._get_active_tenants",
        new=AsyncMock(return_value=tenants),
    ), patch("app.modules.membership.scheduler.set_tenant_id") as mock_set, patch(
        "app.modules.membership.scheduler.SessionLocal", return_value=mock_session
    ):
        await auto_unfreeze_membership_cards()

    called_ids = [c.args[0] for c in mock_set.call_args_list if c.args[0] is not None]
    assert called_ids == [401, 402]


@pytest.mark.asyncio
async def test_membership_no_active_tenants_skips():
    """无 ACTIVE 租户时 membership 任务不调用 set_tenant_id。"""
    from app.modules.membership.scheduler import auto_expire_membership_cards

    with patch(
        "app.modules.membership.scheduler._get_active_tenants",
        new=AsyncMock(return_value=[]),
    ), patch("app.modules.membership.scheduler.set_tenant_id") as mock_set:
        await auto_expire_membership_cards()

    mock_set.assert_not_called()
