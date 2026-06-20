import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { qk } from "../lib/queryKeys";
import type { ApplicationDetail } from "../lib/types";

export function useApplication(id: number) {
  return useQuery({
    queryKey: qk.application(id),
    queryFn: () => api.get<ApplicationDetail>(`/applications/${id}`),
    staleTime: 60 * 1000,
  });
}
