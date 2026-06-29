from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.domain.models import AuthProbe, UnreadSnapshot


class TelegramFormatter:
    def __init__(self, settings: Settings) -> None:
        self._timezone = ZoneInfo(settings.app_timezone)
        self._max_chats = settings.max_chats_in_notification

    def startup(self, interval_seconds: int) -> str:
        hours = interval_seconds / 3600
        interval = f"{hours:g} ч." if hours >= 1 else f"{interval_seconds} сек."
        return (
            "MAX → Telegram запущен\n\n"
            "Chromium открыт один раз и остаётся запущенным между проверками.\n"
            f"Интервал проверки: {interval}"
        )

    def unread(self, snapshot: UnreadSnapshot) -> str:
        lines = [
            "Новые сообщения в MAX",
            "",
            f"Непрочитанных: {snapshot.total_unread}",
        ]

        if snapshot.chats:
            lines.append("")
            for chat in snapshot.chats[: self._max_chats]:
                count = f" ({chat.unread_count})" if chat.unread_count > 1 else ""
                lines.append(f"• {chat.name}{count}")
                if chat.snippet and chat.snippet != chat.name:
                    lines.append(f"  {chat.snippet}")

            hidden = len(snapshot.chats) - self._max_chats
            if hidden > 0:
                lines.append(f"• Ещё чатов: {hidden}")
        else:
            lines.extend(
                [
                    "",
                    "MAX показывает непрочитанные сообщения, но имена чатов пока не удалось определить.",
                ]
            )

        lines.extend(["", f"Проверено: {self._format_time(snapshot.captured_at)}"])
        return "\n".join(lines)

    def auth_required(self, probe: AuthProbe) -> str:
        return (
            "Требуется вход в MAX\n\n"
            f"Причина: {probe.reason}\n\n"
            "Открой SSH-туннель к noVNC, зайди в веб-версию MAX и оставь вкладку открытой."
        )

    def unknown_page(self, probe: AuthProbe) -> str:
        return (
            "Не удалось распознать страницу MAX\n\n"
            f"Причина: {probe.reason}\n"
            f"Текущий адрес: {probe.url}\n\n"
            "Диагностические файлы сохранены в runtime/screenshots."
        )

    def error(self, error: Exception) -> str:
        return (
            "Ошибка проверки MAX\n\n"
            f"{type(error).__name__}: {error}\n\n"
            "Сервис продолжит работу и повторит проверку автоматически."
        )

    def test(self) -> str:
        return "Тестовое уведомление MAX → Telegram успешно отправлено."

    def _format_time(self, value: datetime) -> str:
        return value.astimezone(self._timezone).strftime("%d.%m.%Y %H:%M:%S")
