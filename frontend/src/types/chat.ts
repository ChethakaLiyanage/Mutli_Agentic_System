export interface ChatMessage {
  id: string;
  eventId?: string;
  sender: "user" | "system";
  text: string;
  timestamp: string;
}
