import { useDiagnostics } from "../hooks/useDiagnostics";
import { relativeTime } from "../lib/format";
import LoadingSkeleton from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import type { DiagnosticsSource } from "../lib/types";

const DOT: Record<string, string> = {
  OK: "bg-green-500",
  DEGRADED: "bg-amber-500",
  ERROR: "bg-red-500",
  IDLE: "bg-slate-400",
};

function SourceCard({ s }: { s: DiagnosticsSource }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 font-semibold">
          <span className={`h-2 w-2 rounded-full ${DOT[s.status] ?? "bg-slate-400"}`} />
          {s.source}
        </span>
        <span className="text-xs text-slate-400">{relativeTime(s.last_sync)}</span>
      </div>
      {s.type === "ATS" ? (
        <p className="mt-1 text-xs text-slate-500">
          {s.active_boards} boards · {s.healthy ?? 0}✓ {s.degraded ?? 0}~ {s.broken ?? 0}✗ ·
          discovered {s.jobs_discovered} · failed {s.jobs_failed}
        </p>
      ) : (
        <p className="mt-1 text-xs text-slate-500">discovered {s.jobs_discovered}</p>
      )}
    </div>
  );
}

export default function DiagnosticsPage() {
  const { data, isLoading, isError, refetch } = useDiagnostics();
  if (isLoading) return <LoadingSkeleton label="Loading diagnostics…" />;
  if (isError || !data) return <ErrorState onRetry={() => refetch()} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">Discovery Diagnostics</h1>
        <button onClick={() => refetch()} className="text-sm text-blue-600">
          ⟳ Refresh
        </button>
      </div>

      <div className="space-y-2">
        {data.sources.map((s) => (
          <SourceCard key={s.source} s={s} />
        ))}
      </div>

      <div className="rounded-lg bg-slate-100 p-3 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
        {data.totals.companies_active} active · {data.totals.companies_disabled} disabled ·{" "}
        {data.totals.jobs_total} jobs total
      </div>

      <section>
        <h2 className="mb-1 text-sm font-semibold text-slate-600">Recent runs</h2>
        <div className="overflow-hidden rounded-lg border border-slate-200 text-xs dark:border-slate-800">
          {data.recent_runs.length === 0 && (
            <p className="p-3 text-slate-400">No ATS runs yet — seed companies and run discovery.</p>
          )}
          {data.recent_runs.map((r, i) => (
            <div
              key={i}
              className="flex items-center justify-between border-b border-slate-100 px-3 py-1.5 last:border-0 dark:border-slate-800"
            >
              <span className="truncate">
                {r.company} <span className="text-slate-400">· {r.platform}</span>
              </span>
              <span className={r.status === "ERROR" ? "text-red-600" : "text-slate-500"}>
                {r.status === "ERROR" ? r.error || "error" : `+${r.jobs_new} / dropped ${r.jobs_dropped}`}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
