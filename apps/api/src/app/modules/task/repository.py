"""job_queue 数据访问层。

注意：不继承 TenantAwareRepository，因为 Worker 无 HTTP 请求上下文，
ContextVar 里的 tenant_id 为空；所有需要租户过滤的方法都显式传 tenant_id。
"""

import json
from datetime import UTC, datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert  # noqa: F401
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.modules.task.models import JobQueue, JobStatus


class JobQueueRepository(BaseRepository[JobQueue]):
    """任务队列表数据访问。"""

    model_class = JobQueue

    # ------------------------------------------------------------------
    # 入队（幂等）
    # ------------------------------------------------------------------

    # 原生 INSERT（跟 claim 同用原生 SQL，保证同一事务内快照一致可见）
    _ENQUEUE_SQL = text(
        """
        INSERT INTO job_queue
            (tenant_id, type, idempotency_key, payload, run_at, status)
        VALUES
            (:tenant_id, :type, :idempotency_key, CAST(:payload AS jsonb), :run_at, :status)
        ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
        RETURNING id, tenant_id, type, idempotency_key, payload, run_at, status
        """
    )

    async def enqueue(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        type: str,
        idempotency_key: str,
        payload: dict,
        run_at: datetime | None = None,
    ) -> dict | None:
        """入队一条延迟任务（原生 SQL INSERT，避免 ORM identity map 破坏事务快照可见性）。

        - 同一 (tenant_id, idempotency_key) 唯一约束冲突时返回 None（不抛异常）。
        - run_at 为 None 时默认立即执行（now()）。
        - 返回原生 SQL 行数据 dict（不是 ORM 对象），Worker 直接 dict 访问。
        - commit 由调用方控制（Worker 统一 commit 一个 tick，或手动调用方自行 commit）。
        """
        result = await db.execute(
            self._ENQUEUE_SQL.bindparams(
                tenant_id=tenant_id,
                type=type,
                idempotency_key=idempotency_key,
                payload=json.dumps(dict(payload)),
                run_at=run_at or datetime.now(UTC),
                status=JobStatus.PENDING,
            )
        )
        row = result.mappings().first()
        return dict(row) if row else None  # ON CONFLICT DO NOTHING 返回 None

    _UPSERT_SQL = text(
        """
        INSERT INTO job_queue
            (tenant_id, type, idempotency_key, payload, run_at, status)
        VALUES
            (:tenant_id, :type, :idempotency_key, CAST(:payload AS jsonb), :run_at, :status)
        ON CONFLICT (tenant_id, idempotency_key) DO UPDATE
        SET
            type        = EXCLUDED.type,
            payload     = EXCLUDED.payload,
            run_at      = EXCLUDED.run_at,
            status      = 'pending',
            attempts    = 0,
            last_error  = NULL,
            locked_by   = NULL,
            locked_at   = NULL,
            finished_at = NULL
        WHERE job_queue.status <> 'running'
        RETURNING id, tenant_id, type, idempotency_key, payload, run_at, status
        """
    )

    async def upsert(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        type: str,
        idempotency_key: str,
        payload: dict,
        run_at: datetime | None = None,
    ) -> dict | None:
        """投递或**覆盖**一条延迟任务（排期变更时重算 run_at）。

        与 ``enqueue`` 的区别：冲突时重置为 PENDING 并用新的 run_at/payload
        覆盖（重置 attempts / 错误信息 / 锁标记）。正在执行（running）的任务
        不覆盖，避免与 Worker 的 mark_done 互相踩踏；返回 None。
        """
        result = await db.execute(
            self._UPSERT_SQL.bindparams(
                tenant_id=tenant_id,
                type=type,
                idempotency_key=idempotency_key,
                payload=json.dumps(dict(payload)),
                run_at=run_at or datetime.now(UTC),
                status=JobStatus.PENDING,
            )
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def cancel_pending(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        idempotency_keys: list[str],
    ) -> int:
        """撤销尚未执行的延迟任务（置 DONE，终态不再执行）。返回影响行数。"""
        if not idempotency_keys:
            return 0
        result = await db.execute(
            text(
                """
                UPDATE job_queue
                SET status = 'done', finished_at = now(),
                    locked_by = NULL, locked_at = NULL
                WHERE tenant_id = :tenant_id
                  AND idempotency_key = ANY(:keys)
                  AND status IN ('pending', 'failed')
                """
            ).bindparams(tenant_id=tenant_id, keys=idempotency_keys)
        )
        return result.rowcount or 0

    # ------------------------------------------------------------------
    # Claim（FOR UPDATE SKIP LOCKED 多 Worker 互斥抢锁）
    # ------------------------------------------------------------------

    _CLAIM_SQL = text(
        """
        WITH claimed AS (
            SELECT id
            FROM job_queue
            WHERE (status = 'pending' AND run_at <= now())
               OR (status = 'failed')
               OR (
                    status = 'running'
                    AND locked_at + make_interval(secs => :lease) <= now()
                  )
            ORDER BY run_at ASC, id ASC
            LIMIT :batch
            FOR UPDATE SKIP LOCKED
        )
        UPDATE job_queue
        SET
            status     = 'running',
            locked_by  = :worker_id,
            locked_at  = now()
        FROM claimed
        WHERE job_queue.id = claimed.id
        RETURNING
            job_queue.id,
            job_queue.tenant_id,
            job_queue.type,
            job_queue.payload,
            job_queue.status,
            job_queue.attempts,
            job_queue.run_at,
            job_queue.idempotency_key,
            job_queue.locked_by
        """
    )

    async def claim_for_update_skip_locked(
        self,
        db: AsyncSession,
        *,
        worker_id: str,
        lease_seconds: int,
        batch_size: int,
    ) -> list[dict]:
        """原子 claim 一批任务，返回原生 SQL 行数据列表（dict）。

        - PENDING 且 run_at 已到 / FAILED / RUNNING 租约过期都能被 claim。
        - PostgreSQL FOR UPDATE SKIP LOCKED 保证多 Worker 不重复。
        - 返回的 dict 包含 id, tenant_id, type, payload, status, attempts 等。
        - 事务边界由调用方控制（Worker 负责 commit）。
        """
        result = await db.execute(
            self._CLAIM_SQL.bindparams(
                lease=lease_seconds,
                batch=batch_size,
                worker_id=worker_id,
            )
        )
        return [dict(row) for row in result.mappings().all()]

    # ------------------------------------------------------------------
    # 执行结果写回
    # ------------------------------------------------------------------

    async def mark_done(self, db: AsyncSession, job_id: int) -> None:
        """任务执行成功，标记为 DONE。"""
        stmt = (
            update(JobQueue)
            .where(JobQueue.id == job_id)
            .values(
                status=JobStatus.DONE,
                finished_at=func.now(),
                locked_by=None,
                locked_at=None,
            )
        )
        await db.execute(stmt)

    async def mark_failed(
        self,
        db: AsyncSession,
        job_id: int,
        error_text: str,
    ) -> None:
        """任务执行失败，attempts +1，状态置 FAILED（下次可被 claim 重试）。"""
        stmt = (
            update(JobQueue)
            .where(JobQueue.id == job_id)
            .values(
                status=JobStatus.FAILED,
                attempts=JobQueue.attempts + 1,
                last_error=error_text[:1000],  # 截断保护
                locked_by=None,
                locked_at=None,
            )
        )
        await db.execute(stmt)

    async def mark_dead(
        self,
        db: AsyncSession,
        job_id: int,
        error_text: str,
    ) -> None:
        """重试次数耗尽，标记 DEAD（终态，不再被 claim）。"""
        stmt = (
            update(JobQueue)
            .where(JobQueue.id == job_id)
            .values(
                status=JobStatus.DEAD,
                attempts=JobQueue.attempts + 1,
                last_error=error_text[:1000],
                finished_at=func.now(),
                locked_by=None,
                locked_at=None,
            )
        )
        await db.execute(stmt)

    # ------------------------------------------------------------------
    # 辅助查询
    # ------------------------------------------------------------------

    async def count_by_status(
        self,
        db: AsyncSession,
        *,
        tenant_id: int | None = None,
    ) -> dict[str, int]:
        """按 status 统计任务数量（可按租户过滤）。"""

        stmt = select(
            func.count().filter(JobQueue.status == JobStatus.PENDING),
            func.count().filter(JobQueue.status == JobStatus.RUNNING),
            func.count().filter(JobQueue.status == JobStatus.DONE),
            func.count().filter(JobQueue.status == JobStatus.FAILED),
            func.count().filter(JobQueue.status == JobStatus.DEAD),
        )
        if tenant_id is not None:
            stmt = stmt.where(JobQueue.tenant_id == tenant_id)
        result = await db.execute(stmt)
        p, r, d, f, dead = result.one()
        return {
            "pending": p,
            "running": r,
            "done": d,
            "failed": f,
            "dead": dead,
        }
