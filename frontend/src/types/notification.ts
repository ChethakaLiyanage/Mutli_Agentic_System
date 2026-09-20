export interface NotificationItem {
  id: string;
  user_id: string;
  workflow_id?: string | null;
  claim_id?: string | null;
  notification_type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at?: string | null;
  read_at?: string | null;
}

export interface NotificationListResponse {
  notifications: NotificationItem[];
  unread_count: number;
}
