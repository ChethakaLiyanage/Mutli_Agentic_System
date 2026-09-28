import type { ChatMessage } from "../types/chat";

export const CHAT_HISTORY_KEY_PREFIX = "motor_insurance_chat_history_";

export const chatHistoryStorageKey = (userId: string): string =>
  `${CHAT_HISTORY_KEY_PREFIX}${encodeURIComponent(userId)}`;

const isStoredChatMessage = (value: unknown): value is ChatMessage => {
  if (!value || typeof value !== "object") return false;
  const message = value as Record<string, unknown>;
  return (
    typeof message.id === "string" &&
    message.id.length > 0 &&
    (message.eventId === undefined || typeof message.eventId === "string") &&
    (message.sender === "user" || message.sender === "system") &&
    typeof message.text === "string" &&
    typeof message.timestamp === "string" &&
    !Number.isNaN(Date.parse(message.timestamp))
  );
};

export const loadChatHistory = (storageKey: string | null): ChatMessage[] => {
  if (!storageKey) return [];
  try {
    const storedValue = localStorage.getItem(storageKey);
    if (!storedValue) return [];
    const parsed: unknown = JSON.parse(storedValue);
    return Array.isArray(parsed) && parsed.every(isStoredChatMessage)
      ? parsed
      : [];
  } catch {
    return [];
  }
};

export const saveChatHistory = (
  storageKey: string | null,
  messages: ChatMessage[],
): void => {
  if (!storageKey) return;
  try {
    if (messages.length === 0) {
      localStorage.removeItem(storageKey);
      return;
    }
    localStorage.setItem(storageKey, JSON.stringify(messages));
  } catch {
    // Browser storage may be disabled or full; chat remains usable in memory.
  }
};

export const clearChatHistory = (storageKey: string | null): void => {
  if (!storageKey) return;
  try {
    localStorage.removeItem(storageKey);
  } catch {
    // Clearing browser storage is best-effort and must not break New Chat.
  }
};
