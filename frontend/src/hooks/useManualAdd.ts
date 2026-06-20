import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { qk } from "../lib/queryKeys";

export function useManualAdd() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => api.post<Record<string, unknown>>("/jobs/manual", { url }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feed"] });
      qc.invalidateQueries({ queryKey: qk.summary });
    },
  });
}
