from app.domain.models import UnreadChat, UnreadSnapshot
from app.services.monitor import MonitorService


def snapshot(total: int, snippet: str = "") -> UnreadSnapshot:
    chats = []
    if total:
        chats = [UnreadChat(key="chat", name="Чат", snippet=snippet, unread_count=total)]
    return UnreadSnapshot(total_unread=total, chats=chats)


def test_no_notification_for_zero() -> None:
    assert not MonitorService.should_notify(None, snapshot(0), send_initial=True)


def test_initial_notification_can_be_enabled() -> None:
    assert MonitorService.should_notify(None, snapshot(1), send_initial=True)
    assert not MonitorService.should_notify(None, snapshot(1), send_initial=False)


def test_increase_notifies_and_decrease_does_not() -> None:
    assert MonitorService.should_notify(snapshot(1), snapshot(2), send_initial=True)
    assert not MonitorService.should_notify(snapshot(2), snapshot(1), send_initial=True)


def test_same_count_with_new_content_notifies() -> None:
    assert MonitorService.should_notify(
        snapshot(1, "Старое"),
        snapshot(1, "Новое"),
        send_initial=True,
    )
