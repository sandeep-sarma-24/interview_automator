import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setAuthToken, setOnUnauthorized } from "../lib/apiClient";
import type { CandidateToken } from "../lib/types";

const STORAGE_KEY = "jc_token";

interface AuthState {
  token: string | null;
  login: (token: string) => void;
  createCandidate: (display_name: string, email: string) => Promise<string>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY));

  // keep the api client in sync with the active token
  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setToken(null);
  }, []);

  useEffect(() => {
    setOnUnauthorized(() => logout());
  }, [logout]);

  const login = useCallback((t: string) => {
    localStorage.setItem(STORAGE_KEY, t);
    setToken(t);
  }, []);

  const createCandidate = useCallback(
    async (display_name: string, email: string) => {
      const res = await api.post<CandidateToken>("/candidates", { display_name, email });
      login(res.api_token);
      return res.api_token;
    },
    [login],
  );

  const value = useMemo<AuthState>(
    () => ({ token, login, createCandidate, logout }),
    [token, login, createCandidate, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
