"""JobQueue Worker — 异步后台主循环，FOR UPDATE SKIP LOCKED 多实例互斥抢锁。

生命周期：
- main.py lifespan 用 ``asyncio.create_task(worker.run())`` 启动
- 关闭时 ``asyncio.wait_for(worker.stop(), timeout=10)`` 优雅退出
- Worker 内部用独立 ``SessionLocal()``，不走 HTTP 请求的 ContextVar

状态机：
    PENDING ──(claim)──→ RUNNING ──(success)──→ DONE
                          │
                          ├──(失败, attempts<MAX)──→ FAILED ──(下次被 claim)──→ RUNNING
                          └──(失败, attempts≥MAX)──→ DEAD (终态, 不再被 claim)

租约回收：
    RUNNING 状态的 locked_at + TASK_WORKER_LEASE_SECONDS <= now() 时，
    可被其他 Worker 捞回（原 Worker 崩溃或长时间阻塞）。
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import socket
import traceback
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.task.repository import JobQueueRepository

logger = logging.getLogger(__name__)


def _build_worker_id() -> str:
    """生成机器唯一标识（hostname[:pid]，最多 32 字符）。"""
    try:
        host = socket.gethostname()
    except Exception:
        host = platform.node() or "unknown"
    pid = os.getpid()
    raw = f"{host}-{pid}"
    return raw[:32]


class JobWorker:
    """异步任务 Worker。

    ``run()`` 是一个长期运行的主循环；``stop()`` 安全退出。
    Handler 注册表通过 ``set_handlers`` 注入（避免循环 import），
    或在 Worker 启动前调用 ``register_handler`` 逐个注册。
    """

    def __init__(
        self,
        *,
        worker_id: str | None = None,
        handlers: dict[str, Any] | None = None,
    ) -> None:
        self._worker_id = worker_id or _build_worker_id()
        self._repo = JobQueueRepository()
        self._handlers: dict[str, Any] = dict(handlers) if handlers else {}
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

        settings = get_settings()
        self._batch_size = settings.TASK_WORKER_BATCH_SIZE
        self._lease_seconds = settings.TASK_WORKER_LEASE_SECONDS
        self._max_attempts = settings.TASK_WORKER_MAX_ATTEMPTS
        self._tick_seconds = settings.TASK_WORKER_TICK_SECONDS

    # ------------------------------------------------------------------
    # Handler 注册
    # ------------------------------------------------------------------

    def register_handler(self, task_type: str, handler: Any) -> None:
        """注册单个 handler；覆盖同名类型。"""
        self._handlers[task_type] = handler

    def set_handlers(self, handlers: dict[str, Any]) -> None:
        """整体替换 handler 注册表。"""
        self._handlers = dict(handlers)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """主循环：claim → execute → writeback，tick 之间 sleep。"""
        logger.info(
            "[JobWorker] 启动 worker_id=%s, batch=%d, lease=%ds, max_attempts=%d, tick=%.1fs, handlers=%s",
            self._worker_id,
            self._batch_size,
            self._lease_seconds,
            self._max_attempts,
            self._tick_seconds,
            list(self._handlers.keys()),
        )
        try:
            while not self._stop_event.is_set():
                try:
                    processed = await self._tick_once()
                    if processed:
                        logger.debug("[JobWorker] tick 完成, 本批次处理 %d 条", processed)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # 单 tick 异常不应拖垮整个 Worker，下一轮继续
                    logger.exception("[JobWorker] tick 异常（已隔离，下一轮继续）")

                # sleep 直到 tick 到期或 stop_event 被 set
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self._tick_seconds,
                    )
                except TimeoutError:
                    pass  # 正常 tick 间隔到期
        finally:
            logger.info("[JobWorker] worker_id=%s 已退出", self._worker_id)

    async def start(self) -> asyncio.Task[None]:
        """非阻塞启动：将 ``run()`` 包装成 task 返回。"""
        if self._task and not self._task.done():
            return self._task
        self._task = asyncio.create_task(
            self.run(), name=f"job-worker-{self._worker_id}"
        )
        return self._task

    async def stop(self, timeout: float = 10.0) -> None:
        """优雅退出：设置 stop_event，等待 ``run()`` 结束。"""
        self._stop_event.set()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except TimeoutError:
                logger.warning(
                    "[JobWorker] 优雅退出超时 (%.1fs)，强制 cancel worker_id=%s",
                    timeout,
                    self._worker_id,
                )
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception("[JobWorker] 强制 cancel 后仍有异常")
            except asyncio.CancelledError:
                pass
        self._task = None

    @property
    def worker_id(self) -> str:
        return self._worker_id

    # ------------------------------------------------------------------
    # 内部：单次 tick
    # ------------------------------------------------------------------

    async def _tick_once(self) -> int:
        """执行一轮 claim → execute → writeback，返回处理的任务数量。"""
        async with SessionLocal() as db:
            jobs = await self._repo.claim_for_update_skip_locked(
                db,
                worker_id=self._worker_id,
                lease_seconds=self._lease_seconds,
                batch_size=self._batch_size,
            )
            if not jobs:
                return 0

            for job in jobs:
                await self._execute_one(db, job)

            await db.commit()
            return len(jobs)

    # ------------------------------------------------------------------
    # 内部：单任务执行
    # ------------------------------------------------------------------

    async def _execute_one(self, db: AsyncSession, job: dict) -> None:
        """执行单个任务，结果写回数据库。

        job 是原生 SQL claim 返回的 dict（字段：id, type, payload,
        attempts, tenant_id 等），直接 dict 访问避免 SQLAlchemy identity map
        破坏同一事务内原生 SQL 的快照可见性。
        """
        jid = job["id"]
        jtype = job["type"]
        jpayload = job["payload"]
        jtenant = job["tenant_id"]
        jattempts = job["attempts"] or 0

        handler = self._handlers.get(jtype)
        if handler is None:
            logger.error(
                "[JobWorker] 未知任务类型 id=%s type=%s tenant=%s",
                jid, jtype, jtenant,
            )
            await self._repo.mark_dead(db, jid, f"未知任务类型: {jtype}")
            return

        try:
            await handler(db, jpayload, tenant_id=jtenant)
            await self._repo.mark_done(db, jid)
            logger.info(
                "[JobWorker] ✅ DONE id=%s type=%s tenant=%s",
                jid, jtype, jtenant,
            )
        except Exception as exc:
            error_text = (
                f"{exc.__class__.__name__}: {exc}\n"
                f"{traceback.format_exc()}"
            )[:1000]
            next_attempts = jattempts + 1
            if next_attempts >= self._max_attempts:
                logger.error(
                    "[JobWorker] 💀 DEAD id=%s type=%s tenant=%s attempts=%d/%d 最后错误: %s",
                    jid, jtype, jtenant,
                    next_attempts, self._max_attempts, error_text[:200],
                )
                await self._repo.mark_dead(db, jid, error_text)
            else:
                logger.warning(
                    "[JobWorker] ⚠️ FAILED id=%s type=%s tenant=%s attempts=%d/%d 错误: %s",
                    jid, jtype, jtenant,
                    next_attempts, self._max_attempts, error_text[:200],
                )
                await self._repo.mark_failed(db, jid, error_text)
