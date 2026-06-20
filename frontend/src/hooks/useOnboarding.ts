import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { qk } from "../lib/queryKeys";
import type { TrajectorySpec } from "../lib/types";

export function useSaveProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (spec: TrajectorySpec) => api.post("/onboarding/profile", spec),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.me });
      qc.invalidateQueries({ queryKey: ["feed"] });
      qc.invalidateQueries({ queryKey: qk.summary });
    },
  });
}

export function useSaveResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (r: { label: string; target_role?: string; content_text?: string }) =>
      api.post("/onboarding/resume", r),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me }),
  });
}
