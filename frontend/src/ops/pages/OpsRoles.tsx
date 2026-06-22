import { useState } from "react";
import { useAddAlias, useRoleMethods, useRoleUnresolved } from "../hooks";
import { Card, Metric, QueryError, Spinner } from "../components/ui";

// The 8 canonical roles (fixed taxonomy). Update here if the taxonomy changes.
const CANONICAL_KEYS = [
  "software_engineer_generic", "backend_engineer", "full_stack_engineer", "data_engineer",
  "ml_engineer", "ai_engineer", "ai_product_engineer", "program_project_manager",
];

export default function OpsRoles() {
  const methods = useRoleMethods();
  const unresolved = useRoleUnresolved();
  const addAlias = useAddAlias();
  const [choice, setChoice] = useState<Record<string, string>>({});

  if (methods.isLoading) return <Spinner label="Loading role metrics…" />;
  if (methods.isError) return <QueryError error={methods.error} onRetry={() => methods.refetch()} />;

  const m = methods.data!;
  return (
    <div className="space-y-5">
      <h1 className="text-lg font-bold">Role Resolution</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Coverage" value={`${m.coverage_pct}%`} hint="ALIAS+EMBEDDING / total" />
        <Metric label="ALIAS" value={m.counts.ALIAS ?? 0} />
        <Metric label="EMBEDDING" value={m.counts.EMBEDDING ?? 0} />
        <Metric label="UNRESOLVED" value={m.counts.UNRESOLVED ?? 0} />
      </div>

      <Card title="Unresolved titles — teach a LEARNED alias">
        {unresolved.isLoading ? (
          <Spinner />
        ) : (
          <div className="max-h-[28rem] space-y-1 overflow-auto">
            {(unresolved.data?.items ?? []).map((u, i) => (
              <div key={i} className="flex items-center gap-2 border-b border-slate-100 py-1.5 text-sm dark:border-slate-800">
                <span className="flex-1 truncate">{u.normalized_title}</span>
                <select
                  value={choice[u.normalized_title] ?? ""}
                  onChange={(e) => setChoice({ ...choice, [u.normalized_title]: e.target.value })}
                  className="rounded border border-slate-300 px-1 py-0.5 text-xs"
                >
                  <option value="">map to…</option>
                  {CANONICAL_KEYS.map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
                <button
                  disabled={!choice[u.normalized_title] || addAlias.isPending}
                  onClick={() =>
                    addAlias.mutate({ title: u.normalized_title, canonical_key: choice[u.normalized_title] })
                  }
                  className="rounded bg-slate-800 px-2 py-0.5 text-xs text-white disabled:opacity-40"
                >
                  Add
                </button>
              </div>
            ))}
            {(unresolved.data?.items ?? []).length === 0 && (
              <p className="text-sm text-slate-400">No unresolved titles — run discover/resolve-titles.</p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
