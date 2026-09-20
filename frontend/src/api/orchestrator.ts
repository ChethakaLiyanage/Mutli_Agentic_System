import axios from "axios";

import { apiClient, getApiErrorMessage } from "./client";
import type { ClaimDocumentItem } from "../types/review";
import type {
  ClarificationRequest,
  OrchestratorRequest,
  OrchestratorResponse,
  WorkflowResponse,
} from "../types/orchestrator";

export const processRequest = async (
  request: OrchestratorRequest,
): Promise<WorkflowResponse> => {
  const response = await apiClient.post<WorkflowResponse>(
    "/orchestrator/process",
    request,
  );
  return response.data;
};

export const clarifyWorkflow = async (
  workflowId: string,
  request: ClarificationRequest,
): Promise<WorkflowResponse> => {
  const response = await apiClient.post<WorkflowResponse>(
    `/orchestrator/workflows/${encodeURIComponent(workflowId)}/clarify`,
    request,
  );
  return response.data;
};

export const getWorkflow = async (
  workflowId: string,
): Promise<OrchestratorResponse> => {
  const response = await apiClient.get<OrchestratorResponse>(
    `/orchestrator/workflows/${encodeURIComponent(workflowId)}`,
  );
  return response.data;
};

export const submitClaim = async (
  workflowId: string,
): Promise<OrchestratorResponse> => {
  const response = await apiClient.post<OrchestratorResponse>(
    `/orchestrator/workflows/${encodeURIComponent(workflowId)}/submit-claim`,
  );
  return response.data;
};

export const uploadWorkflowDocument = async (
  workflowId: string,
  file: File,
  documentType?: string,
): Promise<ClaimDocumentItem> => {
  const formData = new FormData();
  formData.append("file", file);
  if (documentType) {
    formData.append("document_type", documentType);
  }
  const response = await apiClient.post<ClaimDocumentItem>(
    `/orchestrator/workflows/${encodeURIComponent(workflowId)}/documents`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );
  return response.data;
};

export const getWorkflowDocuments = async (
  workflowId: string,
): Promise<{ documents: ClaimDocumentItem[]; count: number }> => {
  const response = await apiClient.get<{ documents: ClaimDocumentItem[]; count: number }>(
    `/orchestrator/workflows/${encodeURIComponent(workflowId)}/documents`,
  );
  return response.data;
};

export const isWorkflowNotFoundError = (error: unknown): boolean =>
  axios.isAxiosError(error) && error.response?.status === 404;

export const getOrchestratorErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const statusMessages: Record<number, string> = {
      403: "You are not authorized to access this workflow.",
      404: "This workflow could not be found.",
      409: "This workflow can no longer accept clarification.",
      500: "The workflow service is temporarily unavailable. Please try again.",
    };
    const status = error.response?.status;
    if (status && statusMessages[status]) return statusMessages[status];
  }

  return getApiErrorMessage(
    error,
    "The request could not be processed. Please try again.",
  );
};
