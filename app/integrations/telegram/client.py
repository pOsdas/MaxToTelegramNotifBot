import asyncio

import httpx

from app.core.config import Settings
from app.core.logging import get_logger


class TelegramError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token = settings.telegram_bot_token.get_secret_value().strip()
        self._chat_id = settings.telegram_chat_id.strip()
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(20.0))
        self._logger = get_logger(__name__)

    async def validate(self) -> dict:
        self._ensure_configured(require_chat_id=False)
        response = await self._client.get(self._api_url("getMe"))
        data = self._decode_response(response)
        return data["result"]

    async def get_updates(self) -> list[dict]:
        self._ensure_configured(require_chat_id=False)
        response = await self._client.get(
            self._api_url("getUpdates"),
            params={"timeout": 0, "limit": 100},
        )
        data = self._decode_response(response)
        return list(data.get("result") or [])

    async def send_message(self, text: str) -> None:
        self._ensure_configured(require_chat_id=True)
        for chunk in self._split_message(text):
            await self._send_chunk(chunk)

    async def close(self) -> None:
        await self._client.aclose()

    async def _send_chunk(self, text: str) -> None:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = await self._client.post(
                    self._api_url("sendMessage"),
                    json={
                        "chat_id": self._chat_id,
                        "text": text,
                        "disable_web_page_preview": True,
                    },
                )
                self._decode_response(response)
                return
            except (httpx.HTTPError, TelegramError) as exc:
                last_error = exc
                self._logger.warning(
                    "Ошибка Telegram, попытка %s/3: %s", attempt, exc
                )
                if attempt < 3:
                    await asyncio.sleep(2 ** (attempt - 1))
        raise TelegramError(f"Не удалось отправить сообщение: {last_error}")

    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._token}/{method}"

    @staticmethod
    def _decode_response(response: httpx.Response) -> dict:
        try:
            data = response.json()
        except ValueError as exc:
            raise TelegramError(
                f"Telegram вернул не-JSON ответ, HTTP {response.status_code}"
            ) from exc

        if response.is_error or not data.get("ok"):
            description = data.get("description") or response.text[:500]
            raise TelegramError(
                f"Telegram API: HTTP {response.status_code}: {description}"
            )
        return data

    def _ensure_configured(self, require_chat_id: bool) -> None:
        if not self._token:
            raise TelegramError("Не заполнен TELEGRAM_BOT_TOKEN")
        if require_chat_id and not self._chat_id:
            raise TelegramError("Не заполнен TELEGRAM_CHAT_ID")

    @staticmethod
    def _split_message(text: str, limit: int = 3900) -> list[str]:
        if len(text) <= limit:
            return [text]

        chunks: list[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break
            split_at = remaining.rfind("\n", 0, limit)
            if split_at < limit // 2:
                split_at = limit
            chunks.append(remaining[:split_at].rstrip())
            remaining = remaining[split_at:].lstrip()
        return chunks
