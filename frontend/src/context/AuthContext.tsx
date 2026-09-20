import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { getCurrentUser, loginUser, registerUser } from "../api/auth";
import {
  clearStoredAccessToken,
  getStoredAccessToken,
  storeAccessToken,
  UNAUTHORIZED_EVENT,
} from "../api/client";
import type { AuthCredentials, User } from "../types/auth";
import { AuthContext, type AuthContextValue } from "./auth-context";

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() =>
    getStoredAccessToken(),
  );
  const [loading, setLoading] = useState(true);

  const clearSession = useCallback(() => {
    clearStoredAccessToken();
    setToken(null);
    setUser(null);
  }, []);

  const refreshCurrentUser = useCallback(async () => {
    if (!getStoredAccessToken()) {
      setUser(null);
      return;
    }

    try {
      setUser(await getCurrentUser());
    } catch {
      clearSession();
      throw new Error("Unable to restore the authenticated session.");
    }
  }, [clearSession]);

  useEffect(() => {
    let active = true;

    const restoreSession = async () => {
      try {
        if (getStoredAccessToken()) {
          const currentUser = await getCurrentUser();
          if (active) setUser(currentUser);
        }
      } catch {
        if (active) clearSession();
      } finally {
        if (active) setLoading(false);
      }
    };

    const handleUnauthorized = () => clearSession();
    window.addEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    void restoreSession();

    return () => {
      active = false;
      window.removeEventListener(UNAUTHORIZED_EVENT, handleUnauthorized);
    };
  }, [clearSession]);

  const login = useCallback(
    async (credentials: AuthCredentials) => {
      const response = await loginUser(credentials);
      storeAccessToken(response.access_token);
      setToken(response.access_token);

      try {
        const currentUser = await getCurrentUser();
        setUser(currentUser);
        navigate(
          currentUser.role === "admin" ? "/admin-dashboard" : "/dashboard",
          {
          replace: true,
          },
        );
      } catch (error) {
        clearSession();
        throw error;
      }
    },
    [clearSession, navigate],
  );

  const register = useCallback(
    async (credentials: AuthCredentials) => {
      await registerUser(credentials);
      navigate("/login", {
        replace: true,
        state: { registrationComplete: true },
      });
    },
    [navigate],
  );

  const logout = useCallback(() => {
    clearSession();
    navigate("/login", { replace: true });
  }, [clearSession, navigate]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      loading,
      login,
      register,
      logout,
      refreshCurrentUser,
    }),
    [user, token, loading, login, register, logout, refreshCurrentUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
