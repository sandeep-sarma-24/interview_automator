import { useState } from "react";
import { useOpsDiscovery, useOpsDrops } from "../hooks";
import { Card, Dot, QueryError, Spinner, relTime } from "../components/ui";

export default function OpsDiscovery() {
  const { data, isLoading, isError, error, refetch } = useOpsDiscovery();
  const [reason, setReason] = useState<string>("");
  const drops = useOpsDrops(reason || undefined);

  if (isLoading) return <Spinner label="Loading discovery…" />;
  if (isError || !data) return <QueryError error={error} onRetry={() => refetch()} />;

  return (
    <div className="space-y-5">
      <h1 className="text-lg font-bold">Discovery Monitoring</h1>

      <Card title="Sources">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-400">
            <tr><th className="py-1">Source</th><th>Status</th><th>Last run</th><th>Boards</th><th className="text-right">New</th><th className="text-right">Dropped</th></tr>
          </thead>
          <tbody>
            {data.sources.map((s) => (
              <tr key={s.source} className="border-t border-slate-100 dark:border-slate-800">
                <td className="py-1.5 font-medium">{s.source}</td>
                <td><span className="flex items-center gap-1.5"><Dot status={s.status} />{s.status}</span></td>
                <td className="text-slate-500">{relTime(s.last_run)}</td>
                <td className="text-slate-500">{s.active_boards ?? "—"}</td>
                <td className="text-right tabular-nums">{s.jobs_new}</td>
                <td className="text-right tabular-nums text-slate-500">{s.jobs_dropped}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Rejection reasons (retained window)">
        <div className="flex flex-wrap gap-2">
          {Object.entries(data.rejection_reasons).length === 0 && <span className="text-sm text-slate-400">none</span>}
          {Object.entries(data.rejection_reasons).map(([r, n]) => (
            <span key={r} className="rounded-full border border-slate-300 px-2 py-0.5 text-xs">
              {r} · <b>{n}</b>
            </span>
          ))}
        </div>
      </Card>

      {data.failing_boards.length > 0 && (
        <Card title="Failing boards">
          <ul className="space-y-1 text-sm">
            {data.failing_boards.map((b, i) => (
              <li key={i} className="flex justify-between">
                <span>{b.company} <span className="text-slate-400">({b.token})</span></span>
                <span className="text-red-600">{b.reason}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card
        title="Drop inspection"
        right={
          <select value={reason} onChange={(e) => setReason(e.target.value)} className="rounded border border-slate-300 px-2 py-0.5 text-xs">
            <option value="">all reasons</option>
            {["ROLE_FILTER_DROP", "NOT_REMOTE", "BLOCKED_COMPANY", "SENIORITY", "DUPLICATE", "LOCATION"].map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        }
      >
        {drops.isLoading ? (
          <Spinner />
        ) : (
          <>
            <p className="mb-2 text-xs text-slate-400">{drops.data?.total ?? 0} total</p>
            <div className="max-h-80 overflow-auto text-xs">
              {(drops.data?.items ?? []).map((d, i) => (
                <div key={i} className="flex items-center justify-between border-b border-slate-100 py-1 dark:border-slate-800">
                  <span className="truncate">{d.company} <span className="text-slate-400">· {d.title}</span></span>
                  <span className="ml-2 shrink-0 text-slate-500">{d.reason}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </Card>

      <Card title="Recent ATS runs">
        <div className="max-h-64 overflow-auto text-xs">
          {data.recent_runs.map((r, i) => (
            <div key={i} className="flex justify-between border-b border-slate-100 py-1 dark:border-slate-800">
              <span>{r.company} <span className="text-slate-400">· {r.platform}</span></span>
              <span className={r.status === "ERROR" ? "text-red-600" : "text-slate-500"}>
                {r.status === "ERROR" ? r.error || "error" : `+${r.jobs_new} / drop ${r.jobs_dropped}`}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
