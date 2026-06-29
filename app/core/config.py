from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""

    max_web_url: str = "https://web.max.ru/"
    max_check_interval_seconds: int = 3600
    max_initial_delay_seconds: int = 5
    max_page_load_timeout_ms: int = 60_000
    max_dom_settle_seconds: int = 8
    max_retry_interval_seconds: int = 60

    headless: bool = False
    browser_profile_path: Path = Path("/app/runtime/browser-profile")
    screenshots_path: Path = Path("/app/runtime/screenshots")
    logs_path: Path = Path("/app/runtime/logs")
    database_path: Path = Path("/app/runtime/data/app.db")
    heartbeat_path: Path = Path("/app/runtime/data/heartbeat.json")

    app_timezone: str = "Europe/Moscow"
    log_level: str = "INFO"
    send_startup_notification: bool = True
    send_initial_unread: bool = True
    auth_alert_interval_seconds: int = 21_600
    error_alert_interval_seconds: int = 21_600
    snapshot_retention_days: int = 30
    max_chats_in_notification: int = 10

    browser_width: int = 1440
    browser_height: int = 900

    @field_validator("max_check_interval_seconds")
    @classmethod
    def validate_interval(cls, value: int) -> int:
        if value < 60:
            raise ValueError("MAX_CHECK_INTERVAL_SECONDS не может быть меньше 60")
        return value

    @field_validator(
        "max_initial_delay_seconds",
        "max_dom_settle_seconds",
        "max_retry_interval_seconds",
        "auth_alert_interval_seconds",
        "error_alert_interval_seconds",
        "snapshot_retention_days",
        "max_chats_in_notification",
        "browser_width",
        "browser_height",
    )
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Значение не может быть отрицательным")
        return value

    def ensure_runtime_directories(self) -> None:
        for path in (
            self.browser_profile_path,
            self.screenshots_path,
            self.logs_path,
            self.database_path.parent,
            self.heartbeat_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def validate_main_runtime(self) -> None:
        if not self.telegram_bot_token.get_secret_value().strip():
            raise RuntimeError("В .env не заполнен TELEGRAM_BOT_TOKEN")
        if not self.telegram_chat_id.strip():
            raise RuntimeError("В .env не заполнен TELEGRAM_CHAT_ID")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
