// Operator API client — separate OPS_TOKEN (X-Ops-Token), distinct from the
// candidate token. 503 => operator endpoints disabled (SCRAPER_OPS_TOKEN unset).
const BASE = (import.meta.env.VITE_API_BASE as string) || "/api";
const KEY = "jc_ops_token";

let token: string | null = localStorage.getItem(KEY);
let onUnauthorized: (() => void) | null = null;

export function setOpsToken(t: string | null): void {
  token = t;
  if (t) localStorage.setItem(KEY, t);
  else localStorage.removeItem(KEY);
}
export function getOpsToken(): string | null {
  return token;
}
export function setOnOpsUnauthorized(cb: () => void): void {
  onUnauthorized = cb;
}

export class OpsError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (token) headers["X-Ops-Token"] = token;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    onUnauthorized?.();
    throw new OpsError(401, "Invalid operator token");
  }
  if (res.status === 503) {
    throw new OpsError(503, "Operator endpoints disabled (set SCRAPER_OPS_TOKEN)");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new OpsError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const ops = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
};
