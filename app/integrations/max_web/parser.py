from typing import Any

from app.domain.models import (
    MaxScanResult,
    ScanHealth,
    UnreadChat,
    UnreadSnapshot,
)


class UnreadDomParser:
    def __init__(
        self,
        min_named_ratio: float = 0.60,
    ) -> None:
        self._min_named_ratio = min_named_ratio

    def parse(
        self,
        raw: dict[str, Any],
    ) -> MaxScanResult:
        raw_chats = raw.get("chats") or []

        chats: list[UnreadChat] = []
        seen: set[str] = set()

        for index, item in enumerate(raw_chats):
            key = str(
                item.get("key") or f"chat-{index}"
            ).strip()

            if key in seen:
                continue

            seen.add(key)

            chats.append(
                UnreadChat(
                    key=key,
                    name=str(
                        item.get("name")
                        or "Неизвестный чат"
                    ).strip(),
                    snippet=str(
                        item.get("snippet")
                        or ""
                    ).strip(),
                    unread_count=self._to_positive_int(
                        item.get("unreadCount"),
                        default=1,
                    ),
                    raw_text=str(
                        item.get("rawText")
                        or ""
                    ).strip(),
                )
            )

        dom_total = self._to_non_negative_int(
            raw.get("domTotal"),
            default=0,
        )

        title_total = self._to_non_negative_int(
            raw.get("titleTotal"),
            default=0,
        )

        matched_chat_count = (
            self._to_non_negative_int(
                raw.get("matchedChatCount"),
                default=len(chats),
            )
        )

        unmatched_unread_total = (
            self._to_non_negative_int(
                raw.get("unmatchedUnreadTotal"),
                default=0,
            )
        )

        chat_row_count = self._to_non_negative_int(
            raw.get("chatRowCount"),
            default=0,
        )

        named_chat_count = (
            self._to_non_negative_int(
                raw.get("namedChatCount"),
                default=0,
            )
        )

        snippet_chat_count = (
            self._to_non_negative_int(
                raw.get("snippetChatCount"),
                default=0,
            )
        )

        app_present = bool(
            raw.get("appPresent")
        )

        aside_present = bool(
            raw.get("asidePresent")
        )

        title_pattern = bool(
            raw.get("titleUnreadPatternMatched")
        )

        ready_state = str(
            raw.get("documentReadyState")
            or ""
        )

        diagnostics = {
            "candidate_count":
                self._to_non_negative_int(
                    raw.get("candidateCount"),
                    default=0,
                ),
            "matched_chat_count":
                matched_chat_count,
            "unmatched_unread_total":
                unmatched_unread_total,
            "title_total":
                title_total,
            "dom_total":
                dom_total,
            "title_unread_pattern_matched":
                title_pattern,
            "chat_row_count":
                chat_row_count,
            "named_chat_count":
                named_chat_count,
            "snippet_chat_count":
                snippet_chat_count,
            "app_present":
                app_present,
            "aside_present":
                aside_present,
            "main_present":
                bool(raw.get("mainPresent")),
            "document_ready_state":
                ready_state,
            "url":
                str(raw.get("url") or ""),
        }

        broken_reasons: list[str] = []
        degraded_reasons: list[str] = []

        if not app_present:
            broken_reasons.append(
                "Не найден корневой элемент #app"
            )

        if not aside_present:
            broken_reasons.append(
                "Не найдена боковая панель "
                "со списком чатов"
            )

        if ready_state not in {
            "interactive",
            "complete",
        }:
            degraded_reasons.append(
                "Страница ещё не готова: "
                "document.readyState="
                f"{ready_state or 'unknown'}"
            )

        if chat_row_count == 0:
            broken_reasons.append(
                "Не найдена ни одна строка чата"
            )

        elif named_chat_count == 0:
            broken_reasons.append(
                "Строки чатов найдены, "
                "но имена не распознаются"
            )

        else:
            named_ratio = (
                named_chat_count
                / chat_row_count
            )

            diagnostics["named_ratio"] = round(
                named_ratio,
                4,
            )

            if (
                named_ratio
                < self._min_named_ratio
            ):
                degraded_reasons.append(
                    "Имена распознаны только у "
                    f"{named_chat_count} из "
                    f"{chat_row_count} строк чатов"
                )

        if title_total > matched_chat_count:
            degraded_reasons.append(
                "Заголовок сообщает о "
                f"{title_total} непрочитанных "
                "чатах, а DOM распознал только "
                f"{matched_chat_count}"
            )

        if (
            matched_chat_count > 0
            and not title_pattern
        ):
            degraded_reasons.append(
                "DOM нашёл непрочитанные "
                "сообщения, но заголовок "
                "вкладки их не подтверждает"
            )

        if unmatched_unread_total > 0:
            degraded_reasons.append(
                "Найдено непривязанных "
                "к строкам чатов сообщений: "
                f"{unmatched_unread_total}"
            )

        if broken_reasons:
            return MaxScanResult(
                health=ScanHealth.BROKEN,
                snapshot=None,
                reasons=(
                    broken_reasons
                    + degraded_reasons
                ),
                diagnostics=diagnostics,
            )

        sum_chats = sum(
            chat.unread_count
            for chat in chats
        )

        total = max(
            dom_total,
            title_total,
            sum_chats,
        )

        source_parts: list[str] = []

        if title_pattern:
            source_parts.append("title")

        if dom_total or chats:
            source_parts.append("dom")

        if not source_parts:
            source_parts.append(
                "verified-zero"
            )

        snapshot = UnreadSnapshot(
            total_unread=total,
            chats=chats,
            source="+".join(source_parts),
            page_title=str(
                raw.get("title") or ""
            ),
            diagnostics=diagnostics,
        )

        if degraded_reasons:
            return MaxScanResult(
                health=ScanHealth.DEGRADED,
                snapshot=snapshot,
                reasons=degraded_reasons,
                diagnostics=diagnostics,
            )

        return MaxScanResult(
            health=ScanHealth.OK,
            snapshot=snapshot,
            reasons=[],
            diagnostics=diagnostics,
        )

    @staticmethod
    def _to_non_negative_int(
        value: Any,
        default: int,
    ) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _to_positive_int(
        cls,
        value: Any,
        default: int,
    ) -> int:
        return max(
            1,
            cls._to_non_negative_int(
                value,
                default,
            ),
        )
