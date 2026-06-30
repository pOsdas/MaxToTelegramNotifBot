import asyncio

from app.core.config import get_settings
from app.integrations.telegram.client import TelegramClient


async def main() -> None:
    settings = get_settings()
    client = TelegramClient(settings)
    try:
        bot = await client.validate()
        updates = await client.get_updates()
        print(f"Бот: @{bot.get('username', 'без_username')}")

        chats: dict[str, dict] = {}
        for update in updates:
            message = (
                update.get("message")
                or update.get("edited_message")
                or update.get("channel_post")
                or update.get("callback_query", {}).get("message")
            )
            if not message:
                continue
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id is not None:
                chats[str(chat_id)] = chat

        if not chats:
            print("Обновлений нет. Отправь боту /start и запусти команду ещё раз.")
            return

        print("Найденные чаты:")
        for chat_id, chat in chats.items():
            title = (
                chat.get("title")
                or " ".join(
                    part for part in (chat.get("first_name"), chat.get("last_name")) if part
                )
                or chat.get("username")
                or "Без названия"
            )
            print(f"TELEGRAM_CHAT_ID={chat_id}  |  {title}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
