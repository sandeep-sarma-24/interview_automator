import { useOpsWorker } from "../hooks";
import { Card, Dot, Metric, QueryError, Spinner, relTime } from "../components/ui";

export default function OpsWorker() {
  const { data, isLoading, isError, error, refetch } = useOpsWorker();
  if (isLoading) return <Spinner label="Loading worker…" />;
  if (isError || !data) return <QueryError error={error} onRetry={() => refetch()} />;

  return (
    <div className="space-y-5">
      <h1 className="text-lg font-bold">Worker Monitoring</h1>

      <Card>
        <div className="flex items-center gap-3">
          <Dot status={data.status} />
          <span className="text-sm font-medium">{data.status}</span>
          <span className="text-xs text-slate-500">
            heartbeat {data.heartbeat_age_s == null ? "—" : Math.round(data.heartbeat_age_s) + "s ago"}
          </span>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Unscored jobs (backlog)" value={data.backlogs.unscored_jobs} />
        {Object.entries(data.backlogs.by_state).slice(0, 3).map(([k, v]) => (
          <Metric key={k} label={k} value={v} />
        ))}
      </div>

      <Card title="Recent cycles (last 20)">
        <table className="w-full text-xs">
          <thead className="text-left text-slate-400">
            <tr><th className="py-1">When</th><th>Status</th><th>Duration</th><th>Detail</th></tr>
          </thead>
          <tbody>
            {data.recent_cycles.map((c, i) => (
              <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                <td className="py-1 text-slate-500">{relTime(c.ts)}</td>
                <td>{c.level === "ERROR" ? <span className="text-red-600">ERROR</span> : "ok"}</td>
                <td className="text-slate-500">{c.duration_ms != null ? `${(c.duration_ms / 1000).toFixed(1)}s` : "—"}</td>
                <td className="text-slate-500">
                  {Object.entries(c.metadata || {}).map(([k, v]) => `${k}=${String(v)}`).join(" ")}
                </td>
              </tr>
            ))}
            {data.recent_cycles.length === 0 && (
              <tr><td colSpan={4} className="py-2 text-slate-400">No cycles yet — start the worker.</td></tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
