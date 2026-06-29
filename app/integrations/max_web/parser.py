from __future__ import annotations

from typing import Any

from app.domain.models import UnreadChat, UnreadSnapshot


class UnreadDomParser:
    def parse(self, raw: dict[str, Any]) -> UnreadSnapshot:
        raw_chats = raw.get("chats") or []
        chats: list[UnreadChat] = []
        seen: set[str] = set()

        for index, item in enumerate(raw_chats):
            key = str(item.get("key") or f"chat-{index}").strip()
            if key in seen:
                continue
            seen.add(key)

            chats.append(
                UnreadChat(
                    key=key,
                    name=str(item.get("name") or "Неизвестный чат").strip(),
                    snippet=str(item.get("snippet") or "").strip(),
                    unread_count=self._to_positive_int(item.get("unreadCount"), default=1),
                    raw_text=str(item.get("rawText") or "").strip(),
                )
            )

        dom_total = self._to_non_negative_int(raw.get("domTotal"), default=0)
        title_total = self._to_non_negative_int(raw.get("titleTotal"), default=0)
        sum_chats = sum(chat.unread_count for chat in chats)
        total = max(dom_total, title_total, sum_chats)

        source_parts = []
        if title_total:
            source_parts.append("title")
        if dom_total or chats:
            source_parts.append("dom")

        return UnreadSnapshot(
            total_unread=total,
            chats=chats,
            source="+".join(source_parts) or "none",
            page_title=str(raw.get("title") or ""),
            diagnostics={
                "candidate_count": raw.get("candidateCount", 0),
                "title_total": title_total,
                "dom_total": dom_total,
            },
        )

    @staticmethod
    def _to_non_negative_int(value: Any, default: int) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _to_positive_int(cls, value: Any, default: int) -> int:
        return max(1, cls._to_non_negative_int(value, default))
