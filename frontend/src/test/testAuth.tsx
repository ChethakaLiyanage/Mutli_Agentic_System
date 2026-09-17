import type { ReactNode } from "react";

import { AuthContext, type AuthContextValue } from "../context/auth-context";

export const customer = {
  user_id: "USR-001",
  email: "customer@example.com",
  role: "customer" as const,
  created_at: "2026-09-17T10:00:00Z",
};

export const createAuthValue = (
  overrides: Partial<AuthContextValue> = {},
): AuthContextValue => ({
  user: null,
  token: null,
  loading: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshCurrentUser: vi.fn(),
  ...overrides,
});

export const TestAuthProvider = ({
  value,
  children,
}: {
  value: AuthContextValue;
  children: ReactNode;
}) => <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
