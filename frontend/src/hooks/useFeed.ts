import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { qk, type FeedFilters } from "../lib/queryKeys";
import type { FeedResponse } from "../lib/types";

export function useFeed(filters: FeedFilters) {
  const params = new URLSearchParams({
    states: filters.states,
    limit: String(filters.limit),
    offset: String(filters.offset),
  });
  if (filters.search) params.set("search", filters.search);

  return useQuery({
    queryKey: qk.feed(filters),
    queryFn: () => api.get<FeedResponse>(`/feed?${params.toString()}`),
    staleTime: 30 * 1000,
    placeholderData: keepPreviousData,
  });
}
