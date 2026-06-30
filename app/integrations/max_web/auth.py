import re

from playwright.async_api import Page

from app.domain.models import AuthProbe, AuthStatus
from app.integrations.max_web.selectors import AUTH_PHONE_SELECTORS, CHAT_MARKER_SELECTORS


class MaxAuthDetector:
    async def probe(self, page: Page) -> AuthProbe:
        url = page.url
        lowered_url = url.lower()

        if any(part in lowered_url for part in ("/login", "/auth", "/signin")):
            return AuthProbe(
                status=AuthStatus.UNAUTHORIZED,
                reason="URL указывает на страницу входа",
                url=url,
            )

        for selector in AUTH_PHONE_SELECTORS:
            try:
                if await page.locator(selector).count() > 0:
                    return AuthProbe(
                        status=AuthStatus.UNAUTHORIZED,
                        reason=f"Найдено поле авторизации: {selector}",
                        url=url,
                    )
            except Exception:
                continue

        try:
            body_text = (await page.locator("body").inner_text(timeout=5_000))[:12_000]
        except Exception:
            body_text = ""

        login_words = re.search(
            r"(?:войти|введите номер|номер телефона|получить код|продолжить)",
            body_text,
            flags=re.IGNORECASE,
        )
        chat_words = re.search(
            r"(?:чаты|сообщения|контакты|channels|chats)",
            body_text,
            flags=re.IGNORECASE,
        )

        marker_count = 0
        for selector in CHAT_MARKER_SELECTORS:
            try:
                marker_count += min(await page.locator(selector).count(), 20)
            except Exception:
                continue

        if login_words and not chat_words:
            return AuthProbe(
                status=AuthStatus.UNAUTHORIZED,
                reason="На странице обнаружена форма входа",
                url=url,
            )

        if "web.max.ru" in lowered_url and (chat_words or marker_count > 2):
            return AuthProbe(
                status=AuthStatus.AUTHORIZED,
                reason="Открыт интерфейс MAX с элементами чатов",
                url=url,
            )

        if "web.max.ru" in lowered_url and body_text and not login_words:
            return AuthProbe(
                status=AuthStatus.AUTHORIZED,
                reason="Открыта веб-версия MAX без признаков формы входа",
                url=url,
            )

        return AuthProbe(
            status=AuthStatus.UNKNOWN,
            reason="Не удалось уверенно определить состояние авторизации",
            url=url,
        )
