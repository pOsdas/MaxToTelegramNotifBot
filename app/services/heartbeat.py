import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import Settings


class HeartbeatService:
    def __init__(
        self,
        settings: Settings,
    ) -> None:
        self._path = Path(
            settings.heartbeat_path
        )

        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._write_lock = asyncio.Lock()

        self._state: dict[str, Any] = {
            "status": "starting",
            "max_authorized": None,
            "parser_status": "starting",
            "consecutive_parser_failures": 0,
            "last_check_at": None,
            "last_success_at": None,
            "last_error": None,
            "unread_total": None,
            "chat_row_count": None,
            "named_chat_count": None,
        }

    async def start(self) -> None:
        if self._task is not None:
            return

        self._stop_event.clear()

        self._task = asyncio.create_task(
            self._run(),
            name="heartbeat",
        )

    async def stop(self) -> None:
        self._stop_event.set()

        if self._task is None:
            return

        self._task.cancel()

        try:
            await self._task
        except asyncio.CancelledError:
            pass

        self._task = None

    async def update(
        self,
        **values: Any,
    ) -> None:
        self._state.update(values)

        await self._write()

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            await self._write()

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=30,
                )
            except asyncio.TimeoutError:
                continue

    async def _write(self) -> None:
        async with self._write_lock:
            self._path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            payload = {
                **self._state,
                "heartbeat_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }

            temporary = (
                self._path.with_suffix(".tmp")
            )

            temporary.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            temporary.replace(self._path)
