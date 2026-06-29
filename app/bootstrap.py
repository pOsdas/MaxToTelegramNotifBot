from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.integrations.max_web.browser import PersistentBrowser
from app.integrations.max_web.client import MaxWebClient
from app.integrations.telegram.client import TelegramClient
from app.integrations.telegram.formatter import TelegramFormatter
from app.services.heartbeat import HeartbeatService
from app.services.monitor import MonitorService
from app.storage.database import Database
from app.storage.repository import SnapshotRepository


@dataclass(slots=True)
class Application:
    monitor: MonitorService
    heartbeat: HeartbeatService
    browser: PersistentBrowser
    telegram: TelegramClient
    database: Database

    async def run(self, stop_event) -> None:
        await self.heartbeat.start()
        await self.monitor.run(stop_event)

    async def close(self) -> None:
        await self.monitor.close()
        await self.heartbeat.stop()
        await self.telegram.close()
        await self.database.close()


async def build_application(settings: Settings) -> Application:
    database = Database(settings.database_path)
    await database.connect()
    repository = SnapshotRepository(database)
    await repository.initialize()

    browser = PersistentBrowser(settings)
    max_client = MaxWebClient(settings, browser)
    telegram = TelegramClient(settings)
    formatter = TelegramFormatter(settings)
    heartbeat = HeartbeatService(settings)

    monitor = MonitorService(
        settings=settings,
        max_client=max_client,
        telegram=telegram,
        formatter=formatter,
        repository=repository,
        heartbeat=heartbeat,
    )

    return Application(
        monitor=monitor,
        heartbeat=heartbeat,
        browser=browser,
        telegram=telegram,
        database=database,
    )
