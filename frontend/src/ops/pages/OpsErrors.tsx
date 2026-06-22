import { useState } from "react";
import { useOpsErrors } from "../hooks";
import { Card, QueryError, Spinner, relTime } from "../components/ui";

export default function OpsErrors() {
  const { data, isLoading, isError, error, refetch } = useOpsErrors();
  const [open, setOpen] = useState<number | null>(null);
  if (isLoading) return <Spinner label="Loading errors…" />;
  if (isError || !data) return <QueryError error={error} onRetry={() => refetch()} />;

  return (
    <div className="space-y-5">
      <h1 className="text-lg font-bold">Error Monitoring</h1>
      <Card title={`Grouped errors (${data.groups.length})`}>
        {data.groups.length === 0 && <p className="text-sm text-slate-400">No errors recorded. 🎉</p>}
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {data.groups.map((g, i) => (
            <div key={i} className="py-2">
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="flex w-full items-center justify-between text-left text-sm"
              >
                <span>
                  <span className="mr-2 rounded bg-red-100 px-1.5 text-xs font-bold text-red-700">×{g.count}</span>
                  <b>{g.error_type}</b>
                  <span className="ml-2 text-slate-500">{g.category}{g.source ? `/${g.source}` : ""}</span>
                </span>
                <span className="text-xs text-slate-400">{relTime(g.last_seen)}</span>
              </button>
              {open === i && (
                <div className="mt-2 space-y-1">
                  <p className="text-xs text-slate-600 dark:text-slate-300">{g.message}</p>
                  <pre className="max-h-64 overflow-auto rounded bg-slate-900 p-2 text-[11px] leading-snug text-slate-200">
                    {g.stack_trace}
                  </pre>
                  <p className="text-[11px] text-slate-400">first {relTime(g.first_seen)} · last {relTime(g.last_seen)}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
