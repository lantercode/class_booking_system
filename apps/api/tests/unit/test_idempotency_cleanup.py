"""幂等键表（idempotency_keys）保留期清理测试。

覆盖：
1. Worker handler：只删 ``created_at < now - retention`` 的记录，未过期保留；
2. 分批：过期数 > batch_size 时循环删除直到耗尽，总数正确（打印 deleted=总数）；
3. 调度侧双路径：``TASK_WORKER_ENABLED=true`` 只入队不删除；
   ``false`` 时同线程直调 handler 完成删除。

数据通过 tests.membership_support 的 db_factory / get_seed_ids 搭建，
用例结束按 key 精确清理，避免污染开发库。
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.tenant_context import set_tenant_id
from app.modules.booking.models import IdempotencyKey
from app.modules.booking.scheduler import cleanup_expired_idempotency_keys
from app.modules.task.service import cleanup_idempotency_keys
from tests.membership_support import db_factory, get_seed_ids

SCOPE = "booking.create"


@pytest.fixture(scope="function")
async def env():
    async with db_factory() as factory:
        ids = await get_seed_ids(factory)
        yield factory, ids


def _new_key() -> str:
    return f"cleanup-test-{uuid4().hex[:20]}"


async def _insert_keys(factory, tenant_id: int, rows: list[tuple[str, datetime]]) -> None:
    async with factory() as session:
        set_tenant_id(tenant_id)
        for key, created_at in rows:
            session.add(
                IdempotencyKey(
                    tenant_id=tenant_id,
                    scope=SCOPE,
                    key=key,
                    request_hash="x" * 64,
                    created_at=created_at,
                )
            )
        await session.commit()


async def _remaining_keys(factory, tenant_id: int, keys: list[str]) -> list[str]:
    """按 key 精确统计剩余记录（原生 SQL，不依赖 ContextVar）。"""
    async with factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT key FROM idempotency_keys "
                    "WHERE tenant_id = :tid AND key = ANY(:keys)"
                ),
                {"tid": tenant_id, "keys": keys},
            )
        ).scalars().all()
        return list(rows)


async def _delete_keys(factory, tenant_id: int, keys: list[str]) -> None:
    async with factory() as session:
        await session.execute(
            text(
                "DELETE FROM idempotency_keys "
                "WHERE tenant_id = :tid AND key = ANY(:keys)"
            ),
            {"tid": tenant_id, "keys": keys},
        )
        await session.commit()


async def _delete_jobs(factory, tenant_id: int) -> None:
    async with factory() as session:
        await session.execute(
            text("DELETE FROM job_queue WHERE tenant_id = :tid"), {"tid": tenant_id}
        )
        await session.commit()


# ---------------------------------------------------------------------------
# 1. Handler：保留期语义
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_deletes_only_expired_keys(env, capsys):
    factory, ids = env
    tenant_id = ids["tenant_id"]
    now = datetime.now(UTC)
    expired_keys = [_new_key(), _new_key()]
    fresh_key = _new_key()
    all_keys = [*expired_keys, fresh_key]
    await _insert_keys(
        factory,
        tenant_id,
        [
            (expired_keys[0], now - timedelta(days=8)),
            (expired_keys[1], now - timedelta(days=8)),
            (fresh_key, now - timedelta(hours=1)),
        ],
    )
    try:
        # 不设置租户 ContextVar：模拟 Worker 环境
        async with factory() as db:
            await cleanup_idempotency_keys(db, {"retention_days": 7}, tenant_id=tenant_id)
            await db.commit()

        remaining = await _remaining_keys(factory, tenant_id, all_keys)
        assert remaining == [fresh_key]
        assert f"tenant={tenant_id} deleted=2" in capsys.readouterr().out
    finally:
        await _delete_keys(factory, tenant_id, all_keys)


# ---------------------------------------------------------------------------
# 2. Handler：分批删除直到耗尽
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_deletes_in_batches(env, capsys):
    factory, ids = env
    tenant_id = ids["tenant_id"]
    now = datetime.now(UTC)
    keys = [_new_key() for _ in range(3)]
    await _insert_keys(
        factory,
        tenant_id,
        [(key, now - timedelta(days=10)) for key in keys],
    )
    try:
        # batch_size=2：第一轮删 2 条，第二轮删 1 条后结束（1 < 2）
        fake_settings = SimpleNamespace(
            IDEMPOTENCY_KEY_RETENTION_DAYS=7,
            IDEMPOTENCY_CLEANUP_BATCH_SIZE=2,
        )
        with patch("app.core.config.get_settings", lambda: fake_settings):
            async with factory() as db:
                await cleanup_idempotency_keys(
                    db, {"retention_days": 7}, tenant_id=tenant_id
                )
                await db.commit()

        assert await _remaining_keys(factory, tenant_id, keys) == []
        assert f"tenant={tenant_id} deleted=3" in capsys.readouterr().out
    finally:
        await _delete_keys(factory, tenant_id, keys)


# ---------------------------------------------------------------------------
# 3. 调度侧双路径
# ---------------------------------------------------------------------------


def _settings(*, worker_enabled: bool):
    return SimpleNamespace(
        IDEMPOTENCY_CLEANUP_ENABLED=True,
        IDEMPOTENCY_KEY_RETENTION_DAYS=7,
        TASK_WORKER_ENABLED=worker_enabled,
    )


@pytest.mark.asyncio
async def test_scheduler_enqueues_without_deleting_when_worker_enabled(env):
    factory, ids = env
    tenant_id = ids["tenant_id"]
    now = datetime.now(UTC)
    keys = [_new_key()]
    await _insert_keys(factory, tenant_id, [(keys[0], now - timedelta(days=8))])
    try:
        with (
            patch("app.modules.booking.scheduler.SessionLocal", new=factory),
            patch(
                "app.modules.booking.scheduler.get_settings",
                lambda: _settings(worker_enabled=True),
            ),
        ):
            await cleanup_expired_idempotency_keys()

        async with factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT idempotency_key FROM job_queue "
                        "WHERE tenant_id = :tid AND type = 'cleanup_idempotency_keys'"
                    ),
                    {"tid": tenant_id},
                )
            ).scalars().all()

        assert len(rows) == 1
        assert rows[0].startswith(f"idempotency_cleanup:{tenant_id}:")
        # 入队模式只投递，不在调度侧直接删除
        assert await _remaining_keys(factory, tenant_id, keys) == keys
    finally:
        await _delete_jobs(factory, tenant_id)
        await _delete_keys(factory, tenant_id, keys)


@pytest.mark.asyncio
async def test_scheduler_deletes_directly_when_worker_disabled(env):
    factory, ids = env
    tenant_id = ids["tenant_id"]
    now = datetime.now(UTC)
    expired_key = _new_key()
    fresh_key = _new_key()
    keys = [expired_key, fresh_key]
    await _insert_keys(
        factory,
        tenant_id,
        [
            (expired_key, now - timedelta(days=8)),
            (fresh_key, now - timedelta(hours=1)),
        ],
    )
    try:
        with (
            patch("app.modules.booking.scheduler.SessionLocal", new=factory),
            patch(
                "app.modules.booking.scheduler.get_settings",
                lambda: _settings(worker_enabled=False),
            ),
        ):
            await cleanup_expired_idempotency_keys()

        assert await _remaining_keys(factory, tenant_id, keys) == [fresh_key]
    finally:
        await _delete_jobs(factory, tenant_id)
        await _delete_keys(factory, tenant_id, keys)
