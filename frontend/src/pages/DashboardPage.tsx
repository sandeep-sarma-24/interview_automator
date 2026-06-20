import { useState } from "react";
import { Link } from "react-router-dom";
import { useSummary } from "../hooks/useSummary";
import { useRescore } from "../hooks/useRescore";
import { useProfile } from "../hooks/useProfile";
import { relativeTime } from "../lib/format";
import LoadingSkeleton from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import Banner from "../components/Banner";
import AddJobModal from "../components/AddJobModal";

function Stat({ label, value, to }: { label: string; value: number; to?: string }) {
  const body = (
    <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <p className="text-2xl font-bold tabular-nums">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
  return to ? <Link to={to}>{body}</Link> : body;
}

export default function DashboardPage() {
  const { data: me } = useProfile();
  const { data, isLoading, isError, refetch } = useSummary();
  const rescore = useRescore();
  const [showAdd, setShowAdd] = useState(false);

  if (isLoading) return <LoadingSkeleton label="Loading summary…" />;
  if (isError || !data) return <ErrorState onRetry={() => refetch()} />;

  const s = data;
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-bold">{me?.display_name ?? "You"} · Dashboard</h1>
      </header>

      <div className="grid grid-cols-2 gap-2">
        <Stat label="Shortlisted" value={s.by_state.SHORTLISTED ?? 0} to="/review?states=SHORTLISTED" />
        <Stat label="LEAP moves" value={s.leaps} to="/review?states=SHORTLISTED" />
        <Stat label="Interested" value={s.interested} to="/review?states=AWAITING_REVIEW" />
        <Stat label="Bookmarked" value={s.bookmarked} to="/review?states=SHORTLISTED,SCORED" />
        <Stat label="Wrong match" value={s.wrong_match} />
        <Stat label="Rejected" value={s.by_state.REJECTED ?? 0} to="/review?states=REJECTED" />
      </div>

      <Link to="/diagnostics"
        className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-900">
        <span>Discovery · {relativeTime(s.last_discovery_at)}</span>
        <span className="text-slate-400">›</span>
      </Link>

      <div className="flex gap-2">
        <button onClick={() => rescore.mutate()} disabled={rescore.isPending}
          className="flex-1 rounded-md border border-slate-300 py-2 text-sm font-medium disabled:opacity-50">
          {rescore.isPending ? "Scoring…" : "⟳ Re-score"}
        </button>
        <button onClick={() => setShowAdd(true)}
          className="flex-1 rounded-md bg-blue-600 py-2 text-sm font-medium text-white">
          ➕ Add job
        </button>
      </div>

      <Banner tone="info">
        Scoring uses Ollama embeddings when available, otherwise a deterministic fallback — either
        way you keep getting ranked jobs.
      </Banner>

      {showAdd && <AddJobModal onClose={() => setShowAdd(false)} />}
    </div>
  );
}
