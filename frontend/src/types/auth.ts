export type UserRole = "customer" | "claims_officer" | "admin";

export interface User {
  user_id: string;
  email: string;
  role: UserRole;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface AuthCredentials {
  email: string;
  password: string;
}
