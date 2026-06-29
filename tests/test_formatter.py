from datetime import datetime, timezone

from app.core.config import Settings
from app.domain.models import UnreadChat, UnreadSnapshot
from app.integrations.telegram.formatter import TelegramFormatter


def test_unread_formatter_contains_chat_and_count() -> None:
    formatter = TelegramFormatter(Settings(app_timezone="UTC"))
    text = formatter.unread(
        UnreadSnapshot(
            total_unread=3,
            chats=[
                UnreadChat(
                    key="1",
                    name="Иван",
                    snippet="Привет",
                    unread_count=3,
                )
            ],
            captured_at=datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert "Непрочитанных: 3" in text
    assert "Иван (3)" in text
    assert "Привет" in text
