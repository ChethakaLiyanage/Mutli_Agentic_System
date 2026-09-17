export interface ChatMessage {
  id: string;
  sender: "user" | "system";
  text: string;
  timestamp: string;
}
