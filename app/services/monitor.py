from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.models import AuthStatus, SnapshotRecord, UnreadSnapshot
from app.integrations.max_web.client import MaxWebClient
from app.integrations.telegram.client import TelegramClient
from app.integrations.telegram.formatter import TelegramFormatter
from app.services.heartbeat import HeartbeatService
from app.storage.repository import SnapshotRepository


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

    async def run(self, stop_event: asyncio.Event) -> None:
        self._settings.validate_main_runtime()
        await self._max.start()

        if self._settings.send_startup_notification:
            await self._safe_system_notification(
                self._formatter.startup(self._settings.max_check_interval_seconds),
                state_key="startup_notification_at",
                interval_seconds=300,
            )

        if self._settings.max_initial_delay_seconds:
            await self._wait_or_stop(
                stop_event,
                self._settings.max_initial_delay_seconds,
            )

        while not stop_event.is_set():
            delay = await self._run_cycle()
            await self._wait_or_stop(stop_event, delay)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._max.close()

    async def _run_cycle(self) -> int:
        check_time = datetime.now(timezone.utc)
        await self._heartbeat.update(
            status="checking",
            last_check_at=check_time.isoformat(),
            last_error=None,
        )

        try:
            await self._retry_pending_notifications()
            probe = await self._max.auth_status()

            if probe.status == AuthStatus.UNAUTHORIZED:
                self._logger.warning("MAX не авторизован: %s", probe.reason)
                await self._heartbeat.update(
                    status="waiting_for_auth",
                    max_authorized=False,
                )
                await self._safe_system_notification(
                    self._formatter.auth_required(probe),
                    state_key="auth_alert_at",
                    interval_seconds=self._settings.auth_alert_interval_seconds,
                )
                return self._settings.max_retry_interval_seconds

            if probe.status == AuthStatus.UNKNOWN:
                self._logger.warning("Неизвестное состояние страницы MAX: %s", probe.reason)
                await self._max.save_diagnostics("unknown_auth_state")
                await self._heartbeat.update(
                    status="unknown_page",
                    max_authorized=None,
                )
                await self._safe_system_notification(
                    self._formatter.unknown_page(probe),
                    state_key="unknown_page_alert_at",
                    interval_seconds=self._settings.error_alert_interval_seconds,
                )
                return self._settings.max_retry_interval_seconds

            snapshot = await self._max.scan_unread()
            await self._handle_snapshot(snapshot)
            await self._repository.cleanup(self._settings.snapshot_retention_days)
            await self._heartbeat.update(
                status="running",
                max_authorized=True,
                last_success_at=datetime.now(timezone.utc).isoformat(),
                unread_total=snapshot.total_unread,
            )
            self._logger.info(
                "Проверка завершена: непрочитанных=%s, чатов=%s, источник=%s",
                snapshot.total_unread,
                len(snapshot.chats),
                snapshot.source,
            )
            return self._settings.max_check_interval_seconds
        except Exception as exc:
            self._logger.exception("Ошибка цикла проверки MAX")
            try:
                await self._max.save_diagnostics("monitor_error")
            except Exception:
                self._logger.exception("Не удалось сохранить диагностику")
            await self._heartbeat.update(
                status="error",
                last_error=f"{type(exc).__name__}: {exc}",
            )
            await self._safe_system_notification(
                self._formatter.error(exc),
                state_key="error_alert_at",
                interval_seconds=self._settings.error_alert_interval_seconds,
            )
            return self._settings.max_retry_interval_seconds

    async def _handle_snapshot(self, snapshot: UnreadSnapshot) -> None:
        previous_record = await self._repository.get_last()
        previous = previous_record.to_snapshot() if previous_record else None

        if previous_record and previous_record.fingerprint == snapshot.fingerprint:
            return

        notify = self.should_notify(
            previous=previous,
            current=snapshot,
            send_initial=self._settings.send_initial_unread,
        )
        record = await self._repository.create_snapshot(
            snapshot,
            notification_status="pending" if notify else "ignored",
        )

        if notify:
            await self._send_snapshot(record, snapshot)

    async def _retry_pending_notifications(self) -> None:
        pending = await self._repository.list_pending()
        for record in pending:
            try:
                await self._send_snapshot(record, record.to_snapshot())
            except Exception:
                self._logger.exception(
                    "Повторная отправка уведомления id=%s не удалась", record.id
                )

    async def _send_snapshot(
        self,
        record: SnapshotRecord,
        snapshot: UnreadSnapshot,
    ) -> None:
        try:
            await self._telegram.send_message(self._formatter.unread(snapshot))
        except Exception as exc:
            await self._repository.mark_failed(record.id, str(exc))
            raise
        else:
            await self._repository.mark_sent(record.id)

    async def _safe_system_notification(
        self,
        text: str,
        state_key: str,
        interval_seconds: int,
    ) -> None:
        try:
            if not await self._repository.alert_allowed(state_key, interval_seconds):
                return
            await self._telegram.send_message(text)
            await self._repository.mark_alert_sent(state_key)
        except Exception:
            self._logger.exception("Не удалось отправить системное уведомление")

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
        if current.total_unread > previous.total_unread:
            return True
        if current.total_unread < previous.total_unread:
            return False
        return current.fingerprint != previous.fingerprint

    @staticmethod
    async def _wait_or_stop(stop_event: asyncio.Event, seconds: int) -> None:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass
