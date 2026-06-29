from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.integrations.telegram.client import TelegramClient
from app.integrations.telegram.formatter import TelegramFormatter


async def main() -> None:
    settings = get_settings()
    settings.validate_main_runtime()
    client = TelegramClient(settings)
    try:
        bot = await client.validate()
        await client.send_message(TelegramFormatter(settings).test())
        print(f"Готово. Бот: @{bot.get('username', 'без_username')}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
