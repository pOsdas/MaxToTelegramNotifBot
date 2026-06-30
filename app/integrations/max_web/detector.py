from __future__ import annotations

from app.integrations.max_web.selectors import (
    CHAT_NAME_SELECTORS,
    CHAT_ROW_SELECTOR,
    CHAT_SNIPPET_SELECTORS,
    CHAT_TIME_SELECTORS,
    UNREAD_CANDIDATE_SELECTORS,
)


UNREAD_SCAN_SCRIPT = r"""
(args) => {
  const unreadSelectors = args.unreadSelectors;
  const chatRowSelector = args.chatRowSelector;
  const chatNameSelectors = args.chatNameSelectors;
  const chatSnippetSelectors = args.chatSnippetSelectors;
  const chatTimeSelectors = args.chatTimeSelectors;

  const isVisible = (element) => {
    if (!(element instanceof Element)) return false;

    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();

    return style.display !== "none" &&
      style.visibility !== "hidden" &&
      Number(style.opacity || "1") > 0 &&
      rect.width > 0 &&
      rect.height > 0;
  };

  const normalize = (value) => String(value || "")
    .replace(/\s+/g, " ")
    .trim();

  const normalizedLines = (value) => String(value || "")
    .split("\n")
    .map((line) => normalize(line))
    .filter(Boolean);

  const parseCount = (value) => {
    const compact = normalize(value);
    const match = compact.match(/(?:^|\D)(\d{1,4})(?:\D|$)/);

    if (!match) return 0;

    const count = Number(match[1]);
    return Number.isFinite(count) && count > 0 ? count : 0;
  };

  const firstText = (root, selectors) => {
    for (const selector of selectors) {
      try {
        const element = root.querySelector(selector);
        const text = normalize(element?.textContent);
        if (text) return text;
      } catch (_) {
        // Один невалидный селектор не должен ломать весь цикл проверки.
      }
    }
    return "";
  };

  const title = document.title || "";

  // MAX Web сейчас использует заголовок вида "2 непрочитанных чата".
  // Оставляем также поддержку старых форматов "(2) MAX" и "[2] MAX".
  const titleWordMatch = title.match(
    /^\s*(\d{1,4})\s+(?:непрочитан|unread)/i
  );
  const titleBracketMatch = title.match(
    /^\s*[\[(](\d{1,4})[\])]/
  );
  const titleTotal = Number(
    titleWordMatch?.[1] || titleBracketMatch?.[1] || 0
  );

  const candidateSet = new Set();
  const candidates = [];

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

  const chats = [];
  const seenRows = new Set();
  let unmatchedUnreadTotal = 0;

  for (const candidate of candidates.slice(0, 300)) {
    const aria = normalize(candidate.getAttribute("aria-label"));
    const titleAttr = normalize(candidate.getAttribute("title"));
    const text = normalize(candidate.textContent);
    const semanticText = normalize(`${aria} ${titleAttr} ${text}`).toLowerCase();

    const isRussianUnreadMessage =
      semanticText.includes("нов") && semanticText.includes("сообщен");
    const isEnglishUnreadMessage =
      semanticText.includes("unread") && semanticText.includes("message");

    // Счётчики папок имеют текст "непрочитанных чатов" и сюда не попадают.
    if (!isRussianUnreadMessage && !isEnglishUnreadMessage) {
      continue;
    }

    const unreadCount = Math.max(
      parseCount(aria),
      parseCount(titleAttr),
      parseCount(text),
      1
    );

    const row = candidate.closest(chatRowSelector);

    if (!row || !isVisible(row)) {
      unmatchedUnreadTotal += unreadCount;
      continue;
    }

    if (seenRows.has(row)) {
      continue;
    }
    seenRows.add(row);

    const name = firstText(row, chatNameSelectors) || "Неизвестный чат";
    const snippet = firstText(row, chatSnippetSelectors);
    const time = firstText(row, chatTimeSelectors);
    const rawText = normalize(row.innerText || row.textContent || "");

    const stableId =
      row.getAttribute("data-chat-id") ||
      row.getAttribute("data-dialog-id") ||
      row.getAttribute("data-peer-id") ||
      row.querySelector("[data-chat-id]")?.getAttribute("data-chat-id") ||
      row.querySelector("[data-dialog-id]")?.getAttribute("data-dialog-id") ||
      "";

    // В текущей разметке отдельного ID чата нет. Имя является более стабильным
    // ключом, чем data-index: индекс меняется при сортировке списка чатов.
    const key = normalize(stableId) || name.toLocaleLowerCase("ru-RU");

    chats.push({
      key,
      name: name.slice(0, 200),
      snippet: snippet.slice(0, 1000),
      unreadCount,
      rawText: rawText.slice(0, 2000),
      time: time.slice(0, 100),
      rowIndex: row.getAttribute("data-index") || "",
    });
  }

  const chatTotal = chats.reduce(
    (sum, chat) => sum + chat.unreadCount,
    0
  );
  const domTotal = chatTotal + unmatchedUnreadTotal;

  return {
    title,
    titleTotal,
    domTotal,
    candidateCount: candidates.length,
    matchedChatCount: chats.length,
    unmatchedUnreadTotal,
    chats,
    url: location.href,
  };
}
"""


SCAN_ARGUMENTS = {
    "unreadSelectors": list(UNREAD_CANDIDATE_SELECTORS),
    "chatRowSelector": CHAT_ROW_SELECTOR,
    "chatNameSelectors": list(CHAT_NAME_SELECTORS),
    "chatSnippetSelectors": list(CHAT_SNIPPET_SELECTORS),
    "chatTimeSelectors": list(CHAT_TIME_SELECTORS),
}
