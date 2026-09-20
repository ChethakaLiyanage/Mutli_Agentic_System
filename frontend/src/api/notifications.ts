import { apiClient } from "./client";
import type {
  NotificationItem,
  NotificationListResponse,
} from "../types/notification";

export const fetchNotifications = async (): Promise<NotificationListResponse> => {
  const response = await apiClient.get<NotificationListResponse>("/notifications");
  return response.data;
};

export const markNotificationRead = async (
  notificationId: string,
): Promise<NotificationItem> => {
  const response = await apiClient.patch<NotificationItem>(
    `/notifications/${encodeURIComponent(notificationId)}/read`,
  );
  return response.data;
};
