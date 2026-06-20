// TS types mirroring the backend API contracts (§1 of the M3 plan).

export type Verdict = "INTERESTED" | "NOT_INTERESTED" | "BOOKMARK" | "WRONG_MATCH";
export type TrajectoryDirection = "LEAP" | "FORWARD" | "LATERAL" | "STALL" | "BACKWARD";
export type Preference = "PREFERRED" | "NEUTRAL" | "AVOID" | "BLOCKED";

export interface CandidateToken {
  id: number;
  display_name: string;
  api_token: string;
}

export interface Me {
  id: number;
  display_name: string;
  email: string;
  has_profile: boolean;
  profile_version_no: number | null;
  resumes: { label: string; target_role: string | null }[];
}

export interface TrajectorySpec {
  total_experience_months: number;
  seniority_label?: string | null;
  core_skills: string[];
  acquiring_skills: string[];
  target_roles: string[];
  acceptable_roles: string[];
  avoid_roles: string[];
  target_domain_signals: string[];
  cities: string[];
  remote_required: boolean;
  current_ctc?: number | null;
  salary_min_multiplier?: number;
  salary_target_multiplier?: number;
  salary_stretch_multiplier?: number;
}

export interface FeedItem {
  application_id: number;
  current_state: string;
  reason_code: string | null;
  priority_score: number | null;
  verdict: Verdict | null;
  title: string;
  location: string | null;
  is_remote: number | null;
  source: string;
  source_url: string | null;
  company: string;
  trajectory_direction: TrajectoryDirection | null;
  total_score: number | null;
  confidence: number | null;
  leap_override: number | null;
  signal_density: "RICH" | "THIN" | null;
  explanation_summary: string | null;
}

export interface FeedResponse {
  total: number;
  limit: number;
  offset: number;
  items: FeedItem[];
}

export interface Signal {
  signal_type: string;
  direction: "POSITIVE" | "NEGATIVE" | "NEUTRAL";
  label: string;
  detail: string | null;
}

export interface ApplicationDetail extends FeedItem {
  description_text: string | null;
  scoring_model_version: string | null;
  verdict_note: string | null;
  signals: Signal[];
}

export interface Summary {
  by_state: Record<string, number>;
  leaps: number;
  interested: number;
  not_interested: number;
  bookmarked: number;
  wrong_match: number;
  last_discovery_at: string | null;
}

export interface DiagnosticsSource {
  source: string;
  type: string;
  active_boards: number | null;
  healthy?: number;
  degraded?: number;
  broken?: number;
  last_sync: string | null;
  jobs_discovered: number;
  jobs_failed: number;
  status: "OK" | "DEGRADED" | "ERROR" | "IDLE";
}

export interface DiagnosticsRun {
  company: string;
  platform: string;
  status: string;
  jobs_new: number;
  jobs_dropped: number;
  error: string | null;
  started_at: string;
}

export interface Diagnostics {
  sources: DiagnosticsSource[];
  recent_runs: DiagnosticsRun[];
  totals: { companies_active: number; companies_disabled: number; jobs_total: number };
}

export interface PreferenceRow {
  company: string;
  preference: Preference;
  note: string | null;
}

export interface VerdictResponse {
  application_id: number;
  verdict: Verdict;
  verdict_note: string | null;
  current_state: string;
}
