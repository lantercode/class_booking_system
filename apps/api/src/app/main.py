"""FastAPI 应用入口."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings

# from starlette.middleware.sessions import Session
from app.core.database import SessionLocal
from app.core.exceptions import DanceSaasException
from app.core.tenant_query import setup_tenant_query_injection
from app.deps.auth import get_redis_client
from app.middleware.error_handler import dance_saas_exception_handler
from app.middleware.tenant_middleware import TenantASGIMiddleware
from app.modules.admin.router import router as admin_router  # ⭐ 新增：管理后台路由
from app.modules.ai.router import router as ai_router  # 🤖 新增：AI 智能助手路由
from app.modules.auth.router import router as auth_router
from app.modules.booking.router import router as booking_router  # ⭐ 新增：预约路由
from app.modules.classroom.router import router as classroom_router  # ⭐ 新增：教室路由
from app.modules.common.router import router as common_router
from app.modules.course.router import router as course_router  # ⭐ 新增：课程路由（T05 占位）
from app.modules.membership.router import router as membership_router  # 会员卡路由
from app.modules.membership.scheduler import (
    auto_activate_membership_cards,
    auto_expire_membership_cards,
    auto_unfreeze_membership_cards,
    notify_expiring_membership_cards,
)
from app.modules.role.router import router as role_router  # ⭐ 新增：角色权限路由
from app.modules.schedule.router import router as schedule_router  # 排期路由
from app.modules.schedule.scheduler import (
    auto_cancel_underbooked_schedules,
    auto_finish_expired_schedules,
)
from app.modules.teacher.router import router as teacher_router  # 教师路由
from app.modules.tenant.router import router as tenant_router  # 租户配置路由
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
        minutes=5,  # ⚠️ 开发环境测试：5分钟（生产环境请改回60）
        id="auto_expire_membership_cards",
        replace_existing=True,
    )
    print("✅ 定时任务已注册: auto_expire_membership_cards (每 5min 运行 - 测试模式)")

    # 5. 【优先级2】启动会员卡自动激活定时任务
    # 依赖：auto_expire 已正确标记过期卡状态
    scheduler.add_job(
        auto_activate_membership_cards,
        "interval",
        minutes=5,  # ⚠️ 开发环境测试：5分钟（生产环境请改回30）
        id="auto_activate_membership_cards",
        replace_existing=True,
    )
    print("✅ 定时任务已注册: auto_activate_membership_cards (每 5min 运行 - 测试模式)")

    # 6. 启动会员卡到期提醒定时任务
    scheduler.add_job(
        notify_expiring_membership_cards,
        "interval",
        minutes=5,  # ⚠️ 开发环境测试：5分钟（生产环境请改回60）
        id="notify_expiring_membership_cards",
        replace_existing=True,
    )
    print("✅ 定时任务已注册: notify_expiring_membership_cards (每 5min 运行 - 测试模式)")

    # 7. 启动会员卡自动解冻定时任务
    scheduler.add_job(
        auto_unfreeze_membership_cards,
        "interval",
        minutes=5,  # ⚠️ 开发环境测试：5分钟（生产环境请改回30）
        id="auto_unfreeze_membership_cards",
        replace_existing=True,
    )
    print("✅ 定时任务已注册: auto_unfreeze_membership_cards (每 5min 运行 - 测试模式)")

    # 8. 启动自动取消人数不足课程定时任务
    scheduler.add_job(
        auto_cancel_underbooked_schedules,
        "interval",
        minutes=5,  # ⚠️ 开发环境测试：5分钟（生产环境请改回15）
        id="auto_cancel_underbooked_schedules",
        replace_existing=True,
    )
    print("✅ 定时任务已注册: auto_cancel_underbooked_schedules (每 5min 运行 - 测试模式)")

    # 9. 启动scheduler（在所有job添加完毕后）
    scheduler.start()
    print("✅ APScheduler 定时任务调度器已启动")

    yield

    # 关闭时清理
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ↓↓↓ 在这里添加租户中间件 ↓↓↓
app.add_middleware(TenantASGIMiddleware, session_factory=SessionLocal)

# ⭐ 新增：API 限流中间件配置（防止滥用）
# 注意：中间件将在 lifespan 中动态添加（因为 Redis 需要异步初始化）
RATE_LIMIT_CONFIG = {
    "limit": 100,  # 每分钟最多 100 次请求
    "window": 60,  # 时间窗口：60 秒
    "exclude_paths": ["/docs", "/redoc", "/openapi.json", "/health", "/api/v1/common/health"],
}

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
app.include_router(ai_router)  # AI 智能助手路由（已在 router.py 中定义前缀 /api/v1/ai）

# ⭐ 挂载静态文件服务，用于提供上传文件的访问
uploads_path = Path("./uploads")
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")
