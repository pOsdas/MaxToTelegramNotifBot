from app.integrations.max_web.detector import SCAN_ARGUMENTS, UNREAD_SCAN_SCRIPT


def test_unread_scan_script_does_not_contain_broken_regex() -> None:
    assert ".split(/+/)" not in UNREAD_SCAN_SCRIPT
    assert '.split("\\n")' in UNREAD_SCAN_SCRIPT


def test_detector_supports_current_max_title() -> None:
    assert "непрочитан|unread" in UNREAD_SCAN_SCRIPT


def test_detector_uses_current_max_chat_rows() -> None:
    assert SCAN_ARGUMENTS["chatRowSelector"] == "aside div[data-index]"


def test_detector_filters_folder_counters() -> None:
    assert 'semanticText.includes("сообщен")' in UNREAD_SCAN_SCRIPT
    assert 'semanticText.includes("message")' in UNREAD_SCAN_SCRIPT
