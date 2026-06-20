import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { qk } from "../lib/queryKeys";
import type { Me } from "../lib/types";

export function useProfile() {
  return useQuery({
    queryKey: qk.me,
    queryFn: () => api.get<Me>("/me"),
    staleTime: 5 * 60 * 1000,
  });
}
