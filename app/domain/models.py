from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AuthStatus(StrEnum):
    AUTHORIZED = "authorized"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


class AuthProbe(BaseModel):
    status: AuthStatus
    reason: str
    url: str = ""


class UnreadChat(BaseModel):
    key: str
    name: str = "Неизвестный чат"
    snippet: str = ""
    unread_count: int = 1
    raw_text: str = ""

    @field_validator("unread_count")
    @classmethod
    def normalize_count(cls, value: int) -> int:
        return max(1, value)


class UnreadSnapshot(BaseModel):
    total_unread: int = 0
    chats: list[UnreadChat] = Field(default_factory=list)
    source: str = "dom"
    page_title: str = ""
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("total_unread")
    @classmethod
    def normalize_total(cls, value: int) -> int:
        return max(0, value)

    def canonical_payload(self) -> dict[str, Any]:
        chats = sorted(
            (
                {
                    "key": chat.key,
                    "name": chat.name.strip(),
                    "snippet": chat.snippet.strip(),
                    "unread_count": chat.unread_count,
                }
                for chat in self.chats
            ),
            key=lambda item: (item["key"], item["name"], item["snippet"]),
        )
        return {
            "total_unread": self.total_unread,
            "chats": chats,
            "source": self.source,
        }

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class SnapshotRecord(BaseModel):
    id: int
    fingerprint: str
    total_unread: int
    payload_json: str
    observed_at: datetime
    notification_status: str
    notification_attempts: int
    notified_at: datetime | None = None
    last_error: str | None = None

    def to_snapshot(self) -> UnreadSnapshot:
        return UnreadSnapshot.model_validate_json(self.payload_json)
