from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variables"""

    DEEPSEEK_API_KEY: str | None = None
    APIFY_API_TOKEN: str | None = None
    LOGFIRE_TOKEN: str | None = None
    BROWSERBASE_API_KEY: str | None = None
    BROWSERBASE_PROJECT_ID: str | None = None
    MAXIMUM_RETRIES: int = 2
    APP_NAME: str = "Flight Finder"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
