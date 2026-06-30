import asyncio
from datetime import datetime, timezone

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.models import (
    AuthStatus,
    MaxScanResult,
    ScanHealth,
    SnapshotRecord,
    UnreadSnapshot,
)
from app.integrations.max_web.client import (
    MaxWebClient,
)
from app.integrations.telegram.client import (
    TelegramClient,
)
from app.integrations.telegram.formatter import (
    TelegramFormatter,
)
from app.services.heartbeat import (
    HeartbeatService,
)
from app.storage.repository import (
    SnapshotRepository,
)


class MonitorService:
    def __init__(
        self,
        settings: Settings,
        max_client: MaxWebClient,
        telegram: TelegramClient,
        formatter: TelegramFormatter,
        repository: SnapshotRepository,
        heartbeat: HeartbeatService,
    ) -> None:
        self._settings = settings
        self._max = max_client
        self._telegram = telegram
        self._formatter = formatter
        self._repository = repository
        self._heartbeat = heartbeat

        self._logger = get_logger(__name__)

        self._closed = False
        self._consecutive_parser_failures = 0

    async def run(
        self,
        stop_event: asyncio.Event,
    ) -> None:
        self._settings.validate_main_runtime()

        await self._max.start()

        if (
            self._settings
            .send_startup_notification
        ):
            await self._safe_system_notification(
                self._formatter.startup(
                    self._settings
                    .max_check_interval_seconds
                ),
                state_key=(
                    "startup_notification_at"
                ),
                interval_seconds=300,
            )

        if (
            self._settings
            .max_initial_delay_seconds
        ):
            await self._wait_or_stop(
                stop_event,
                self._settings
                .max_initial_delay_seconds,
            )

        while not stop_event.is_set():
            delay = await self._run_cycle()

            await self._wait_or_stop(
                stop_event,
                delay,
            )

    async def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        await self._max.close()

    async def _run_cycle(self) -> int:
        check_time = datetime.now(
            timezone.utc
        )

        await self._heartbeat.update(
            status="checking",
            last_check_at=check_time.isoformat(),
            last_error=None,
        )

        try:
            await self._retry_pending_notifications()

            probe = await self._max.auth_status()

            if (
                probe.status
                == AuthStatus.UNAUTHORIZED
            ):
                self._logger.warning(
                    "MAX не авторизован: %s",
                    probe.reason,
                )

                await self._heartbeat.update(
                    status="waiting_for_auth",
                    max_authorized=False,
                    parser_status="unknown",
                )

                await self._safe_system_notification(
                    self._formatter.auth_required(
                        probe
                    ),
                    state_key="auth_alert_at",
                    interval_seconds=(
                        self._settings
                        .auth_alert_interval_seconds
                    ),
                )

                return (
                    self._settings
                    .max_retry_interval_seconds
                )

            if (
                probe.status
                == AuthStatus.UNKNOWN
            ):
                self._logger.warning(
                    "Неизвестное состояние "
                    "страницы MAX: %s",
                    probe.reason,
                )

                await self._max.save_diagnostics(
                    "unknown_auth_state"
                )

                await self._heartbeat.update(
                    status="unknown_page",
                    max_authorized=None,
                    parser_status="unknown",
                )

                await self._safe_system_notification(
                    self._formatter.unknown_page(
                        probe
                    ),
                    state_key=(
                        "unknown_page_alert_at"
                    ),
                    interval_seconds=(
                        self._settings
                        .error_alert_interval_seconds
                    ),
                )

                return (
                    self._settings
                    .max_retry_interval_seconds
                )

            result, attempts = (
                await self._scan_with_recovery()
            )

            if not result.is_trusted:
                await self._handle_untrusted_scan(
                    result,
                    attempts,
                )

                return (
                    self._settings
                    .max_retry_interval_seconds
                )

            snapshot = result.snapshot

            if snapshot is None:
                raise RuntimeError(
                    "Доверенный результат "
                    "сканирования не содержит "
                    "snapshot"
                )

            await self._handle_parser_recovery(
                snapshot
            )

            await self._handle_snapshot(
                snapshot
            )

            await self._repository.cleanup(
                self._settings
                .snapshot_retention_days
            )

            self._consecutive_parser_failures = 0

            await self._repository.set_state(
                "parser_status",
                ScanHealth.OK.value,
            )

            await self._heartbeat.update(
                status="running",
                max_authorized=True,
                parser_status=ScanHealth.OK.value,
                consecutive_parser_failures=0,
                last_success_at=(
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
                unread_total=(
                    snapshot.total_unread
                ),
                chat_row_count=(
                    snapshot.diagnostics.get(
                        "chat_row_count"
                    )
                ),
                named_chat_count=(
                    snapshot.diagnostics.get(
                        "named_chat_count"
                    )
                ),
                last_error=None,
            )

            self._logger.info(
                "Проверка завершена: "
                "непрочитанных=%s, "
                "чатов=%s, "
                "строк=%s, "
                "источник=%s",
                snapshot.total_unread,
                len(snapshot.chats),
                snapshot.diagnostics.get(
                    "chat_row_count",
                    0,
                ),
                snapshot.source,
            )

            return (
                self._settings
                .max_check_interval_seconds
            )

        except Exception as exc:
            self._logger.exception(
                "Ошибка цикла проверки MAX"
            )

            try:
                await self._max.save_diagnostics(
                    "monitor_error"
                )
            except Exception:
                self._logger.exception(
                    "Не удалось сохранить "
                    "диагностику"
                )

            await self._heartbeat.update(
                status="error",
                last_error=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

            await self._safe_system_notification(
                self._formatter.error(exc),
                state_key="error_alert_at",
                interval_seconds=(
                    self._settings
                    .error_alert_interval_seconds
                ),
            )

            return (
                self._settings
                .max_retry_interval_seconds
            )

    async def _scan_with_recovery(
        self,
    ) -> tuple[MaxScanResult, int]:
        result = await self._max.scan_unread()

        if result.is_trusted:
            return result, 1

        self._log_untrusted_result(
            "первичная проверка",
            result,
        )

        await asyncio.sleep(
            self._settings
            .parser_retry_delay_seconds
        )

        result = await self._max.scan_unread()

        if result.is_trusted:
            return result, 2

        self._log_untrusted_result(
            "повторная проверка",
            result,
        )

        await self._max.reload_page()

        result = await self._max.scan_unread()

        if result.is_trusted:
            return result, 3

        self._log_untrusted_result(
            "после перезагрузки вкладки",
            result,
        )

        await self._max.restart_browser()

        result = await self._max.scan_unread()

        return result, 4

    async def _handle_untrusted_scan(
        self,
        result: MaxScanResult,
        attempts: int,
    ) -> None:
        self._consecutive_parser_failures += 1

        self._logger.error(
            "Parser Health Guard отклонил "
            "результат: status=%s, "
            "reasons=%s",
            result.health.value,
            result.reason_text,
        )

        try:
            await self._max.save_diagnostics(
                f"parser_{result.health.value}"
            )
        except Exception:
            self._logger.exception(
                "Не удалось сохранить "
                "диагностику парсера"
            )

        await self._repository.set_state(
            "parser_status",
            result.health.value,
        )

        await self._heartbeat.update(
            status="parser_problem",
            max_authorized=True,
            parser_status=(
                result.health.value
            ),
            consecutive_parser_failures=(
                self._consecutive_parser_failures
            ),
            chat_row_count=(
                result.diagnostics.get(
                    "chat_row_count"
                )
            ),
            named_chat_count=(
                result.diagnostics.get(
                    "named_chat_count"
                )
            ),
            last_error=result.reason_text,
        )

        await self._safe_system_notification(
            self._formatter.parser_problem(
                result,
                attempts,
            ),
            state_key="parser_alert_at",
            interval_seconds=(
                self._settings
                .parser_alert_interval_seconds
            ),
        )

    async def _handle_parser_recovery(
        self,
        snapshot: UnreadSnapshot,
    ) -> None:
        previous_status = (
            await self._repository.get_state(
                "parser_status"
            )
        )

        if previous_status not in {
            ScanHealth.DEGRADED.value,
            ScanHealth.BROKEN.value,
        }:
            return

        try:
            await self._telegram.send_message(
                self._formatter
                .parser_recovered(snapshot)
            )
        except Exception:
            self._logger.exception(
                "Не удалось отправить "
                "уведомление о восстановлении "
                "парсера"
            )

    def _log_untrusted_result(
        self,
        stage: str,
        result: MaxScanResult,
    ) -> None:
        self._logger.warning(
            "Недостоверный результат MAX "
            "(%s): status=%s, reasons=%s",
            stage,
            result.health.value,
            result.reason_text,
        )

    async def _handle_snapshot(
        self,
        snapshot: UnreadSnapshot,
    ) -> None:
        previous_record = (
            await self._repository.get_last()
        )

        previous = (
            previous_record.to_snapshot()
            if previous_record
            else None
        )

        if (
            previous_record
            and previous_record.fingerprint
            == snapshot.fingerprint
        ):
            return

        notify = self.should_notify(
            previous=previous,
            current=snapshot,
            send_initial=(
                self._settings
                .send_initial_unread
            ),
        )

        record = (
            await self._repository
            .create_snapshot(
                snapshot,
                notification_status=(
                    "pending"
                    if notify
                    else "ignored"
                ),
            )
        )

        if notify:
            await self._send_snapshot(
                record,
                snapshot,
            )

    async def _retry_pending_notifications(
        self,
    ) -> None:
        pending = (
            await self._repository.list_pending()
        )

        for record in pending:
            try:
                await self._send_snapshot(
                    record,
                    record.to_snapshot(),
                )
            except Exception:
                self._logger.exception(
                    "Повторная отправка "
                    "уведомления id=%s "
                    "не удалась",
                    record.id,
                )

    async def _send_snapshot(
        self,
        record: SnapshotRecord,
        snapshot: UnreadSnapshot,
    ) -> None:
        try:
            await self._telegram.send_message(
                self._formatter.unread(
                    snapshot
                )
            )
        except Exception as exc:
            await self._repository.mark_failed(
                record.id,
                str(exc),
            )

            raise
        else:
            await self._repository.mark_sent(
                record.id
            )

    async def _safe_system_notification(
        self,
        text: str,
        state_key: str,
        interval_seconds: int,
    ) -> None:
        try:
            allowed = (
                await self._repository
                .alert_allowed(
                    state_key,
                    interval_seconds,
                )
            )

            if not allowed:
                return

            await self._telegram.send_message(
                text
            )

            await self._repository.mark_alert_sent(
                state_key
            )

        except Exception:
            self._logger.exception(
                "Не удалось отправить "
                "системное уведомление"
            )

    @staticmethod
    def should_notify(
        previous: UnreadSnapshot | None,
        current: UnreadSnapshot,
        send_initial: bool,
    ) -> bool:
        if current.total_unread <= 0:
            return False

        if previous is None:
            return send_initial

        if (
            current.total_unread
            > previous.total_unread
        ):
            return True

        if (
            current.total_unread
            < previous.total_unread
        ):
            return False

        return (
            current.fingerprint
            != previous.fingerprint
        )

    @staticmethod
    async def _wait_or_stop(
        stop_event: asyncio.Event,
        seconds: int,
    ) -> None:
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=seconds,
            )
        except asyncio.TimeoutError:
            pass
