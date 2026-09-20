import { apiClient } from "./client";
import type {
  ClaimAssignmentRequest,
  ClaimAssignmentResponse,
  HumanDecisionRequest,
  HumanDecisionResponse,
  ReviewDetailResponse,
  ReviewQueueResponse,
} from "../types/review";

export const fetchReviewQueue = async (): Promise<ReviewQueueResponse> => {
  const response = await apiClient.get<ReviewQueueResponse>("/review/queue", {
    params: { limit: 100, offset: 0 },
  });
  return response.data;
};

export const fetchReviewDetail = async (
  workflowId: string,
): Promise<ReviewDetailResponse> => {
  const response = await apiClient.get<ReviewDetailResponse>(
    `/review/workflows/${encodeURIComponent(workflowId)}`,
  );
  return response.data;
};

export const assignClaim = async (
  workflowId: string,
  request: ClaimAssignmentRequest,
): Promise<ClaimAssignmentResponse> => {
  const response = await apiClient.post<ClaimAssignmentResponse>(
    `/review/workflows/${encodeURIComponent(workflowId)}/assign`,
    request,
  );
  return response.data;
};

export const submitHumanDecision = async (
  workflowId: string,
  request: HumanDecisionRequest,
): Promise<HumanDecisionResponse> => {
  const response = await apiClient.post<HumanDecisionResponse>(
    `/review/workflows/${encodeURIComponent(workflowId)}/decision`,
    request,
  );
  return response.data;
};
