"""派生状态对账单测（阶段 6.2）。

覆盖：
- 空租户返回固定键集合且全为 0（SQL 可执行性）；
- 超期未激活期卡、到点人数不足排期能被计入差异（只读，不改数据）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.tenant_context import set_tenant_id
from app.modules.common.reconcile import _count_diffs
from app.modules.course.models import CourseType
from tests.membership_support import (
    create_course,
    create_schedule,
    db_factory,
    get_seed_ids,
)

TENANT_ID = 9999

DIFF_KEYS = {
    "schedule_finish_diff",
    "card_expired_diff",
    "card_activate_diff",
    "card_unfreeze_diff",
    "card_cancel_pending_diff",
    "schedule_underbooked_diff",
}


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

    assert diffs == {key: 0 for key in DIFF_KEYS}


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

    assert set(diffs) == DIFF_KEYS
    assert all(isinstance(v, int) and v >= 0 for v in diffs.values())


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        created = {"course_ids": [], "schedule_ids": [], "type_codes": [], "card_ids": []}
        yield factory, ids, created
        async with factory() as session:
            for cid in created["card_ids"]:
                await session.execute(
                    text("DELETE FROM membership_cards WHERE id = :i"), {"i": cid}
                )
            for sid in created["schedule_ids"]:
                await session.execute(
                    text("DELETE FROM course_schedules WHERE id = :i"), {"i": sid}
                )
            for cid in created["course_ids"]:
                await session.execute(text("DELETE FROM courses WHERE id = :i"), {"i": cid})
            for code in created["type_codes"]:
                await session.execute(
                    text("DELETE FROM course_types WHERE code = :c"), {"c": code}
                )
            await session.commit()


async def _diffs(factory, tenant_id: int) -> dict[str, int]:
    set_tenant_id(tenant_id)
    try:
        async with factory() as db:
            return await _count_diffs(
                db, tenant_id, now=datetime.now(UTC), grace=timedelta(minutes=30)
            )
    finally:
        set_tenant_id(None)


@pytest.mark.asyncio
async def test_underbooked_schedule_counted(env):
    factory, ids, created = env
    tenant_id = ids["tenant_id"]
    before = await _diffs(factory, tenant_id)

    code = f"rc-{uuid4().hex[:8]}"
    created["type_codes"].append(code)
    async with factory() as session:
        session.add(
            CourseType(
                tenant_id=tenant_id,
                name="对账测试类型",
                code=code,
                min_students=5,
                cancel_before_minutes=60,
            )
        )
        await session.commit()

    course_id = await create_course(factory, tenant_id, course_type_code=code)
    created["course_ids"].append(course_id)
    # 距开始 10 分钟：已过「开课前 60 分钟」截止点，且 0 人预约 < 5
    schedule_id = await create_schedule(
        factory,
        tenant_id,
        course_id=course_id,
        teacher_id=ids["teacher_id"],
        start_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    created["schedule_ids"].append(schedule_id)

    after = await _diffs(factory, tenant_id)
    assert after["schedule_underbooked_diff"] == before["schedule_underbooked_diff"] + 1


@pytest.mark.asyncio
async def test_stale_pending_card_counted(env):
    factory, ids, created = env
    tenant_id = ids["tenant_id"]
    before = await _diffs(factory, tenant_id)

    async with factory() as session:
        card_id = (
            await session.execute(
                text(
                    """
                    INSERT INTO membership_cards
                        (tenant_id, public_id, student_id, card_type, used_credits,
                         status, created_at, updated_at)
                    VALUES
                        (:tid, gen_random_uuid(), :sid, 'period', 0,
                         0, now() - interval '100 days', now())
                    RETURNING id
                    """
                ).bindparams(tid=tenant_id, sid=ids["student_id"])
            )
        ).scalar_one()
        await session.commit()
    created["card_ids"].append(card_id)

    after = await _diffs(factory, tenant_id)
    assert after["card_cancel_pending_diff"] == before["card_cancel_pending_diff"] + 1
