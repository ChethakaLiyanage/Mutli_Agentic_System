import axios, { AxiosError } from "axios";

export const ACCESS_TOKEN_KEY = "motor_insurance_access_token";
export const UNAUTHORIZED_EVENT = "motor-insurance:unauthorized";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.trim();

if (!API_BASE_URL) {
  console.warn(
    "VITE_API_BASE_URL is not set. API requests will use the current origin.",
  );
}

export const getStoredAccessToken = (): string | null =>
  localStorage.getItem(ACCESS_TOKEN_KEY);

export const storeAccessToken = (token: string): void => {
  // localStorage is acceptable for this prototype. Production applications
  // should consider server-managed HTTP-only cookies and CSRF protection.
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
};

export const clearStoredAccessToken = (): void => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
};

export const apiClient = axios.create({
  baseURL: API_BASE_URL || undefined,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = getStoredAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 && getStoredAccessToken()) {
      clearStoredAccessToken();
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    return Promise.reject(error);
  },
);

type BackendValidationIssue = {
  msg?: string;
};

type BackendErrorBody = {
  detail?: string | BackendValidationIssue[];
};

export const getApiErrorMessage = (
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string => {
  if (!axios.isAxiosError<BackendErrorBody>(error)) {
    return error instanceof Error && error.message ? error.message : fallback;
  }

  if (!error.response) {
    return "Unable to reach the service. Check your connection and try again.";
  }

  const detail = error.response.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const message = detail.find((issue) => issue.msg)?.msg;
    if (message) return message;
  }

  const statusMessages: Record<number, string> = {
    401: "Your session is invalid or has expired. Please sign in again.",
    403: "You do not have permission to perform this action.",
    409: "This account already exists.",
    422: "Please check the information you entered.",
    500: "The service encountered a problem. Please try again later.",
  };

  return statusMessages[error.response.status] ?? fallback;
};
