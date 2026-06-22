import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { getOpsToken, setOnOpsUnauthorized, setOpsToken } from "./opsClient";

interface OpsAuthState {
  token: string | null;
  login: (t: string) => void;
  logout: () => void;
}

const Ctx = createContext<OpsAuthState | null>(null);

export function OpsAuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getOpsToken());

  const logout = useCallback(() => {
    setOpsToken(null);
    setToken(null);
  }, []);
  const login = useCallback((t: string) => {
    setOpsToken(t.trim());
    setToken(t.trim());
  }, []);

  useEffect(() => setOnOpsUnauthorized(() => logout()), [logout]);

  const value = useMemo(() => ({ token, login, logout }), [token, login, logout]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useOpsAuth(): OpsAuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useOpsAuth must be used within OpsAuthProvider");
  return v;
}
