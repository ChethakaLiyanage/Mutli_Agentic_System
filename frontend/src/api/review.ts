import { apiClient } from "./client";
import type { ReviewQueueResponse } from "../types/review";

export const fetchReviewQueue = async (): Promise<ReviewQueueResponse> => {
  const response = await apiClient.get<ReviewQueueResponse>("/review/queue", {
    params: { limit: 100, offset: 0 },
  });
  return response.data;
};
