import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.models import (
    AuthProbe,
    MaxScanResult,
)
from app.integrations.max_web.auth import (
    MaxAuthDetector,
)
from app.integrations.max_web.browser import (
    PersistentBrowser,
)
from app.integrations.max_web.detector import (
    SCAN_ARGUMENTS,
    UNREAD_SCAN_SCRIPT,
)
from app.integrations.max_web.parser import (
    UnreadDomParser,
)


class MaxWebClient:
    def __init__(
        self,
        settings: Settings,
        browser: PersistentBrowser,
    ) -> None:
        self._settings = settings
        self._browser = browser
        self._auth = MaxAuthDetector()

        self._parser = UnreadDomParser(
            settings.parser_min_named_ratio
        )

        self._logger = get_logger(__name__)

    async def start(self) -> None:
        page = await self._browser.start()

        await page.bring_to_front()

        await asyncio.sleep(
            self._settings.max_dom_settle_seconds
        )

    async def auth_status(self) -> AuthProbe:
        page = await self._browser.ensure_running()

        return await self._auth.probe(page)

    async def scan_unread(
        self,
    ) -> MaxScanResult:
        page = await self._browser.ensure_running()

        await page.bring_to_front()

        raw = await page.evaluate(
            UNREAD_SCAN_SCRIPT,
            SCAN_ARGUMENTS,
        )

        result = self._parser.parse(raw)

        if result.snapshot is not None:
            result.snapshot.captured_at = (
                datetime.now(timezone.utc)
            )

        return result

    async def reload_page(self) -> None:
        page = await self._browser.ensure_running()

        self._logger.warning(
            "Перезагружаю вкладку MAX "
            "для восстановления парсера"
        )

        await page.reload(
            wait_until="domcontentloaded"
        )

        await asyncio.sleep(
            self._settings.max_dom_settle_seconds
        )

    async def restart_browser(self) -> None:
        page = await self._browser.restart()

        await page.bring_to_front()

        await asyncio.sleep(
            self._settings.max_dom_settle_seconds
        )

    async def save_diagnostics(
        self,
        reason: str,
    ) -> tuple[Path, Path, Path]:
        page = await self._browser.ensure_running()

        timestamp = datetime.now(
            timezone.utc
        ).strftime("%Y%m%dT%H%M%SZ")

        safe_reason = "".join(
            c
            if c.isalnum() or c in "-_"
            else "_"
            for c in reason
        )[:60]

        base = (
            self._settings.screenshots_path
            / f"{timestamp}_{safe_reason}"
        )

        screenshot_path = base.with_suffix(
            ".png"
        )

        html_path = base.with_suffix(
            ".html"
        )

        metadata_path = base.with_suffix(
            ".json"
        )

        await page.screenshot(
            path=str(screenshot_path),
            full_page=True,
        )

        html_path.write_text(
            await page.content(),
            encoding="utf-8",
        )

        metadata_path.write_text(
            json.dumps(
                {
                    "url": page.url,
                    "title": await page.title(),
                    "reason": reason,
                    "captured_at": (
                        datetime.now(
                            timezone.utc
                        ).isoformat()
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self._logger.info(
            "Диагностика MAX сохранена: %s",
            base,
        )

        return (
            screenshot_path,
            html_path,
            metadata_path,
        )

    async def close(self) -> None:
        await self._browser.close()
