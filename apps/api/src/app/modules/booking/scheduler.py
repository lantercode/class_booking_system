"""预约模块定时任务：幂等键表（idempotency_keys）保留期清理。

租户隔离：
- 定时任务运行在 APScheduler 线程 / Worker，ContextVar 为空；先查所有 ACTIVE
  租户，循环内 ``set_tenant_id(tenant_id)`` 后处理，``finally`` 清理上下文。
- 单租户失败（含 Redis / 队列异常）只记录日志并继续，不影响其他租户。

双路径灰度（与 membership/scheduler.py 一致）：
- ``TASK_WORKER_ENABLED=true``：逐租户入队 ``cleanup_idempotency_keys``，幂等键按天；
- ``TASK_WORKER_ENABLED=false``：本线程直接调用同一 handler，避免重复实现清理逻辑。
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.tenant_context import set_tenant_id
from app.modules.tenant.models import Tenant, TenantStatus

logger = logging.getLogger(__name__)


async def _get_active_tenants():
    """查询所有状态为 ACTIVE 的租户列表。

    注意：Tenant 模型不含 tenant_id 字段，tenant_query 自动注入不会过滤此查询。
    """
    async with SessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.status == TenantStatus.ACTIVE.value)
        )
        return result.scalars().all()


async def cleanup_expired_idempotency_keys():
    """每日清理过期幂等键（默认保留 7 天，单批 1000 行）。

    ``IDEMPOTENCY_CLEANUP_ENABLED=false`` 时直接返回；否则逐 ACTIVE 租户执行：
    入队模式下只投递任务、由 JobWorker 消费；直调模式下本线程调用 handler。
    """
    settings = get_settings()
    if not settings.IDEMPOTENCY_CLEANUP_ENABLED:
        logger.info("[定时任务] IDEMPOTENCY_CLEANUP_ENABLED=false, 跳过幂等键清理")
        return

    from app.modules.task.service import cleanup_idempotency_keys, task_service

    via_queue = settings.TASK_WORKER_ENABLED
    job_date = datetime.now(UTC).strftime("%Y%m%d")
    payload = {"retention_days": settings.IDEMPOTENCY_KEY_RETENTION_DAYS}

    tenants = await _get_active_tenants()
    if not tenants:
        return

    for tenant in tenants:
        tenant_id = tenant.id
        set_tenant_id(tenant_id)
        try:
            async with SessionLocal() as db:
                if via_queue:
                    job = await task_service.enqueue(
                        db,
                        tenant_id=tenant_id,
                        type="cleanup_idempotency_keys",
                        # 按天去重：任务 DEAD 后次日仍可重新入队重试。
                        idempotency_key=f"idempotency_cleanup:{tenant_id}:{job_date}",
                        payload=payload,
                    )
                    await db.commit()
                    logger.info(
                        f"[定时任务][租户{tenant_id}] 幂等键清理"
                        f"{'已入队' if job is not None else '幂等命中（今日已入队）'}"
                    )
                else:
                    await cleanup_idempotency_keys(
                        db, dict(payload), tenant_id=tenant_id
                    )
                    await db.commit()
        except Exception as e:
            logger.exception(
                f"[定时任务][租户{tenant_id}] 幂等键清理失败，已跳过该租户: {e}"
            )
            continue
        finally:
            set_tenant_id(None)
