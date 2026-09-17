import { apiClient } from "./client";
import type { AuthCredentials, LoginResponse, User } from "../types/auth";

export const registerUser = async (
  credentials: AuthCredentials,
): Promise<User> => {
  const response = await apiClient.post<User>("/auth/register", credentials);
  return response.data;
};

export const loginUser = async (
  credentials: AuthCredentials,
): Promise<LoginResponse> => {
  const response = await apiClient.post<LoginResponse>(
    "/auth/login",
    credentials,
  );
  return response.data;
};

export const getCurrentUser = async (): Promise<User> => {
  const response = await apiClient.get<User>("/auth/me");
  return response.data;
};
