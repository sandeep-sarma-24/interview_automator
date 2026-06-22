// Types mirroring app/repositories/ops.py + ops_routes.py responses.

export interface OpsHealth {
  db: string;
  worker: { status: string; heartbeat_age_s: number | null };
  ollama: { status: string; mode: string };
  discovery: { healthy: number; degraded: number; broken: number };
  totals: { jobs: number; companies_active: number; companies_disabled: number };
  last_error_at: string | null;
  last_discovery_at: string | null;
}

export interface DiscoverySource {
  source: string;
  last_run: string | null;
  jobs_new: number;
  jobs_dropped: number;
  active_boards?: number;
  status: string;
}
export interface DiscoveryRun {
  company: string; platform: string; status: string;
  jobs_new: number; jobs_dropped: number; error: string | null; started_at: string;
}
export interface OpsDiscovery {
  sources: DiscoverySource[];
  rejection_reasons: Record<string, number>;
  failing_boards: { company: string; token: string; reason: string | null }[];
  recent_runs: DiscoveryRun[];
}
export interface DropItem { ts: string; source: string; company: string | null; title: string | null; reason: string }
export interface OpsDrops { total: number; limit: number; offset: number; items: DropItem[] }

export interface WorkerCycle { ts: string; level: string; duration_ms: number | null; metadata: Record<string, unknown> }
export interface OpsWorker {
  status: string; heartbeat_age_s: number | null;
  recent_cycles: WorkerCycle[];
  backlogs: { unscored_jobs: number; by_state: Record<string, number> };
}

export interface ApiServiceStat {
  service: string; calls: number; failures: number; retries: number;
  p50_ms: number | null; p95_ms: number | null;
}
export interface ApiFailure { ts: string; service: string; host: string; path: string; status_code: number | null; error: string | null }
export interface OpsApiCalls { window_hours: number; by_service: ApiServiceStat[]; recent_failures: ApiFailure[] }

export interface ErrorGroup {
  category: string; source: string | null; error_type: string; message: string | null;
  stack_trace: string | null; count: number; first_seen: string; last_seen: string;
}
export interface OpsErrors { groups: ErrorGroup[] }

export interface RoleMethods { counts: Record<string, number>; total: number; coverage_pct: number }
export interface RoleUnresolved { items: { normalized_title: string; best_sim: number | null; resolved_at: string }[] }

export interface ExplainDim { score: number | null; weight: number; contribution: number }
export interface ScoreExplain {
  trajectory_direction: string | null;
  dimensions: Record<string, ExplainDim>;
  weighted_sum: number; company_adjust: number | null; final_score: number | null;
  confidence: number | null; signal_density: string | null; leap_override: number | null;
  embed_sim: number | null; scoring_model_version: string | null;
}
export interface OpsExplain {
  application_id: number; company: string; title: string; candidate_id: number;
  current_state: string; reason_code: string | null;
  explain: ScoreExplain;
  signals: { signal_type: string; direction: string; label: string; detail: string | null }[];
}
