from app.domain.models import UnreadChat, UnreadSnapshot


def test_fingerprint_does_not_depend_on_chat_order() -> None:
    first = UnreadSnapshot(
        total_unread=2,
        chats=[
            UnreadChat(key="b", name="Б", snippet="2"),
            UnreadChat(key="a", name="А", snippet="1"),
        ],
    )
    second = UnreadSnapshot(
        total_unread=2,
        chats=[
            UnreadChat(key="a", name="А", snippet="1"),
            UnreadChat(key="b", name="Б", snippet="2"),
        ],
    )

    assert first.fingerprint == second.fingerprint


def test_fingerprint_changes_when_snippet_changes() -> None:
    first = UnreadSnapshot(
        total_unread=1,
        chats=[UnreadChat(key="a", name="А", snippet="Старое")],
    )
    second = UnreadSnapshot(
        total_unread=1,
        chats=[UnreadChat(key="a", name="А", snippet="Новое")],
    )

    assert first.fingerprint != second.fingerprint
