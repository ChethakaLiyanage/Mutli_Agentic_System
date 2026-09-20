import { apiClient } from "./client";
import type { ClaimDetailCustomer, MyClaimsResponse } from "../types/claim";

export const fetchMyClaims = async (): Promise<MyClaimsResponse> => {
  const response = await apiClient.get<MyClaimsResponse>("/claims/my-claims");
  return response.data;
};

export const fetchClaimDetail = async (
  claimId: string,
): Promise<ClaimDetailCustomer> => {
  const response = await apiClient.get<ClaimDetailCustomer>(
    `/claims/${encodeURIComponent(claimId)}`,
  );
  return response.data;
};
