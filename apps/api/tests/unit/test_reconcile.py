"""派生状态对账单测（阶段 6.2）。

只验证 `_count_diffs` 的 SQL 可执行性与空租户返回结构，不修改任何数据。
使用 db_session 的函数级事务，用例结束自动回滚。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.core.tenant_context import set_tenant_id
from app.modules.common.reconcile import _count_diffs

TENANT_ID = 9999


async def _seed_tenant(db) -> None:
    await db.execute(
        text(
            """
            INSERT INTO tenants (id, public_id, name, slug, status, plan, settings)
            VALUES (:id, gen_random_uuid(), 'reconcile-t', 'reconcile-9999', 1, 'free', '{}')
            """
        ).bindparams(id=TENANT_ID)
    )
    await db.flush()


async def test_count_diffs_zero_for_empty_tenant(db_session):
    await _seed_tenant(db_session)
    set_tenant_id(TENANT_ID)
    try:
        diffs = await _count_diffs(
            db_session, TENANT_ID, now=datetime.now(UTC), grace=timedelta(minutes=30)
        )
    finally:
        set_tenant_id(None)

    assert diffs == {
        "schedule_finish_diff": 0,
        "card_expired_diff": 0,
        "card_activate_diff": 0,
        "card_unfreeze_diff": 0,
    }


async def test_count_diffs_keys_are_stable(db_session):
    """返回键集合固定，避免后续消费方（监控/告警）改字段时静默失败。"""
    await _seed_tenant(db_session)
    set_tenant_id(TENANT_ID)
    try:
        diffs = await _count_diffs(
            db_session, TENANT_ID, now=datetime.now(UTC), grace=timedelta(minutes=0)
        )
    finally:
        set_tenant_id(None)

    assert set(diffs) == {
        "schedule_finish_diff",
        "card_expired_diff",
        "card_activate_diff",
        "card_unfreeze_diff",
    }
    assert all(isinstance(v, int) and v >= 0 for v in diffs.values())
