import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ops } from "./opsClient";
import type {
  OpsApiCalls, OpsDiscovery, OpsDrops, OpsErrors, OpsExplain, OpsHealth, OpsWorker,
  RoleMethods, RoleUnresolved,
} from "./types";

const live = (ms: number) => ({ refetchInterval: ms, staleTime: ms });

export const useOpsHealth = () =>
  useQuery({ queryKey: ["ops", "health"], queryFn: () => ops.get<OpsHealth>("/ops/health"), ...live(15000) });

export const useOpsDiscovery = () =>
  useQuery({ queryKey: ["ops", "discovery"], queryFn: () => ops.get<OpsDiscovery>("/ops/discovery"), ...live(30000) });

export const useOpsDrops = (reason?: string) =>
  useQuery({
    queryKey: ["ops", "drops", reason ?? ""],
    queryFn: () => ops.get<OpsDrops>(`/ops/discovery/drops?limit=100${reason ? `&reason=${reason}` : ""}`),
    staleTime: 30000,
  });

export const useOpsWorker = () =>
  useQuery({ queryKey: ["ops", "worker"], queryFn: () => ops.get<OpsWorker>("/ops/worker"), ...live(15000) });

export const useOpsApiCalls = (windowHours = 24) =>
  useQuery({
    queryKey: ["ops", "api-calls", windowHours],
    queryFn: () => ops.get<OpsApiCalls>(`/ops/api-calls?window_hours=${windowHours}`),
    ...live(30000),
  });

export const useOpsErrors = () =>
  useQuery({ queryKey: ["ops", "errors"], queryFn: () => ops.get<OpsErrors>("/ops/errors"), ...live(20000) });

export const useRoleMethods = () =>
  useQuery({ queryKey: ["ops", "roles", "methods"], queryFn: () => ops.get<RoleMethods>("/ops/roles/methods"), staleTime: 30000 });

export const useRoleUnresolved = () =>
  useQuery({ queryKey: ["ops", "roles", "unresolved"], queryFn: () => ops.get<RoleUnresolved>("/ops/roles/unresolved?limit=200"), staleTime: 30000 });

export const useOpsExplain = (id: number | null) =>
  useQuery({
    queryKey: ["ops", "explain", id],
    queryFn: () => ops.get<OpsExplain>(`/ops/applications/${id}/explain`),
    enabled: id != null,
  });

export function useAddAlias() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { title: string; canonical_key: string }) => ops.post("/ops/roles/aliases", v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ops", "roles"] }),
  });
}
