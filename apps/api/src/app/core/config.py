"""应用配置 - 基于 Pydantic Settings 加载 .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "dance-saas"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    DATABASE_URL: str = "postgresql+asyncpg://dance:dance_dev_pass@localhost:5432/dance_saas"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "change_me"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Token Blacklist 配置
    REDIS_TOKEN_BLACKLIST_PREFIX: str = "blacklist:"
    ENABLE_TOKEN_BLACKLIST: bool = True

    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
