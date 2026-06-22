import { useOpsHealth } from "../hooks";
import { Card, Dot, Metric, QueryError, Spinner, relTime } from "../components/ui";

export default function OpsOverview() {
  const { data, isLoading, isError, error, refetch } = useOpsHealth();
  if (isLoading) return <Spinner label="Loading health…" />;
  if (isError || !data) return <QueryError error={error} onRetry={() => refetch()} />;

  const Row = ({ label, status, detail }: { label: string; status: string; detail: string }) => (
    <div className="flex items-center justify-between border-b border-slate-100 py-2 last:border-0 dark:border-slate-800">
      <span className="flex items-center gap-2 text-sm font-medium">
        <Dot status={status} /> {label}
      </span>
      <span className="text-xs text-slate-500">{detail}</span>
    </div>
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">System Health</h1>
        <span className="text-xs text-slate-400">auto-refresh 15s</span>
      </div>

      <Card title="Subsystems">
        <Row label="Database" status={data.db} detail={data.db} />
        <Row
          label="Worker"
          status={data.worker.status}
          detail={`${data.worker.status} · heartbeat ${data.worker.heartbeat_age_s == null ? "—" : Math.round(data.worker.heartbeat_age_s) + "s ago"}`}
        />
        <Row label="Ollama" status={data.ollama.status} detail={`${data.ollama.status} · ${data.ollama.mode}`} />
        <Row
          label="Discovery"
          status={data.discovery.broken > 0 ? "ERROR" : data.discovery.degraded > 0 ? "DEGRADED" : "HEALTHY"}
          detail={`${data.discovery.healthy}✓ ${data.discovery.degraded}~ ${data.discovery.broken}✗ boards`}
        />
      </Card>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Jobs" value={data.totals.jobs} />
        <Metric label="Active companies" value={data.totals.companies_active} />
        <Metric label="Disabled companies" value={data.totals.companies_disabled} />
        <Metric label="Last discovery" value={relTime(data.last_discovery_at)} />
      </div>

      <Card title="Recent">
        <div className="flex justify-between text-sm">
          <span>Last error</span>
          <span className={data.last_error_at ? "text-amber-600" : "text-slate-400"}>
            {relTime(data.last_error_at)}
          </span>
        </div>
      </Card>
    </div>
  );
}
