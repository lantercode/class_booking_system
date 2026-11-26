"""阶段 2.2 会员卡过期迁移测试。

覆盖：
- scheduler：Worker 启用 → 入队 ``expire_membership_card``；未启用 → 直接调 Service；
- Worker handler：无租户 ContextVar 环境下完成过期（次卡清零 + 流水）。
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.modules.membership.models import CardStatus, CardType
from app.modules.membership.scheduler import auto_expire_membership_cards
from app.modules.task.service import expire_membership_card
from tests.membership_support import (
    cleanup,
    count_transactions,
    create_card,
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


async def _expired_count_card(factory, ids, *, total: int = 5, used: int = 2) -> int:
    expire_at = datetime.now(UTC) - timedelta(days=1)
    return await create_card(
        factory, ids["tenant_id"], ids["student_id"],
        card_type=CardType.COUNT.value, status=CardStatus.ACTIVE.value,
        valid_from=day_start(expire_at - timedelta(days=29)),
        expire_at=expire_at, total_credits=total, used_credits=used,
        applicable_course_type_code=None,
    )


async def _delete_jobs(factory, tenant_id: int) -> None:
    async with factory() as session:
        await session.execute(
            text("DELETE FROM job_queue WHERE tenant_id = :tid"), {"tid": tenant_id}
        )
        await session.commit()


@pytest.mark.asyncio
async def test_scheduler_enqueues_when_worker_enabled(env):
    factory, ids = env
    card_id = await _expired_count_card(factory, ids)
    try:
        with (
            patch("app.modules.membership.scheduler.SessionLocal", new=factory),
            patch(
                "app.modules.membership.scheduler.get_settings",
                lambda: _settings(worker_enabled=True),
            ),
        ):
            await auto_expire_membership_cards()

        async with factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT type, payload FROM job_queue "
                        "WHERE tenant_id = :tid AND type = 'expire_membership_card'"
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

        # 入队模式下调度侧不改状态
        assert (await fetch_card(factory, ids["tenant_id"], card_id)).status == (
            CardStatus.ACTIVE.value
        )
    finally:
        await _delete_jobs(factory, ids["tenant_id"])
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_scheduler_expires_directly_when_worker_disabled(env):
    factory, ids = env
    card_id = await _expired_count_card(factory, ids)
    try:
        with (
            patch("app.modules.membership.scheduler.SessionLocal", new=factory),
            patch(
                "app.modules.membership.scheduler.get_settings",
                lambda: _settings(worker_enabled=False),
            ),
        ):
            await auto_expire_membership_cards()

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.EXPIRED.value
        assert card.used_credits == card.total_credits  # 剩余次数清零
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])


@pytest.mark.asyncio
async def test_handler_expires_card_without_tenant_context(env):
    factory, ids = env
    card_id = await _expired_count_card(factory, ids)
    try:
        # 不设置租户 ContextVar：模拟 Worker 环境
        async with factory() as db:
            await expire_membership_card(
                db, {"card_id": card_id}, tenant_id=ids["tenant_id"]
            )
            await db.commit()

        card = await fetch_card(factory, ids["tenant_id"], card_id)
        assert card.status == CardStatus.EXPIRED.value
        assert card.used_credits == card.total_credits

        # 幂等：二次执行不重复写流水
        async with factory() as db:
            await expire_membership_card(
                db, {"card_id": card_id}, tenant_id=ids["tenant_id"]
            )
            await db.commit()
        assert await count_transactions(factory, ids["tenant_id"], card_id) == 1
    finally:
        await cleanup(factory, ids["tenant_id"], card_ids=[card_id])
