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
    OSS_ENDPOINT: str = ""            # e.g. oss-cn-hangzhou.aliyuncs.com
    OSS_REGION: str = ""              # e.g. cn-hangzhou
    OSS_ACCESS_KEY_ID: str = ""
    OSS_ACCESS_KEY_SECRET: str = ""
    OSS_BUCKET: str = ""
    OSS_PUBLIC_BASE_URL: str = ""     # 可选；留空则 Service 按 endpoint+bucket 拼接

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
            if not self.OSS_ACCESS_KEY_ID:
                missing.append("OSS_ACCESS_KEY_ID")
            if not self.OSS_ACCESS_KEY_SECRET:
                missing.append("OSS_ACCESS_KEY_SECRET")
            if not self.OSS_BUCKET:
                missing.append("OSS_BUCKET")
            if missing:
                raise ValueError(
                    f"STORAGE_BACKEND=oss 时以下配置项必填: {', '.join(missing)}"
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
