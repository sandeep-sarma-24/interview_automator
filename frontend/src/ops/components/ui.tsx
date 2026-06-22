// Small shared primitives for the operator dashboard (dense, desktop-oriented).
import type { OpsError } from "../opsClient";

const STATUS_DOT: Record<string, string> = {
  ok: "bg-green-500", up: "bg-green-500", RUNNING: "bg-green-500", HEALTHY: "bg-green-500",
  degraded: "bg-amber-500", DEGRADED: "bg-amber-500", IDLE: "bg-slate-400", STALE: "bg-amber-500",
  down: "bg-red-500", ERROR: "bg-red-500", BROKEN: "bg-red-500", unknown: "bg-slate-400",
};

export function Dot({ status }: { status: string }) {
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${STATUS_DOT[status] ?? "bg-slate-400"}`} />;
}

export function Card({ title, children, right }: { title?: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      {title && (
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-600 dark:text-slate-300">{title}</h2>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Metric({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="rounded-md border border-slate-200 p-3 dark:border-slate-800">
      <p className="text-2xl font-bold tabular-nums">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
      {hint && <p className="text-[11px] text-slate-400">{hint}</p>}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-6 text-sm text-slate-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-transparent" />
      {label}
    </div>
  );
}

export function QueryError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error as OpsError;
  const disabled = e?.status === 503;
  return (
    <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      <p className="font-medium">{disabled ? "Operator endpoints are disabled" : "Request failed"}</p>
      <p className="text-xs">{e?.message ?? "error"}</p>
      {disabled && <p className="mt-1 text-xs">Set <code>SCRAPER_OPS_TOKEN</code> in the API environment to enable.</p>}
      {onRetry && !disabled && (
        <button onClick={onRetry} className="mt-2 rounded border border-red-300 px-2 py-1 text-xs">Retry</button>
      )}
    </div>
  );
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)}m ago`;
  if (s < 129600) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}
