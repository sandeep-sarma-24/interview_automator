import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { qk } from "../lib/queryKeys";
import type { Diagnostics } from "../lib/types";

export function useDiagnostics() {
  return useQuery({
    queryKey: qk.diagnostics,
    queryFn: () => api.get<Diagnostics>("/diagnostics"),
    staleTime: 60 * 1000,
  });
}
