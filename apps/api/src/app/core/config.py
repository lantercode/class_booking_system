"""应用配置 - 基于 Pydantic Settings 加载 .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root(start: Path) -> Path:
    current = start.resolve()
    for p in [current, *current.parents]:
        if (p / ".env").exists():
            return p
    for p in [current, *current.parents]:
        if (p / "pyproject.toml").exists():
            return p
    return current.parent


PROJECT_ROOT = _find_project_root(Path(__file__))

_env_file = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_env_file) if _env_file.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "dance-saas"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    DATABASE_URL: str = "postgresql+asyncpg://dance:dance_dev_pass@localhost:5432/dance_saas"
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI 对话限流（按登录用户，仅作用于 /api/v1/ai/chat）
    AI_CHAT_RATE_LIMIT: int = 20
    AI_CHAT_RATE_WINDOW: int = 60

    # ============================================================
    # AI LLM 接入（火山方舟 / 默认关闭，关闭时行为与纯规则链路一致）
    # ============================================================
    # 方舟密钥：只能来自环境变量 / .env.*，禁止硬编码；禁止出现在日志与异常中
    ARK_API_KEY: str = Field(default="", repr=False)
    AI_LLM_ENABLED: bool = False
    AI_LLM_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    AI_LLM_MODEL: str = "doubao-seed-2-1-lite-260915"
    # 模型白名单（逗号分隔），防止误配视频/高价模型
    AI_LLM_ALLOWED_MODELS: str = (
        "doubao-seed-2-1-lite-260915,"
        "doubao-seed-2-1-pro-260915,"
        "doubao-seed-2-0-lite-260428,"
        "doubao-seed-evolving"
    )
    # 单次模型调用超时（毫秒）
    AI_LLM_TIMEOUT_MS: int = 6000
    # 单次 /ai/chat 的 LLM 总预算（毫秒）
    AI_LLM_TOTAL_BUDGET_MS: int = 15000
    AI_LLM_MAX_TOKENS: int = 800
    AI_LLM_MAX_RETRIES: int = 2
    # 单请求最大模型调用轮次（Phase 2 默认 4；P95 超 12 秒时回退为 2）
    AI_LLM_MAX_TOOL_LOOPS: int = 4
    # 上下文裁剪：历史消息条数上限与字符预算（双限，优先保留最近消息）
    AI_LLM_HISTORY_LIMIT: int = 6
    AI_LLM_HISTORY_MAX_CHARS: int = 2000
    # 只读闸门：为 True 时写工具不进入模型可见工具集
    AI_LLM_READONLY_ONLY: bool = True
    # 写操作 Agent 总开关：仅当 READONLY_ONLY=False 且本项为 True 时写工具才可见
    AI_LLM_WRITE_TOOLS: bool = False
    # 租户灰度白名单（逗号分隔租户标识），空表示不启用
    AI_LLM_ENABLED_TENANTS: str = ""

    # ============================================================
    # 会员续费预警（站内消息；默认关闭，按租户灰度）
    # ============================================================
    AI_RENEWAL_ALERT_ENABLED: bool = False
    # N 天内到期即预警
    AI_RENEWAL_ALERT_DAYS: int = 7
    # 剩余课时 ≤ 阈值即预警
    AI_RENEWAL_ALERT_CREDITS_THRESHOLD: int = 3
    # 单租户每日最多发送条数（防打扰）
    AI_RENEWAL_ALERT_MAX_PER_DAY: int = 50
    # 租户白名单（逗号分隔 tenant_id），空表示不启用
    AI_RENEWAL_ALERT_TENANTS: str = ""

    # Redis 认证密码；开发环境可留空，生产环境必须设置
    REDIS_PASSWORD: str = ""

    JWT_SECRET: str = "change_me"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Token Blacklist 配置
    REDIS_TOKEN_BLACKLIST_PREFIX: str = "blacklist:"
    ENABLE_TOKEN_BLACKLIST: bool = True

    # RBAC 权限校验开关：False = 执行真实权限校验（生产必须为 False）
    # 仅限本地调试时临时置 True；禁止在任何部署环境中开启
    PERMISSION_CHECK_BYPASS: bool = False

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"

    WECHAT_APP_ID: str = ""
    WECHAT_SECRET: str = ""

    AUTO_FINISH_ENABLED: bool = True
    AUTO_FINISH_GRACE_MINUTES: int = 30

    # 自动取消人数不足课程
    AUTO_CANCEL_UNDERBOOKED_ENABLED: bool = True

    # F6.3：PENDING 期卡超期未激活自动作废
    PENDING_CARD_CANCEL_ENABLED: bool = True
    PENDING_CARD_CANCEL_DAYS: int = 90

    # ============================================================
    # 幂等键表（idempotency_keys）保留期清理
    # ============================================================
    # 总开关；关闭后每日生产者直接返回，不做任何删除
    IDEMPOTENCY_CLEANUP_ENABLED: bool = True
    # 保留天数：created_at 早于 now - N 天的记录视为过期
    IDEMPOTENCY_KEY_RETENTION_DAYS: int = 7
    # 单批删除行数（PostgreSQL 用 CTE + LIMIT 分批，避免长事务与锁表）
    IDEMPOTENCY_CLEANUP_BATCH_SIZE: int = 1000

    # ============================================================
    # 异步任务队列（JobQueue）
    # ============================================================
    # Worker 总开关；默认关闭，生产环境置 True
    TASK_WORKER_ENABLED: bool = False
    # 每轮 claim 批量捞取的最大任务数
    TASK_WORKER_BATCH_SIZE: int = 20
    # RUNNING 状态的租约超时（秒）；超过此值未更新租约的任务可被其他 Worker 捞回
    TASK_WORKER_LEASE_SECONDS: int = 120
    # 单次入队的最大重试次数（attempts 达到此值后标记为 DEAD，不再重试）
    TASK_WORKER_MAX_ATTEMPTS: int = 3
    # Worker 主循环 tick 间隔（秒）
    TASK_WORKER_TICK_SECONDS: float = 1.0

    # ---- 实时推送（阶段 4） ----
    NOTIFY_HEARTBEAT_SECONDS: int = 25
    NOTIFY_MAX_CONNECTIONS_PER_USER: int = 3
    # 单用户（user_id=0 为租户广播）每秒最多投递的信号数，超限丢弃（可凭 HTTP 补齐）
    NOTIFY_MAX_EVENTS_PER_SECOND: int = 20

    # ============================================================
    # F7：文件存储配置
    # ============================================================
    STORAGE_BACKEND: Literal["local", "oss"] = "local"

    # 本地存储（开发期降级方案）
    LOCAL_UPLOAD_DIR: str = str(PROJECT_ROOT / ".uploads")
    LOCAL_UPLOAD_PUBLIC_URL_PREFIX: str = "/uploads"

    # 阿里云 OSS（生产推荐）
    OSS_ENDPOINT: str = ""            # e.g. oss-cn-shanghai.aliyuncs.com
    OSS_REGION: str = ""              # e.g. cn-shanghai
    # 凭证模式：static=静态 AK/SK；ecs_role=ECS 实例 RAM 角色（STS 临时凭证，自动刷新）
    OSS_CREDENTIALS_MODE: Literal["static", "ecs_role"] = "static"
    OSS_ROLE_NAME: str = ""           # ecs_role 模式必填，e.g. class-booking-oss-role
    OSS_ACCESS_KEY_ID: str = ""       # 仅 static 模式使用
    OSS_ACCESS_KEY_SECRET: str = ""   # 仅 static 模式使用
    OSS_BUCKET: str = ""
    OSS_PUBLIC_BASE_URL: str = ""     # 可选；仅本地/公读场景直链使用，私有桶走预签名
    # 预签名有效期（秒）：默认 1 小时；上限 7 天（OSS 服务端限制 604800）
    OSS_PRESIGN_TTL_SECONDS: int = 3600

    @model_validator(mode="after")
    def validate_storage_backend(self) -> "Settings":
        """存储配置校验：生产禁用 local；oss 模式必填 OSS_*."""
        is_production = self.APP_ENV.strip().lower() == "production"

        if self.STORAGE_BACKEND == "local" and is_production:
            raise RuntimeError(
                "生产环境禁止 STORAGE_BACKEND=local；请配置阿里云 OSS 并设置 STORAGE_BACKEND=oss"
            )

        if self.STORAGE_BACKEND == "oss":
            missing: list[str] = []
            if not self.OSS_ENDPOINT:
                missing.append("OSS_ENDPOINT")
            if not self.OSS_REGION:
                missing.append("OSS_REGION")
            if not self.OSS_BUCKET:
                missing.append("OSS_BUCKET")
            if self.OSS_CREDENTIALS_MODE == "ecs_role":
                # ECS RAM 角色模式：AK/SK 由实例元数据服务签发，不应落盘
                if not self.OSS_ROLE_NAME:
                    missing.append("OSS_ROLE_NAME")
            else:
                if not self.OSS_ACCESS_KEY_ID:
                    missing.append("OSS_ACCESS_KEY_ID")
                if not self.OSS_ACCESS_KEY_SECRET:
                    missing.append("OSS_ACCESS_KEY_SECRET")

            if missing:
                raise ValueError(
                    f"STORAGE_BACKEND=oss 时以下配置项必填: {', '.join(missing)}"
                )

        # 预签名有效期：60 秒 ~ 7 天（OSS 服务端硬上限 604800 秒）
        if not 60 <= self.OSS_PRESIGN_TTL_SECONDS <= 604800:
            raise ValueError(
                "OSS_PRESIGN_TTL_SECONDS 必须在 60 ~ 604800（7 天）之间，"
                f"当前值 {self.OSS_PRESIGN_TTL_SECONDS}"
            )

        return self

    @model_validator(mode="after")
    def validate_llm(self) -> "Settings":
        """AI LLM 配置校验：仅在启用时校验，关闭状态下不因缺少 Key 启动失败。"""
        if not self.AI_LLM_ENABLED:
            return self

        if not self.ARK_API_KEY.strip():
            raise ValueError("启用 AI_LLM 时 ARK_API_KEY 必填（仅支持环境变量注入）")

        if self.AI_LLM_MODEL.strip() not in self.ai_llm_allowed_model_list:
            raise ValueError(
                f"AI_LLM_MODEL 不在 AI_LLM_ALLOWED_MODELS 允许清单内，当前值 {self.AI_LLM_MODEL!r}"
            )

        if self.AI_LLM_TIMEOUT_MS >= self.AI_LLM_TOTAL_BUDGET_MS:
            raise ValueError(
                "AI_LLM_TIMEOUT_MS 必须小于 AI_LLM_TOTAL_BUDGET_MS，"
                f"当前值 {self.AI_LLM_TIMEOUT_MS} >= {self.AI_LLM_TOTAL_BUDGET_MS}"
            )

        return self

    @property
    def is_production(self) -> bool:
        """便捷属性：是否运行在生产环境。"""
        return self.APP_ENV.strip().lower() == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def ai_llm_allowed_model_list(self) -> list[str]:
        """模型白名单（去空格后的列表）。"""
        return [m.strip() for m in self.AI_LLM_ALLOWED_MODELS.split(",") if m.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
