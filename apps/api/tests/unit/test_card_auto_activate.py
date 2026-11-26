"""P3-2.1 会员卡自动激活迁移测试。

覆盖三条链路：
1. ``MembershipCardService.auto_activate_card``：到点激活 / 未到点 / 冲突 / 幂等；
2. scheduler：Worker 启用 → 入队 ``activate_membership_card``；未启用 → 直接调 Service；
3. Worker handler：无租户 ContextVar 的环境下也能完成激活。
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.modules.membership.models import CardStatus, CardType
from app.modules.membership.scheduler import auto_activate_membership_cards
from app.modules.membership.service import membership_card_service
from app.modules.task.service import activate_membership_card
from tests.membership_support import (
    cleanup,
    count_transactions,
    create_card,
    create_product,
    day_end,
    day_start,
    db_factory,
    fetch_card,
    get_seed_ids,
)


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        yield factory, ids


def _settings(*, worker_enabled: bool):
    return SimpleNamespace(TASK_WORKER_ENABLED=worker_enabled)


async def _delete_jobs(factory, tenant_id: int) -> None:
    async with factory() as session:
        await session.execute(
            text("DELETE FROM job_queue WHERE tenant_id = :tid"), {"tid": tenant_id}
        )
        await session.commit()


# ---------------------------------------------------------------------------
# 1. Service 层
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_activate_due_pending_card(env):
    factory, ids = env
    valid_from = day_start(datetime.now(UTC) - timedelta(days=3))
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=30, valid_from=valid_from,
        expire_at=day_end(valid_from + timedelta(days=29)),
        applicable_course_type_code=None,  # 不参与冲突判断，聚焦激活本身
    )
    try:
        # 不设置租户 ContextVar：模拟 Worker 环境
        async with factory() as db:
            card = await membership_card_service.auto_activate_card(
                db, card_id, ids["tenant_id"]
            )
            await db.commit()

        assert card is not None
        assert card.status == CardStatus.ACTIVE.value
        # expire_at 基于 valid_from 快照重算：valid_from + 29 天 23:59:59
        assert card.expire_at == day_end(valid_from + timedelta(days=29))
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1

        # 幂等：再执行一次不重复激活、不重复写流水
        async with factory() as db:
            again = await membership_card_service.auto_activate_card(
                db, card_id, ids["tenant_id"]
            )
            await db.commit()
        assert again is None
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_auto_activate_skips_card_not_yet_valid(env):
    factory, ids = env
    valid_from = day_start(datetime.now(UTC) + timedelta(days=2))
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=30, valid_from=valid_from,
        expire_at=day_end(valid_from + timedelta(days=29)),
    )
    try:
        async with factory() as db:
            card = await membership_card_service.auto_activate_card(
                db, card_id, ids["tenant_id"]
            )
            await db.commit()
        assert card is None
        assert (await fetch_card(factory, ids["tenant_id"], card_id)).status == (
            CardStatus.PENDING.value
        )
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_auto_activate_skips_conflicting_period_card(env):
    factory, ids = env
    now = datetime.now(UTC)
    existing_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.ACTIVE.value,
        validity_days=30, valid_from=day_start(now - timedelta(days=5)),
        expire_at=day_end(now + timedelta(days=24)),
        applicable_course_type_code="regular",
    )
    pending_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=30, valid_from=day_start(now - timedelta(days=1)),
        expire_at=day_end(now + timedelta(days=28)),
        applicable_course_type_code="regular",
    )
    try:
        async with factory() as db:
            card = await membership_card_service.auto_activate_card(
                db, pending_id, ids["tenant_id"]
            )
            await db.commit()
        assert card is None
        assert (await fetch_card(factory, ids["tenant_id"], pending_id)).status == (
            CardStatus.PENDING.value
        )
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[existing_id, pending_id])


@pytest.mark.asyncio
async def test_auto_activate_falls_back_to_product_validity_days(env):
    factory, ids = env
    product_id = await create_product(
        factory, ids["tenant_id"],
        card_type=CardType.COUNT.value, validity_days=10,
        total_credits=5, applicable_course_type_code=None,
    )
    valid_from = day_start(datetime.now(UTC) - timedelta(days=1))
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.COUNT.value, status=CardStatus.PENDING.value,
        validity_days=None, product_id=product_id,
        valid_from=valid_from, expire_at=None,
        total_credits=5, applicable_course_type_code=None,
    )
    try:
        async with factory() as db:
            card = await membership_card_service.auto_activate_card(
                db, card_id, ids["tenant_id"]
            )
            await db.commit()
        assert card is not None
        assert card.expire_at == day_end(valid_from + timedelta(days=9))
    finally:
        await cleanup(
            factory, ids["tenant_id"],
            card_ids=[card_id], product_ids=[product_id],
        )


# ---------------------------------------------------------------------------
# 2. Scheduler（Worker 开关双路径）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_enqueues_when_worker_enabled(env):
    factory, ids = env
    valid_from = day_start(datetime.now(UTC) - timedelta(days=2))
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=30, valid_from=valid_from,
        expire_at=day_end(valid_from + timedelta(days=29)),
        applicable_course_type_code=None,
    )
    try:
        with (
            patch("app.modules.membership.scheduler.SessionLocal", new=factory),
            patch(
                "app.modules.membership.scheduler.get_settings",
                lambda: _settings(worker_enabled=True),
            ),
        ):
            await auto_activate_membership_cards()

        async with factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT type, payload FROM job_queue "
                        "WHERE tenant_id = :tid AND type = 'activate_membership_card'"
                    ),
                    {"tid": ids["tenant_id"]},
                )
            ).mappings().all()

        assert len(rows) == 1
        payload = rows[0]["payload"]
        if isinstance(payload, str):
            import json

            payload = json.loads(payload)
        assert payload["card_id"] == card_id

        # 入队模式下调度侧不直接改状态
        assert (await fetch_card(factory, ids["tenant_id"], card_id)).status == (
            CardStatus.PENDING.value
        )
    finally:
        await _delete_jobs(factory, ids["tenant_id"])
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_scheduler_activates_directly_when_worker_disabled(env):
    factory, ids = env
    valid_from = day_start(datetime.now(UTC) - timedelta(days=2))
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=30, valid_from=valid_from,
        expire_at=day_end(valid_from + timedelta(days=29)),
        applicable_course_type_code=None,
    )
    try:
        with (
            patch("app.modules.membership.scheduler.SessionLocal", new=factory),
            patch(
                "app.modules.membership.scheduler.get_settings",
                lambda: _settings(worker_enabled=False),
            ),
        ):
            await auto_activate_membership_cards()

        assert (await fetch_card(factory, ids["tenant_id"], card_id)).status == (
            CardStatus.ACTIVE.value
        )
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


# ---------------------------------------------------------------------------
# 3. Worker handler（无 ContextVar）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_activates_card_without_tenant_context(env):
    factory, ids = env
    valid_from = day_start(datetime.now(UTC) - timedelta(days=1))
    card_id = await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.PERIOD.value, status=CardStatus.PENDING.value,
        validity_days=30, valid_from=valid_from,
        expire_at=day_end(valid_from + timedelta(days=29)),
        applicable_course_type_code=None,
    )
    try:
        async with factory() as db:
            await activate_membership_card(
                db, {"card_id": card_id}, tenant_id=ids["tenant_id"]
            )
            await db.commit()

        assert (await fetch_card(factory, ids["tenant_id"], card_id)).status == (
            CardStatus.ACTIVE.value
        )
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])
