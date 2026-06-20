import { useState } from "react";
import { usePreferences, useSetPreference } from "../hooks/usePreferences";
import LoadingSkeleton from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import type { Preference } from "../lib/types";

const ORDER: Preference[] = ["PREFERRED", "AVOID", "BLOCKED", "NEUTRAL"];
const PILL: Record<Preference, string> = {
  PREFERRED: "bg-green-50 text-green-700 border-green-200",
  AVOID: "bg-amber-50 text-amber-700 border-amber-200",
  BLOCKED: "bg-red-50 text-red-700 border-red-200",
  NEUTRAL: "bg-slate-50 text-slate-600 border-slate-200",
};

export default function CompaniesPage() {
  const { data, isLoading, isError, refetch } = usePreferences();
  const setPref = useSetPreference();
  const [company, setCompany] = useState("");
  const [preference, setPreference] = useState<Preference>("BLOCKED");

  if (isLoading) return <LoadingSkeleton label="Loading preferences…" />;
  if (isError || !data) return <ErrorState onRetry={() => refetch()} />;

  const grouped = ORDER.map((p) => ({ p, rows: data.filter((d) => d.preference === p) })).filter(
    (g) => g.rows.length > 0,
  );

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold">Company preferences</h1>

      <div className="flex gap-2">
        <input
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          placeholder="company"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <select
          value={preference}
          onChange={(e) => setPreference(e.target.value as Preference)}
          className="rounded-md border border-slate-300 px-2 text-sm"
        >
          {ORDER.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <button
          disabled={!company.trim() || setPref.isPending}
          onClick={() => {
            setPref.mutate({ company: company.trim(), preference });
            setCompany("");
          }}
          className="rounded-md bg-slate-800 px-3 text-sm text-white disabled:opacity-50"
        >
          Save
        </button>
      </div>

      {grouped.length === 0 && <p className="text-sm text-slate-400">No preferences yet.</p>}
      {grouped.map((g) => (
        <section key={g.p}>
          <h2 className="mb-1 text-xs font-semibold uppercase text-slate-400">{g.p}</h2>
          <div className="flex flex-wrap gap-1.5">
            {g.rows.map((r) => (
              <span
                key={r.company}
                className={`rounded-full border px-2 py-0.5 text-xs ${PILL[g.p]}`}
                title={r.note || undefined}
              >
                {r.company}
              </span>
            ))}
          </div>
        </section>
      ))}
      <p className="text-xs text-slate-400">
        BLOCKED companies are hard-filtered before scoring; AVOID lowers the score; PREFERRED raises it.
      </p>
    </div>
  );
}
