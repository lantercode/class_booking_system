"""应用配置 - 基于 Pydantic Settings 加载 .env."""

from functools import lru_cache
from pathlib import Path

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

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
