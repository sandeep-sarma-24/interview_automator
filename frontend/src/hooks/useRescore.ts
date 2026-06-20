import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { qk } from "../lib/queryKeys";

export function useRescore() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<Record<string, unknown>>("/actions/score"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feed"] });
      qc.invalidateQueries({ queryKey: qk.summary });
    },
  });
}
