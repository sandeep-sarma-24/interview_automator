import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { qk } from "../lib/queryKeys";
import type { Preference, PreferenceRow } from "../lib/types";

export function usePreferences() {
  return useQuery({
    queryKey: qk.preferences,
    queryFn: () => api.get<PreferenceRow[]>("/preferences"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSetPreference() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: { company: string; preference: Preference; note?: string }) =>
      api.post("/preferences", p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.preferences });
      qc.invalidateQueries({ queryKey: ["feed"] });
    },
  });
}
