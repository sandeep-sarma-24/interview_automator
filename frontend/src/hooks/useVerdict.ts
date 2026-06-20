import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { qk } from "../lib/queryKeys";
import type { Verdict, VerdictResponse } from "../lib/types";

export function useVerdict() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { applicationId: number; verdict: Verdict; note?: string }) =>
      api.post<VerdictResponse>(`/applications/${v.applicationId}/verdict`, {
        verdict: v.verdict,
        note: v.note,
      }),
    onSuccess: (_res, vars) => {
      // Verdicts move applications between states; refresh the lists.
      qc.invalidateQueries({ queryKey: ["feed"] });
      qc.invalidateQueries({ queryKey: qk.summary });
      qc.invalidateQueries({ queryKey: qk.application(vars.applicationId) });
    },
  });
}
