from __future__ import annotations

AUTH_PHONE_SELECTORS = (
    'input[type="tel"]',
    'input[autocomplete="tel"]',
    'input[name*="phone" i]',
)

CHAT_MARKER_SELECTORS = (
    '[role="listitem"]',
    '[data-testid*="chat" i]',
    '[data-qa*="chat" i]',
    '[class*="chat" i]',
    'nav',
)

UNREAD_CANDIDATE_SELECTORS = (
    '[aria-label*="непрочитан" i]',
    '[aria-label*="unread" i]',
    '[title*="непрочитан" i]',
    '[title*="unread" i]',
    '[data-testid*="unread" i]',
    '[data-qa*="unread" i]',
    '[class*="unread" i]',
    '[class*="badge" i]',
    '[class*="counter" i]',
)

CHAT_CONTAINER_SELECTOR = (
    '[role="listitem"], '
    '[data-testid*="chat" i], '
    '[data-qa*="chat" i], '
    'li, a[href], [class*="chat" i]'
)
