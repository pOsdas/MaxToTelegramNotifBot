from __future__ import annotations

from app.integrations.max_web.selectors import (
    CHAT_CONTAINER_SELECTOR,
    UNREAD_CANDIDATE_SELECTORS,
)


UNREAD_SCAN_SCRIPT = r"""
(args) => {
  const unreadSelectors = args.unreadSelectors;
  const chatContainerSelector = args.chatContainerSelector;

  const isVisible = (element) => {
    if (!(element instanceof Element)) return false;
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      Number(style.opacity || '1') > 0 &&
      rect.width > 0 && rect.height > 0;
  };

  const parseCount = (value) => {
    if (!value) return 0;
    const compact = String(value).replace(/\s+/g, ' ').trim();
    const match = compact.match(/(?:^|\D)(\d{1,4})(?:\D|$)/);
    if (!match) return 0;
    const number = Number(match[1]);
    return Number.isFinite(number) && number >= 0 ? number : 0;
  };

  const normalizedLines = (text) => String(text || '')
    .split(/+/)
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter(Boolean);

  const title = document.title || '';
  const titleMatch = title.match(/^\s*(?:\((\d{1,4})\)|\[(\d{1,4})\])/);
  const titleTotal = titleMatch ? Number(titleMatch[1] || titleMatch[2]) : 0;

  const candidates = [];
  const candidateSet = new Set();

  for (const selector of unreadSelectors) {
    let elements = [];
    try {
      elements = Array.from(document.querySelectorAll(selector));
    } catch (_) {
      continue;
    }
    for (const element of elements) {
      if (!candidateSet.has(element) && isVisible(element)) {
        candidateSet.add(element);
        candidates.push(element);
      }
    }
  }

  const chatsByKey = new Map();
  let looseTotal = 0;

  candidates.slice(0, 300).forEach((candidate, index) => {
    const text = candidate.textContent || '';
    const aria = candidate.getAttribute('aria-label') || '';
    const titleAttr = candidate.getAttribute('title') || '';
    const testId = candidate.getAttribute('data-testid') || '';
    const qa = candidate.getAttribute('data-qa') || '';
    const className = typeof candidate.className === 'string' ? candidate.className : '';
    const semanticText = `${text} ${aria} ${titleAttr} ${testId} ${qa} ${className}`;

    const semanticUnread = /непрочитан|unread/i.test(semanticText);
    let unreadCount = Math.max(
      parseCount(text),
      parseCount(aria),
      parseCount(titleAttr)
    );
    if (!unreadCount && semanticUnread) unreadCount = 1;

    // Обычные декоративные badge/counter без числа и без слова unread пропускаем.
    if (!unreadCount) return;

    const container = candidate.closest(chatContainerSelector);
    if (!container || !isVisible(container)) {
      looseTotal += unreadCount;
      return;
    }

    const rawText = (container.innerText || container.textContent || '').trim();
    const lines = normalizedLines(rawText);
    const meaningful = lines.filter((line) => !/^\d{1,4}$/.test(line));

    const name = meaningful[0] ||
      container.getAttribute('aria-label') ||
      container.getAttribute('title') ||
      'Неизвестный чат';
    const snippet = meaningful.length > 1 ? meaningful[meaningful.length - 1] : '';

    const href = container instanceof HTMLAnchorElement ? container.getAttribute('href') : '';
    const key =
      container.getAttribute('data-chat-id') ||
      container.getAttribute('data-dialog-id') ||
      container.getAttribute('data-testid') ||
      container.getAttribute('data-qa') ||
      href ||
      container.getAttribute('aria-label') ||
      `${name}|${snippet}|${index}`;

    const existing = chatsByKey.get(key);
    if (!existing || unreadCount > existing.unreadCount) {
      chatsByKey.set(key, {
        key,
        name: String(name).slice(0, 200),
        snippet: String(snippet).slice(0, 500),
        unreadCount,
        rawText: String(rawText).slice(0, 1500),
      });
    }
  });

  const chats = Array.from(chatsByKey.values());
  const chatTotal = chats.reduce((sum, chat) => sum + chat.unreadCount, 0);
  const domTotal = Math.max(chatTotal + looseTotal, chats.length);

  return {
    title,
    titleTotal,
    domTotal,
    candidateCount: candidates.length,
    chats,
    url: location.href,
  };
}
"""


SCAN_ARGUMENTS = {
    "unreadSelectors": list(UNREAD_CANDIDATE_SELECTORS),
    "chatContainerSelector": CHAT_CONTAINER_SELECTOR,
}
