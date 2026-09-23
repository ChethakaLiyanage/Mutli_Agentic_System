import { apiClient } from "./client";

export type PolicyCategory =
  | "full_comprehensive"
  | "partial_comprehensive"
  | "third_party";

export interface AdminCustomerCreatePayload {
  name?: string;
  email: string;
  password: string;
  policy_type: PolicyCategory;
}

export interface AdminCustomer {
  user_id: string;
  email: string;
  name: string | null;
  role: "customer";
  policy_id: string;
  policy_number: string;
  policy_type: PolicyCategory;
  created_at: string;
}

export interface AdminCustomerListResponse {
  customers: AdminCustomer[];
  total: number;
}

export const createCustomerAccount = async (
  payload: AdminCustomerCreatePayload,
): Promise<AdminCustomer> => {
  const response = await apiClient.post<AdminCustomer>(
    "/admin/customers",
    payload,
  );
  return response.data;
};

export const fetchCustomersList = async (): Promise<AdminCustomerListResponse> => {
  const response = await apiClient.get<AdminCustomerListResponse>(
    "/admin/customers",
  );
  return response.data;
};
