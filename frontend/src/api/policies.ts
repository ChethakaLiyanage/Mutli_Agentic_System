import { apiClient } from "./client";
import type { MyPoliciesResponse } from "../types/policy";

export const fetchMyPolicies = async (): Promise<MyPoliciesResponse> => {
  const response = await apiClient.get<MyPoliciesResponse>("/policies/my-policies");
  return response.data;
};