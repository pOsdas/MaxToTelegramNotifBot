from __future__ import annotations

AUTH_PHONE_SELECTORS = (
    'input[type="tel"]',
    'input[autocomplete="tel"]',
    'input[name*="phone" i]',
)

# Признаки авторизованного интерфейса MAX. Селекторы не завязаны
# на сгенерированные Svelte-классы вида svelte-xxxxxx.
CHAT_MARKER_SELECTORS = (
    'aside div[data-index] button',
    'aside h3',
    'nav[aria-label]',
)

# В текущем MAX Web каждая строка списка чатов находится в div[data-index].
# Область ограничена aside, чтобы не спутать чат с сообщениями в открытом диалоге.
CHAT_ROW_SELECTOR = 'aside div[data-index]'

# Счётчик непрочитанных сообщений имеет aria-label вида:
#   ", 1 новое сообщение, "
# Для разных языков и форм множественного числа берём кандидатов шире,
# а окончательную проверку выполняем в detector.py.
UNREAD_CANDIDATE_SELECTORS = (
    'aside [aria-label*="сообщен"]',
    'aside [aria-label*="unread" i]',
    'aside [aria-label*="message" i]',
)

CHAT_NAME_SELECTORS = (
    'h3 span.name span.text',
    'h3 span.name',
    'h3',
)

CHAT_SNIPPET_SELECTORS = (
    'button.cell > span.text',
    'button > span.text',
)

CHAT_TIME_SELECTORS = (
    'span.time[aria-label]',
    'span.time',
)
