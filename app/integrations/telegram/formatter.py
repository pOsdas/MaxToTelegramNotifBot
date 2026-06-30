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

    def parser_problem(
        self,
        result,
        attempts: int,
    ) -> str:
        diagnostics = result.diagnostics

        lines = [
            "Возможна поломка парсера MAX",
            "",
            f"Статус: {result.health.value}",
            (
                "Проверок восстановления "
                f"выполнено: {attempts}"
            ),
            "",
            "Причины:",
        ]

        lines.extend(
            f"• {reason}"
            for reason in result.reasons
        )

        lines.extend(
            [
                "",
                (
                    "Строк чатов: "
                    f"{diagnostics.get('chat_row_count', 0)}"
                ),
                (
                    "Распознано имён: "
                    f"{diagnostics.get('named_chat_count', 0)}"
                ),
                (
                    "Непрочитанных чатов "
                    "по заголовку: "
                    f"{diagnostics.get('title_total', 0)}"
                ),
                (
                    "Непрочитанных чатов "
                    "по DOM: "
                    f"{diagnostics.get('matched_chat_count', 0)}"
                ),
                "",
                (
                    "Сервис не принял этот "
                    "результат за достоверный ноль."
                ),
                (
                    "HTML, JSON и скриншот "
                    "сохранены в runtime/screenshots."
                ),
            ]
        )

        return "\n".join(lines)

    def parser_recovered(
        self,
        snapshot,
    ) -> str:
        diagnostics = snapshot.diagnostics

        return (
            "Парсер MAX восстановился\n\n"
            "Структура страницы снова "
            "распознаётся корректно.\n"
            "Строк чатов: "
            f"{diagnostics.get('chat_row_count', 0)}\n"
            f"Непрочитанных: {snapshot.total_unread}\n"
            "Проверено: "
            f"{self._format_time(snapshot.captured_at)}"
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
