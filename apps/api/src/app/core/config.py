"""应用配置 - 基于 Pydantic Settings 加载 .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
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

    @property
    def is_production(self) -> bool:
        """便捷属性：是否运行在生产环境。"""
        return self.APP_ENV.strip().lower() == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
