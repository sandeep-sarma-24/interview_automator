import { useOpsApiCalls } from "../hooks";
import { Card, QueryError, Spinner, relTime } from "../components/ui";

export default function OpsApiCalls() {
  const { data, isLoading, isError, error, refetch } = useOpsApiCalls(24);
  if (isLoading) return <Spinner label="Loading API calls…" />;
  if (isError || !data) return <QueryError error={error} onRetry={() => refetch()} />;

  return (
    <div className="space-y-5">
      <h1 className="text-lg font-bold">Outbound API Monitoring <span className="text-xs font-normal text-slate-400">· last {data.window_hours}h</span></h1>

      <Card title="By service">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-400">
            <tr><th className="py-1">Service</th><th className="text-right">Calls</th><th className="text-right">Failures</th><th className="text-right">p50</th><th className="text-right">p95</th><th className="text-right">Retries</th></tr>
          </thead>
          <tbody>
            {data.by_service.map((s) => (
              <tr key={s.service} className="border-t border-slate-100 dark:border-slate-800">
                <td className="py-1.5 font-medium">{s.service}</td>
                <td className="text-right tabular-nums">{s.calls}</td>
                <td className={`text-right tabular-nums ${s.failures > 0 ? "text-red-600" : "text-slate-400"}`}>{s.failures}</td>
                <td className="text-right tabular-nums text-slate-500">{s.p50_ms ?? "—"}ms</td>
                <td className="text-right tabular-nums text-slate-500">{s.p95_ms ?? "—"}ms</td>
                <td className="text-right tabular-nums text-slate-500">{s.retries}</td>
              </tr>
            ))}
            {data.by_service.length === 0 && <tr><td colSpan={6} className="py-2 text-slate-400">No calls in window.</td></tr>}
          </tbody>
        </table>
        <p className="mt-1 text-[11px] text-slate-400">p50/p95 are approximate (computed in-app; SQLite has no percentile).</p>
      </Card>

      <Card title="Recent failures">
        <div className="max-h-72 overflow-auto text-xs">
          {data.recent_failures.map((f, i) => (
            <div key={i} className="flex justify-between border-b border-slate-100 py-1 dark:border-slate-800">
              <span className="truncate">{f.service} <span className="text-slate-400">{f.host}{f.path}</span></span>
              <span className="ml-2 shrink-0 text-red-600">{f.status_code ?? f.error} · {relTime(f.ts)}</span>
            </div>
          ))}
          {data.recent_failures.length === 0 && <span className="text-slate-400">none 🎉</span>}
        </div>
      </Card>
    </div>
  );
}
