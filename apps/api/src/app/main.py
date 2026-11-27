"""FastAPI 应用入口."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings

# from starlette.middleware.sessions import Session
from app.core.database import SessionLocal
from app.core.exceptions import DanceSaasException
from app.core.oss_client import close_oss_client
from app.core.tenant_query import setup_tenant_query_injection
from app.deps.auth import get_redis_client
from app.middleware.error_handler import (
    dance_saas_exception_handler,
    integrity_error_handler,
    unhandled_exception_handler,
)
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.tenant_middleware import TenantASGIMiddleware
from app.modules.admin.router import router as admin_router  # ⭐ 新增：管理后台路由
from app.modules.ai.router import router as ai_router  # 🤖 新增：AI 智能助手路由
from app.modules.auth.router import router as auth_router
from app.modules.booking.router import router as booking_router  # ⭐ 新增：预约路由
from app.modules.classroom.router import router as classroom_router  # ⭐ 新增：教室路由
from app.modules.common.reconcile import reconcile_derived_status
from app.modules.common.router import router as common_router
from app.modules.course.router import router as course_router  # ⭐ 新增：课程路由（T05 占位）
from app.modules.home_config.router import router as home_config_router  # ⭐ 首页配置路由（F7.0.4）
from app.modules.membership.router import router as membership_router  # 会员卡路由
from app.modules.membership.scheduler import (
    auto_activate_membership_cards,
    auto_cancel_pending_membership_cards,
    auto_expire_membership_cards,
    auto_unfreeze_membership_cards,
    notify_expiring_membership_cards,
    send_renewal_alerts,
)
from app.modules.notification.router import router as notification_router
from app.modules.notify.bus import bus as notify_bus
from app.modules.notify.bus import start_listener as start_notify_listener
from app.modules.notify.bus import stop_listener as stop_notify_listener
from app.modules.notify.router import router as notify_router
from app.modules.role.router import router as role_router  # ⭐ 新增：角色权限路由
from app.modules.schedule.jobs import backfill_schedule_jobs
from app.modules.schedule.router import router as schedule_router  # 排期路由
from app.modules.schedule.scheduler import (
    auto_cancel_underbooked_schedules,
    auto_finish_expired_schedules,
)
from app.modules.task.service import HANDLERS
from app.modules.task.worker import JobWorker
from app.modules.teacher.router import router as teacher_router  # 教师路由
from app.modules.tenant.router import router as tenant_router  # 租户配置路由
from app.modules.upload.router import router as upload_router  # ⭐ 文件上传路由（F7.0.1）
from app.modules.user.router import router as user_router  # 用户管理路由

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器 - 初始化 Redis + 租户注入 + 定时任务"""
    # 1. 启用多租户查询自动注入
    setup_tenant_query_injection()
    print("✅ 多租户查询自动注入已启用")

    # 2. 检查并初始化 Redis
    print("检查 Redis 连接...")
    redis_client = await get_redis_client()
    if not redis_client:
        raise RuntimeError(
            "❌ Redis 不可用！生产环境必须启用 Redis。\n请检查: docker-compose up -d redis"
        )
    print("✅ Redis 连接正常！")

    # 2.1 启动实时推送 Redis 订阅（阶段 4）
    notify_bus.max_connections_per_user = settings.NOTIFY_MAX_CONNECTIONS_PER_USER
    notify_bus.max_events_per_second = settings.NOTIFY_MAX_EVENTS_PER_SECOND
    await start_notify_listener()
    print("✅ 实时推送订阅已启动")

    # 3. 启动 APScheduler 定时任务
    scheduler = AsyncIOScheduler(timezone="UTC")

    # 添加所有定时任务
    # ⚠️ 重要：任务执行顺序影响业务逻辑
    # 优先级：过期处理 > 激活 > 其他

    if settings.AUTO_FINISH_ENABLED:
        scheduler.add_job(
            auto_finish_expired_schedules,
            "interval",
            minutes=5,  # ⚠️ 开发环境测试：5分钟（生产环境请改回60）
            id="auto_finish_expired_schedules",
            replace_existing=True,
        )
        print(
            f"✅ 定时任务已注册: auto_finish_expired_schedules "
            f"(每 5min 运行 - 测试模式, grace={settings.AUTO_FINISH_GRACE_MINUTES}min)"
        )
    else:
        print("⚠️  AUTO_FINISH_ENABLED=false, 跳过定时任务注册")

    # 4. 【优先级1】启动会员卡自动过期定时任务（必须先执行）
    # 原因：其他任务依赖正确的卡状态，过期卡必须先被标记
    scheduler.add_job(
        auto_expire_membership_cards,
        "interval",
        minutes=60,
        id="auto_expire_membership_cards",
        replace_existing=True,
    )
    print("✅ 定时任务已注册: auto_expire_membership_cards (每 60min 运行)")

    # 5. 【优先级2】启动会员卡自动激活定时任务
    # 依赖：auto_expire 已正确标记过期卡状态
    scheduler.add_job(
        auto_activate_membership_cards,
        "interval",
        minutes=60,
        id="auto_activate_membership_cards",
        replace_existing=True,
    )
    print("✅ 定时任务已注册: auto_activate_membership_cards (每 60min 运行)")

    # 6. 启动会员卡到期提醒定时任务
    scheduler.add_job(
        notify_expiring_membership_cards,
        "interval",
        minutes=60,
        id="notify_expiring_membership_cards",
        replace_existing=True,
    )
    print("✅ 定时任务已注册: notify_expiring_membership_cards (每 60min 运行)")

    # 6.1 会员续费预警（站内消息，默认关闭）
    if settings.AI_RENEWAL_ALERT_ENABLED:
        scheduler.add_job(
            send_renewal_alerts,
            "interval",
            minutes=1440,
            id="send_renewal_alerts",
            replace_existing=True,
        )
        print(
            "✅ 定时任务已注册: send_renewal_alerts "
            f"(每 1440min 运行, days={settings.AI_RENEWAL_ALERT_DAYS})"
        )
    else:
        print("⚠️  AI_RENEWAL_ALERT_ENABLED=false, 跳过续费预警任务注册")

    # 7. 启动会员卡自动解冻定时任务
    scheduler.add_job(
        auto_unfreeze_membership_cards,
        "interval",
        minutes=60,
        id="auto_unfreeze_membership_cards",
        replace_existing=True,
    )
    print("✅ 定时任务已注册: auto_unfreeze_membership_cards (每 60min 运行)")

    # 7.1 【F6.3】启动 PENDING 期卡超期作废定时任务（每天一次）
    if settings.PENDING_CARD_CANCEL_ENABLED:
        scheduler.add_job(
            auto_cancel_pending_membership_cards,
            "interval",
            minutes=1440,
            id="auto_cancel_pending_membership_cards",
            replace_existing=True,
        )
        print(
            "✅ 定时任务已注册: auto_cancel_pending_membership_cards "
            f"(每 1440min 运行, days={settings.PENDING_CARD_CANCEL_DAYS})"
        )
    else:
        print("⚠️  PENDING_CARD_CANCEL_ENABLED=false, 跳过期卡作废任务注册")

    # 8. 启动自动取消人数不足课程定时任务
    scheduler.add_job(
        auto_cancel_underbooked_schedules,
        "interval",
        minutes=5,  # ⚠️ 开发环境测试：5分钟（生产环境请改回15）
        id="auto_cancel_underbooked_schedules",
        replace_existing=True,
    )
    print("✅ 定时任务已注册: auto_cancel_underbooked_schedules (每 5min 运行 - 测试模式)")

    # 8.1 每日派生状态对账（阶段 6.2）：比对「时间派生状态」与「落库状态」，仅输出差异
    # 每天 03:00（北京时间）跑一次；启动后 1 分钟先补跑一次，
    # 避免 interval=1440 首次执行要等 24 小时、开发环境频繁重启导致永不触发。
    scheduler.add_job(
        reconcile_derived_status,
        CronTrigger(hour=3, minute=0, timezone="Asia/Shanghai"),
        id="reconcile_derived_status",
        replace_existing=True,
        next_run_time=datetime.now(UTC) + timedelta(minutes=1),
    )
    print("✅ 定时任务已注册: reconcile_derived_status (每日 03:00 北京时间，启动后 1 分钟先跑一次)")

    # 8.2 阶段 6.1：Worker 模式下只下线「直写」的排期扫描任务。
    # 会员卡扫描保留：它们在 worker 模式下已改为「扫描候选 → 入队」，是生产者，
    # 若一并移除会导致卡激活/过期/解冻任务永远不被投递。
    if settings.TASK_WORKER_ENABLED:
        removed: list[str] = []
        for job_id in (
            "auto_finish_expired_schedules",
            "auto_cancel_underbooked_schedules",
        ):
            if scheduler.get_job(job_id) is not None:
                scheduler.remove_job(job_id)
                removed.append(job_id)
        if removed:
            print(f"⚠️  TASK_WORKER_ENABLED=true, 已下线排期直写扫描: {removed}")

        # 8.3 存量排期补投延迟任务（幂等）：上线前已存在的排期没有 job_queue 记录
        scheduler.add_job(
            backfill_schedule_jobs,
            "interval",
            minutes=10,
            id="backfill_schedule_jobs",
            replace_existing=True,
        )
        print("✅ 定时任务已注册: backfill_schedule_jobs (每 10min 运行 - 幂等补投)")

    # 9. 启动scheduler（在所有job添加完毕后）
    scheduler.start()
    print("✅ APScheduler 定时任务调度器已启动")

    # 10. 启动异步任务 Worker（JobQueue 消费者；默认关闭）
    worker: JobWorker | None = None
    if settings.TASK_WORKER_ENABLED:
        worker = JobWorker()
        worker.set_handlers(HANDLERS)
        await worker.start()
        print(
            f"✅ 异步任务 Worker 已启动: worker_id={worker.worker_id}, "
            f"handlers={list(HANDLERS.keys())}, "
            f"batch={settings.TASK_WORKER_BATCH_SIZE}, "
            f"lease={settings.TASK_WORKER_LEASE_SECONDS}s"
        )
    else:
        print("⚠️  TASK_WORKER_ENABLED=false, 跳过异步任务 Worker 启动")

    yield

    # 关闭时清理

    # 9.1 停止实时推送订阅
    try:
        await stop_notify_listener()
    except Exception as e:
        logger.warning(f"停止实时推送订阅时出错: {e}")

    # 10. 先优雅停止 Worker（等待在跑的任务完成，超时 10s 后 cancel）
    if worker is not None:
        try:
            await asyncio.wait_for(worker.stop(), timeout=15)
            print("⏹️  异步任务 Worker 已优雅停止")
        except TimeoutError:
            print("⚠️  异步任务 Worker 停止超时，已强制 cancel")
        except Exception as e:
            logger.warning(f"停止 Worker 时出错: {e}")

    try:
        await close_oss_client()
    except Exception as e:
        logger.warning(f"关闭 OSS 客户端时出错: {e}")

    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            print("⏹️  定时任务已停止")
    except Exception as e:
        logger.warning(f"停止定时任务时出错: {e}")


