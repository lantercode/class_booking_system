"""JobQueue + Worker 单测。

Repository 层：手动创建 tenant + enqueue/commit/claim/commit + 原生 SQL 验证 + finally 清理。
Worker 层：独立 session factory（自建 engine），手动 commit + finally 清理。
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.task.models import JobStatus
from app.modules.task.repository import JobQueueRepository
from app.modules.task.service import HANDLERS
from app.modules.task.worker import JobWorker
from app.modules.tenant.models import Tenant

# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


async def _seed_tenant(db: AsyncSession, *, tid: int = 9999, name: str = "tq") -> Tenant:
    """在 db 中 insert + flush 一个最小 ACTIVE tenant（原生 INSERT 避免 ORM identity map 问题）。"""
    await db.execute(text(
        """
        INSERT INTO tenants (id, public_id, name, slug, status, plan, settings)
        VALUES (:id, gen_random_uuid(), :name, :slug, 1, 'free', '{}')
        """
    ).bindparams(id=tid, name=name, slug=f"{name}-{tid}"))
    return Tenant(id=tid)


async def _cleanup_all(db: AsyncSession) -> None:
    await db.execute(text("DELETE FROM job_queue"))
    await db.execute(text("DELETE FROM tenants WHERE id >= 9990"))
    await db.commit()


def _make_sf():
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL, echo=False,
        pool_size=3, max_overflow=5, pool_pre_ping=True,
    )
    sf = async_sessionmaker(engine, expire_on_commit=False)
    return sf, engine


# ---------------------------------------------------------------------------
# 1. Repository 层（原生 SQL INSERT + 手动 commit + finally 清理）
# ---------------------------------------------------------------------------


class TestJobQueueRepository:
    """Repository 层：enqueue 返回 dict，claim 返回 dict 列表。"""

    # ---------- enqueue ----------

    async def test_enqueue_returns_dict(self, db_session):
        repo = JobQueueRepository()
        await _seed_tenant(db_session, tid=9999, name="eq")

        job = await repo.enqueue(
            db_session, tenant_id=9999, type="t",
            idempotency_key="q1", payload={"hello": "world"},
        )
        assert job is not None
        assert job["type"] == "t"
        assert job["status"] == JobStatus.PENDING

    async def test_enqueue_idempotent_dup_returns_none(self, db_session):
        repo = JobQueueRepository()
        await _seed_tenant(db_session, tid=9999, name="dup")

        first = await repo.enqueue(
            db_session, tenant_id=9999, type="t",
            idempotency_key="dup", payload={},
        )
        second = await repo.enqueue(
            db_session, tenant_id=9999, type="t",
            idempotency_key="dup", payload={"n": 2},
        )
        assert first is not None and second is None

    async def test_enqueue_distinct_tenants_same_key(self, db_session):
        repo = JobQueueRepository()
        await _seed_tenant(db_session, tid=9999, name="shared")
        await _seed_tenant(db_session, tid=9998, name="shared")

        j1 = await repo.enqueue(db_session, tenant_id=9999, type="t",
                                idempotency_key="shared", payload={})
        j2 = await repo.enqueue(db_session, tenant_id=9998, type="t",
                                idempotency_key="shared", payload={})
        assert j1 is not None and j2 is not None
        assert j1["id"] != j2["id"]

    # ---------- claim（原生 SQL INSERT 已落库才能被 CTE 看到）----------

    async def test_claim_pending_job_becomes_running(self, db_session):
        repo = JobQueueRepository()
        try:
            await _seed_tenant(db_session, tid=9999, name="c")
            await repo.enqueue(db_session, tenant_id=9999, type="t",
                               idempotency_key="c1", payload={})
            await db_session.commit()  # 让原生 INSERT 落库
            await db_session.execute(text("BEGIN"))

            claimed = await repo.claim_for_update_skip_locked(
                db_session, worker_id="w1", lease_seconds=120, batch_size=10,
            )
            assert len(claimed) == 1
            job = claimed[0]
            assert job["status"] == JobStatus.RUNNING
            assert job["locked_by"] == "w1"
        finally:
            await _cleanup_all(db_session)

    async def test_claim_skips_future_run_at(self, db_session):
        repo = JobQueueRepository()
        try:
            await _seed_tenant(db_session, tid=9999, name="f")
            future = datetime.now(UTC) + timedelta(minutes=30)
            await repo.enqueue(
                db_session, tenant_id=9999, type="t",
                idempotency_key="futu", payload={}, run_at=future,
            )
            await db_session.commit()
            await db_session.execute(text("BEGIN"))

            claimed = await repo.claim_for_update_skip_locked(
                db_session, worker_id="w1", lease_seconds=120, batch_size=10,
            )
            assert len(claimed) == 0
        finally:
            await _cleanup_all(db_session)

    # ---------- mark_* ----------

    async def test_mark_done_sets_finished_at(self, db_session):
        repo = JobQueueRepository()
        try:
            await _seed_tenant(db_session, tid=9999, name="md")
            job = await repo.enqueue(db_session, tenant_id=9999, type="t",
                                     idempotency_key="md", payload={})
            await db_session.commit()
            jid = job["id"]

            await db_session.execute(text("BEGIN"))
            await repo.claim_for_update_skip_locked(
                db_session, worker_id="w1", lease_seconds=120, batch_size=10,
            )
            await repo.mark_done(db_session, jid)

            # 原生 SQL 验证（避开 ORM identity map 缓存）
            row = (await db_session.execute(
                text("SELECT status, finished_at, locked_by FROM job_queue WHERE id = :i")
                .bindparams(i=jid)
            )).mappings().one()
            assert row["status"] == JobStatus.DONE
            assert row["finished_at"] is not None
            assert row["locked_by"] is None
        finally:
            await _cleanup_all(db_session)

    async def test_mark_failed_increments_attempts(self, db_session):
        repo = JobQueueRepository()
        try:
            await _seed_tenant(db_session, tid=9999, name="mf")
            job = await repo.enqueue(db_session, tenant_id=9999, type="t",
                                     idempotency_key="mf", payload={})
            await db_session.commit()
            jid = job["id"]

            await db_session.execute(text("BEGIN"))
            await repo.claim_for_update_skip_locked(
                db_session, worker_id="w1", lease_seconds=120, batch_size=10,
            )
            await repo.mark_failed(db_session, jid, "boom")

            row = (await db_session.execute(
                text("SELECT status, attempts, last_error FROM job_queue WHERE id = :i")
                .bindparams(i=jid)
            )).mappings().one()
            assert row["status"] == JobStatus.FAILED
            assert row["attempts"] == 1  # 0 → 1
            assert row["last_error"] == "boom"
        finally:
            await _cleanup_all(db_session)


# ---------------------------------------------------------------------------
# 2. Worker 层（独立 engine + session factory，手动 commit + finally 清理）
# ---------------------------------------------------------------------------


class TestJobWorker:
    """Worker 并发、租约、重试。"""

    async def _seed_tenant_and_jobs(self, sf, *, count=5, prefix="w") -> tuple[int, list[int]]:
        async with sf() as s:
            await _seed_tenant(s, tid=9999, name=prefix)
            repo = JobQueueRepository()
            ids = []
            for i in range(count):
                j = await repo.enqueue(
                    s, tenant_id=9999, type="test_worker",
                    idempotency_key=f"{prefix}-{i}", payload={"i": i},
                )
                ids.append(j["id"])
            await s.commit()
            return ids

    async def _finalize(self, sf, engine):
        try:
            async with sf() as s:
                await _cleanup_all(s)
        finally:
            await engine.dispose()

    # ---------- 并发抢锁 ----------

    async def test_concurrent_claim_no_overlap(self):
        sf, engine = _make_sf()
        try:
            ids = await self._seed_tenant_and_jobs(sf, count=5, prefix="cc")
            repo = JobQueueRepository()

            async def _claim(worker_id):
                async with sf() as s:
                    claimed = await repo.claim_for_update_skip_locked(
                        s, worker_id=worker_id, lease_seconds=120, batch_size=10,
                    )
                    await s.commit()
                    return {j["id"] for j in claimed}

            set_a, set_b = await asyncio.gather(_claim("A"), _claim("B"))
            assert set_a.isdisjoint(set_b)
            assert set_a | set_b == set(ids)
        finally:
            await self._finalize(sf, engine)

    # ---------- 租约回收 ----------

    async def test_lease_recovery_after_timeout(self):
        sf, engine = _make_sf()
        try:
            ids = await self._seed_tenant_and_jobs(sf, count=1, prefix="lr")
            repo = JobQueueRepository()
            LEASE = 2

            async with sf() as s1:
                claimed = await repo.claim_for_update_skip_locked(
                    s1, worker_id="A", lease_seconds=LEASE, batch_size=10,
                )
                await s1.commit()
                assert len(claimed) == 1

            await asyncio.sleep(LEASE + 1)

            # 轮询等待租约到期：固定 sleep 在机器负载高时可能仍判为未过期（flake）
            claimed_b: list[dict] = []
            deadline = asyncio.get_running_loop().time() + 8
            while not claimed_b and asyncio.get_running_loop().time() < deadline:
                async with sf() as s2:
                    claimed_b = await repo.claim_for_update_skip_locked(
                        s2, worker_id="B", lease_seconds=LEASE, batch_size=10,
                    )
                    await s2.commit()
                if not claimed_b:
                    await asyncio.sleep(0.5)

            assert len(claimed_b) == 1
            assert claimed_b[0]["id"] == ids[0]
            assert claimed_b[0]["locked_by"] == "B"
        finally:
            await self._finalize(sf, engine)

    # ---------- 重试到 DEAD ----------

    async def test_always_failing_handler_reaches_dead(self):
        sf, engine = _make_sf()
        try:
            ids = await self._seed_tenant_and_jobs(sf, count=1, prefix="ret")

            async def boom(db_sess, payload, *, tenant_id):
                raise RuntimeError("I always fail")

            worker = JobWorker(worker_id="tester", handlers={"test_worker": boom})
            worker._tick_seconds = 0.05
            worker._max_attempts = 3

            await worker.start()
            await asyncio.sleep(1.0)  # >= 4 轮 tick 保证重试到 DEAD
            await worker.stop(timeout=3)

            async with sf() as s:
                row = (await s.execute(
                    text("SELECT status, attempts, last_error FROM job_queue WHERE id = :i")
                    .bindparams(i=ids[0])
                )).mappings().one()
                assert row["status"] == JobStatus.DEAD
                assert row["attempts"] >= 3
                assert "I always fail" in (row["last_error"] or "")
        finally:
            await self._finalize(sf, engine)

    # ---------- 未知类型 → DEAD ----------

    async def test_unknown_handler_type_becomes_dead(self):
        sf, engine = _make_sf()
        try:
            async with sf() as s:
                await _seed_tenant(s, tid=9999, name="unk")
                repo = JobQueueRepository()
                j = await repo.enqueue(
                    s, tenant_id=9999, type="no_such_handler",
                    idempotency_key="unk", payload={},
                )
                await s.commit()
                jid = j["id"]

            worker = JobWorker(worker_id="unk-w", handlers={})
            worker._tick_seconds = 0.05
            await worker.start()
            await asyncio.sleep(0.5)
            await worker.stop(timeout=3)

            async with sf() as s:
                row = (await s.execute(
                    text("SELECT status, last_error FROM job_queue WHERE id = :i")
                    .bindparams(i=jid)
                )).mappings().one()
                assert row["status"] == JobStatus.DEAD
                assert "未知任务类型" in (row["last_error"] or "")
        finally:
            await self._finalize(sf, engine)

    # ---------- 优雅停机 ----------

    async def test_worker_graceful_stop_no_tasks(self):
        worker = JobWorker(worker_id="graceful", handlers=HANDLERS)
        worker._tick_seconds = 60

        await worker.start()
        await asyncio.sleep(0.05)

        await asyncio.wait_for(worker.stop(timeout=1), timeout=2)


# ---------------------------------------------------------------------------
# 3. Handler & Service 基本测试
# ---------------------------------------------------------------------------


class TestHandlerAndService:
    async def test_handlers_registered(self):
        assert "notify_renewal_alert" in HANDLERS
        assert callable(HANDLERS["notify_renewal_alert"])

    async def test_task_service_enqueue(self, db_session):
        from app.modules.task.service import task_service

        await _seed_tenant(db_session, tid=9999, name="svc")
        try:
            job = await task_service.enqueue(
                db_session,
                tenant_id=9999,
                type="notify_renewal_alert",
                idempotency_key="svc-1",
                payload={
                    "user_id": 1, "type": "renewal_alert",
                    "title": "t", "content": "c",
                    "idempotency_key": "note-1",
                },
            )
            assert job is not None
            assert job["type"] == "notify_renewal_alert"
        finally:
            await _cleanup_all(db_session)


# ---------------------------------------------------------------------------
# 4. 续费预警：调度触发 → 入队（P3-2）
# ---------------------------------------------------------------------------


def _renewal_settings(*, worker_enabled: bool):
    from types import SimpleNamespace

    return SimpleNamespace(
        TASK_WORKER_ENABLED=worker_enabled,
        AI_RENEWAL_ALERT_ENABLED=True,
        AI_RENEWAL_ALERT_TENANTS="9997",  # 白名单只放行本测试租户
        AI_RENEWAL_ALERT_DAYS=7,
        AI_RENEWAL_ALERT_CREDITS_THRESHOLD=3,
        AI_RENEWAL_ALERT_MAX_PER_DAY=10,
    )


async def _patch_renewal_candidates(monkeypatch, items: list[dict]) -> None:
    from app.ai.agent import renewal as renewal_mod
    from app.modules.membership.service import membership_card_service

    async def fake_list(db, tenant_id, **kwargs):
        return items

    async def fake_compose(item):
        return f"提醒-{item['card_id']}"

    monkeypatch.setattr(membership_card_service, "list_renewal_alerts", fake_list)
    monkeypatch.setattr(renewal_mod, "compose_renewal_content", fake_compose)


class TestRenewalAlertsDispatch:
    """P3-2：Worker 启用时入队，未启用时保持同步直发。"""

    RENEWAL_ITEMS = [
        {
            "card_id": 11, "student_id": 501, "product_name": "月卡",
            "remaining_credits": 2, "expire_at": datetime(2026, 11, 30, tzinfo=UTC),
        },
        {
            "card_id": 12, "student_id": 502, "product_name": "次卡",
            "remaining_credits": 1, "expire_at": None,
        },
    ]

    async def _prepare(self, db_session, monkeypatch, *, worker_enabled: bool):
        import app.modules.membership.scheduler as sched

        await _seed_tenant(db_session, tid=9997, name="renewal")
        await db_session.commit()
        await _patch_renewal_candidates(monkeypatch, self.RENEWAL_ITEMS)
        monkeypatch.setattr(
            sched, "get_settings",
            lambda: _renewal_settings(worker_enabled=worker_enabled),
        )
        return sched

    async def _cleanup(self, db_session) -> None:
        from app.core.database import engine as app_engine

        await db_session.execute(text("DELETE FROM notifications WHERE tenant_id = 9997"))
        await _cleanup_all(db_session)
        # send_renewal_alerts 使用全局 SessionLocal；每个测试是独立 event loop，
        # 释放连接池避免连接被下一个 loop 复用时报 "attached to a different loop"。
        await app_engine.dispose()

    async def test_worker_enabled_enqueues_jobs(self, db_session, monkeypatch):
        sched = await self._prepare(db_session, monkeypatch, worker_enabled=True)
        try:
            await sched.send_renewal_alerts()

            rows = (
                await db_session.execute(
                    text(
                        "SELECT tenant_id, type, idempotency_key, payload "
                        "FROM job_queue ORDER BY id"
                    )
                )
            ).mappings().all()
            assert len(rows) == 2
            assert {r["type"] for r in rows} == {"notify_renewal_alert"}
            assert all(r["tenant_id"] == 9997 for r in rows)

            payloads = [
                json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
                for r in rows
            ]
            assert {p["user_id"] for p in payloads} == {501, 502}
            assert {p["content"] for p in payloads} == {"提醒-11", "提醒-12"}
            assert all(p["type"] == "renewal_alert" for p in payloads)

            # 队列模式下不得直接落通知（发送交给 Worker）
            note_count = (
                await db_session.execute(
                    text("SELECT count(*) FROM notifications WHERE tenant_id = 9997")
                )
            ).scalar_one()
            assert note_count == 0
        finally:
            await self._cleanup(db_session)

    async def test_worker_disabled_sends_directly(self, db_session, monkeypatch):
        sched = await self._prepare(db_session, monkeypatch, worker_enabled=False)
        try:
            await sched.send_renewal_alerts()

            note_keys = (
                await db_session.execute(
                    text(
                        "SELECT idempotency_key FROM notifications "
                        "WHERE tenant_id = 9997 ORDER BY id"
                    )
                )
            ).scalars().all()
            assert len(note_keys) == 2
            assert set(note_keys) == {"renewal:11:20261130", "renewal:12:low_credits"}

            job_count = (
                await db_session.execute(
                    text("SELECT count(*) FROM job_queue WHERE tenant_id = 9997")
                )
            ).scalar_one()
            assert job_count == 0
        finally:
            await self._cleanup(db_session)

    async def test_enqueue_is_idempotent_per_day(self, db_session, monkeypatch):
        sched = await self._prepare(db_session, monkeypatch, worker_enabled=True)
        try:
            await sched.send_renewal_alerts()
            await sched.send_renewal_alerts()  # 同日重复触发

            job_count = (
                await db_session.execute(
                    text("SELECT count(*) FROM job_queue WHERE tenant_id = 9997")
                )
            ).scalar_one()
            assert job_count == 2
        finally:
            await self._cleanup(db_session)
