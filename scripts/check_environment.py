from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path

from app.core.config import get_settings
from app.integrations.telegram.client import TelegramClient


async def main() -> None:
    settings = get_settings()
    settings.ensure_runtime_directories()

    print("Проверка каталогов:")
    for path in (
        settings.browser_profile_path,
        settings.screenshots_path,
        settings.logs_path,
        settings.database_path.parent,
    ):
        test_file = Path(path) / ".write-test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        print(f"  OK: {path}")

    connection = sqlite3.connect(settings.database_path)
    connection.execute("SELECT 1")
    connection.close()
    print(f"SQLite: OK ({settings.database_path})")

    token = settings.telegram_bot_token.get_secret_value().strip()
    if token:
        telegram = TelegramClient(settings)
        try:
            bot = await telegram.validate()
            print(f"Telegram: OK (@{bot.get('username', 'без_username')})")
        finally:
            await telegram.close()
    else:
        print("Telegram: TELEGRAM_BOT_TOKEN пока не заполнен")

    display = os.environ.get("DISPLAY")
    print(f"DISPLAY: {display or 'не задан'}")
    print("Окружение готово.")


if __name__ == "__main__":
    asyncio.run(main())
