from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "FlyRank Widget Platform"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    FRONTEND_ORIGIN: str = "http://localhost:5500"
    RATE_LIMIT_PER_MINUTE: int = 10
    AUTH_LOGIN_RATE_LIMIT_PER_MINUTE: int = 5
    AUTH_REGISTER_RATE_LIMIT_PER_MINUTE: int = 3

    NOTIFICATION_WEBHOOK_URL: str = ""
    NOTIFICATION_EMAIL_TO: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True

    NOTIFICATION_POLL_SECONDS: int = 5
    NOTIFICATION_MAX_ATTEMPTS: int = 5
    NOTIFICATION_FAILURE_ALERT_EMAIL: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
