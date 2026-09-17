import { createContext, useContext } from "react";

import type { AuthCredentials, User } from "../types/auth";

export interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (credentials: AuthCredentials) => Promise<void>;
  register: (credentials: AuthCredentials) => Promise<void>;
  logout: () => void;
  refreshCurrentUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
);

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
};
