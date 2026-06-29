from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from app.core.config import Settings
from app.core.logging import get_logger


class PersistentBrowser:
    """Один постоянный Chromium-контекст на всё время работы контейнера."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()
        self._logger = get_logger(__name__)

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Chromium ещё не запущен")
        return self._page

    async def start(self) -> Page:
        async with self._lock:
            if await self._is_usable():
                return self.page

            await self._close_unlocked()
            self._remove_stale_profile_locks()

            self._logger.info("Запускаю постоянный Chromium-контекст")
            self._playwright = await async_playwright().start()
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._settings.browser_profile_path),
                headless=self._settings.headless,
                viewport={
                    "width": self._settings.browser_width,
                    "height": self._settings.browser_height,
                },
                locale="ru-RU",
                args=[
                    "--start-maximized",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-features=Translate,MediaRouter",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            self._context.set_default_timeout(15_000)
            self._context.set_default_navigation_timeout(
                self._settings.max_page_load_timeout_ms
            )

            pages = self._context.pages
            self._page = pages[0] if pages else await self._context.new_page()
            self._page.on("crash", lambda _: self._logger.error("Вкладка Chromium аварийно завершилась"))

            if "web.max.ru" not in self._page.url:
                await self._open_max(self._page)

            return self._page

    async def ensure_running(self) -> Page:
        if await self._is_usable():
            return self.page
        self._logger.warning("Chromium недоступен, выполняю аварийный перезапуск")
        return await self.start()

    async def close(self) -> None:
        async with self._lock:
            await self._close_unlocked()

    async def _close_unlocked(self) -> None:
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                self._logger.exception("Ошибка при закрытии Chromium-контекста")
        self._context = None
        self._page = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                self._logger.exception("Ошибка при остановке Playwright")
        self._playwright = None

    async def _is_usable(self) -> bool:
        if self._context is None or self._page is None:
            return False
        try:
            if self._page.is_closed():
                return False
            await self._page.evaluate("1")
            return True
        except Exception:
            return False

    async def _open_max(self, page: Page) -> None:
        try:
            await page.goto(self._settings.max_web_url, wait_until="domcontentloaded")
        except Exception:
            self._logger.exception("Не удалось полностью загрузить MAX, вкладка оставлена открытой")

    def _remove_stale_profile_locks(self) -> None:
        profile = Path(self._settings.browser_profile_path)
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            path = profile / name
            try:
                if path.is_symlink() or path.exists():
                    path.unlink()
            except OSError:
                self._logger.warning("Не удалось удалить старый lock-файл %s", path)
