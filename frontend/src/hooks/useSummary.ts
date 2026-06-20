import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { qk } from "../lib/queryKeys";
import type { Summary } from "../lib/types";

export function useSummary() {
  return useQuery({
    queryKey: qk.summary,
    queryFn: () => api.get<Summary>("/summary"),
    staleTime: 30 * 1000,
  });
}
