from app.integrations.max_web.parser import UnreadDomParser


def test_parser_uses_largest_total() -> None:
    snapshot = UnreadDomParser().parse(
        {
            "title": "(5) MAX",
            "titleTotal": 5,
            "domTotal": 2,
            "chats": [
                {
                    "key": "chat-1",
                    "name": "Иван",
                    "snippet": "Привет",
                    "unreadCount": 2,
                }
            ],
        }
    )

    assert snapshot.total_unread == 5
    assert snapshot.chats[0].name == "Иван"


def test_parser_removes_duplicate_chat_keys() -> None:
    snapshot = UnreadDomParser().parse(
        {
            "chats": [
                {"key": "same", "name": "Первый", "unreadCount": 1},
                {"key": "same", "name": "Второй", "unreadCount": 2},
            ]
        }
    )

    assert len(snapshot.chats) == 1
