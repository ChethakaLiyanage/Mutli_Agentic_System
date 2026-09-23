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

// ==========================================
// Policy & Knowledge Document Management API
// ==========================================

export type DocumentStatus = "processing" | "active" | "superseded" | "failed" | "archived";
export type DocumentAudience = "customer" | "internal" | "all";

export interface PolicyDocumentItem {
  id: string;
  root_document_id: string;
  title: string;
  document_type: string;
  policy_type: PolicyCategory | null;
  audience: DocumentAudience;
  version: string;
  original_filename: string;
  storage_path?: string | null;
  checksum?: string | null;
  status: DocumentStatus;
  chunks_count: number;
  previous_version_id?: string | null;
  change_summary?: string | null;
  uploaded_by: string;
  created_at: string;
  activated_at?: string | null;
  superseded_at?: string | null;
  updated_at: string;
  metadata?: Record<string, unknown>;
}

export interface PolicyDocumentListResponse {
  documents: PolicyDocumentItem[];
  total: number;
}

export interface PolicyDocumentDetailResponse {
  document: PolicyDocumentItem;
  content_preview?: string | null;
  chunks_count: number;
}

export interface PolicyDocumentVersionsResponse {
  root_document_id: string;
  title: string;
  versions: PolicyDocumentItem[];
}

export interface PolicyDocumentOperationResponse {
  success: boolean;
  message: string;
  document: PolicyDocumentItem;
  chunks_indexed: number;
}

export const fetchPolicyDocuments = async (params?: {
  status?: string;
  policy_type?: string;
  document_type?: string;
  root_only?: boolean;
}): Promise<PolicyDocumentListResponse> => {
  const response = await apiClient.get<PolicyDocumentListResponse>(
    "/admin/policy-documents",
    { params },
  );
  return response.data;
};

export const fetchPolicyDocumentDetail = async (
  documentId: string,
): Promise<PolicyDocumentDetailResponse> => {
  const response = await apiClient.get<PolicyDocumentDetailResponse>(
    `/admin/policy-documents/${documentId}`,
  );
  return response.data;
};

export const fetchPolicyDocumentVersions = async (
  documentId: string,
): Promise<PolicyDocumentVersionsResponse> => {
  const response = await apiClient.get<PolicyDocumentVersionsResponse>(
    `/admin/policy-documents/${documentId}/versions`,
  );
  return response.data;
};

export const fetchPolicyDocumentContent = async (
  documentId: string,
): Promise<string> => {
  const response = await apiClient.get<string>(
    `/admin/policy-documents/${documentId}/content`,
    { responseType: "text" },
  );
  return response.data;
};

export const uploadPolicyDocument = async (
  formData: FormData,
): Promise<PolicyDocumentOperationResponse> => {
  const response = await apiClient.post<PolicyDocumentOperationResponse>(
    "/admin/policy-documents",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );
  return response.data;
};

export const replacePolicyDocument = async (
  documentId: string,
  formData: FormData,
): Promise<PolicyDocumentOperationResponse> => {
  const response = await apiClient.post<PolicyDocumentOperationResponse>(
    `/admin/policy-documents/${documentId}/replace`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );
  return response.data;
};
