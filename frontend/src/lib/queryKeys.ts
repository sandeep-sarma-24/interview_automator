export interface FeedFilters {
  states: string;
  search: string;
  limit: number;
  offset: number;
}

export const qk = {
  me: ["me"] as const,
  summary: ["summary"] as const,
  diagnostics: ["diagnostics"] as const,
  preferences: ["preferences"] as const,
  feed: (f: FeedFilters) => ["feed", f] as const,
  application: (id: number) => ["application", id] as const,
};