app = FastAPI(
    title="Dance SaaS API",
    description="舞蹈机构约课 SaaS 系统 API",
    version="0.1.0",
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
    redirect_slashes=False,
)
app.add_exception_handler(DanceSaasException, dance_saas_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ↓↓↓ 在这里添加租户中间件 ↓↓↓
app.add_middleware(TenantASGIMiddleware, session_factory=SessionLocal)

# ⭐ API 限流（仅作用于显式配置的路径，避免影响其他业务 API）
# Redis 客户端通过 get_redis_client 惰性获取（应用级单例，避免重复连接池）
app.add_middleware(
    RateLimiterMiddleware,
    redis_provider=get_redis_client,
    limit=settings.AI_CHAT_RATE_LIMIT,
    window=settings.AI_CHAT_RATE_WINDOW,
    path_limits={
        "/api/v1/ai/chat": (settings.AI_CHAT_RATE_LIMIT, settings.AI_CHAT_RATE_WINDOW),
    },
    # 已登录用户按 JWT user_id 限流，未带 Token 时降级为 IP
    user_key_paths=("/api/v1/ai/chat",),
    only_path_limits=True,
    exclude_paths=["/docs", "/redoc", "/openapi.json", "/health", "/api/v1/common/health"],
)

API_V1_PREFIX = "/api/v1"
app.include_router(common_router, prefix=API_V1_PREFIX)
app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(admin_router, prefix=API_V1_PREFIX)  # ⭐ 管理后台路由（含 RBAC 权限控制）
app.include_router(user_router, prefix=API_V1_PREFIX)  # ⭐ 用户管理路由
app.include_router(role_router, prefix=API_V1_PREFIX)  # ⭐ 角色权限路由
app.include_router(course_router, prefix=API_V1_PREFIX)  # ⭐ 课程路由（T05 占位）
app.include_router(classroom_router, prefix=API_V1_PREFIX)  # ⭐ 教室路由
app.include_router(schedule_router, prefix=API_V1_PREFIX)  # ⭐ 排期路由
app.include_router(booking_router, prefix=API_V1_PREFIX)  # ⭐ 预约路由
app.include_router(teacher_router, prefix=API_V1_PREFIX)  # 教师路由
app.include_router(tenant_router, prefix=API_V1_PREFIX)  # 租户配置路由
app.include_router(membership_router, prefix=API_V1_PREFIX)  # 会员卡路由
app.include_router(upload_router, prefix=API_V1_PREFIX)  # ⭐ 文件上传路由（F7.0.1）
app.include_router(home_config_router, prefix=API_V1_PREFIX)  # ⭐ 首页配置路由（F7.0.4）
app.include_router(notification_router, prefix=API_V1_PREFIX)  # ⭐ 站内消息路由
app.include_router(notify_router, prefix=API_V1_PREFIX)  # ⭐ 实时推送（SSE / WebSocket）
app.include_router(ai_router)  # AI 智能助手路由（已在 router.py 中定义前缀 /api/v1/ai）

# ⭐ 挂载静态文件服务（本地存储降级方案）；生产模式强制 STORAGE_BACKEND=oss 不走这里
if settings.STORAGE_BACKEND == "local":
    local_upload_dir = Path(settings.LOCAL_UPLOAD_DIR)
    local_upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        settings.LOCAL_UPLOAD_PUBLIC_URL_PREFIX,
        StaticFiles(directory=str(local_upload_dir)),
        name="uploads",
    )
