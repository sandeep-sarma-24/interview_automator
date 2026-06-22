import { useState } from "react";
import { useOpsExplain } from "../hooks";
import { Card, QueryError, Spinner } from "../components/ui";

const SIGN: Record<string, string> = { POSITIVE: "+", NEGATIVE: "−", NEUTRAL: "~" };

export default function OpsExplain() {
  const [input, setInput] = useState("");
  const [id, setId] = useState<number | null>(null);
  const q = useOpsExplain(id);

  return (
    <div className="space-y-5">
      <h1 className="text-lg font-bold">Score Inspector</h1>

      <form
        onSubmit={(e) => { e.preventDefault(); const n = Number(input); if (n) setId(n); }}
        className="flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="application id"
          className="w-40 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
        />
        <button className="rounded-md bg-slate-800 px-3 py-1.5 text-sm text-white">Inspect</button>
      </form>

      {id != null && (q.isLoading ? <Spinner /> : q.isError ? <QueryError error={q.error} /> : q.data && (
        <>
          <Card>
            <p className="text-xs text-slate-500">{q.data.company} · candidate #{q.data.candidate_id} · {q.data.current_state}{q.data.reason_code ? ` (${q.data.reason_code})` : ""}</p>
            <h2 className="text-base font-semibold">{q.data.title}</h2>
            <p className="mt-1 text-sm">
              Direction <b>{q.data.explain.trajectory_direction ?? "—"}</b> · final{" "}
              <b>{q.data.explain.final_score == null ? "—" : Math.round(q.data.explain.final_score * 100)}</b> ·
              model {q.data.explain.scoring_model_version}
            </p>
          </Card>

          <Card title="Dimension breakdown (score × weight = contribution)">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-slate-400">
                <tr><th className="py-1">Dimension</th><th className="text-right">Score</th><th className="text-right">Weight</th><th className="text-right">Contribution</th></tr>
              </thead>
              <tbody>
                {Object.entries(q.data.explain.dimensions).map(([k, d]) => (
                  <tr key={k} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="py-1 capitalize">{k}</td>
                    <td className="text-right tabular-nums">{d.score?.toFixed(2) ?? "—"}</td>
                    <td className="text-right tabular-nums text-slate-500">{d.weight}</td>
                    <td className="text-right tabular-nums font-medium">{d.contribution.toFixed(3)}</td>
                  </tr>
                ))}
                <tr className="border-t border-slate-200 dark:border-slate-700">
                  <td className="py-1 font-medium">weighted sum</td><td /><td />
                  <td className="text-right tabular-nums font-medium">{q.data.explain.weighted_sum.toFixed(3)}</td>
                </tr>
                <tr>
                  <td className="text-slate-500">company adjust</td><td /><td />
                  <td className="text-right tabular-nums text-slate-500">{q.data.explain.company_adjust ?? 0}</td>
                </tr>
                <tr>
                  <td className="font-bold">final</td><td /><td />
                  <td className="text-right tabular-nums font-bold">{q.data.explain.final_score?.toFixed(3) ?? "—"}</td>
                </tr>
              </tbody>
            </table>
            <p className="mt-1 text-[11px] text-slate-400">confidence {q.data.explain.confidence ?? "—"} · density {q.data.explain.signal_density ?? "—"} · embed_sim {q.data.explain.embed_sim ?? "—"}</p>
          </Card>

          <Card title="Signals">
            <ul className="space-y-0.5 text-sm">
              {q.data.signals.map((s, i) => (
                <li key={i}>
                  <b>{SIGN[s.direction]}</b> {s.label}
                  {s.detail && <span className="text-slate-400"> — {s.detail}</span>}
                </li>
              ))}
            </ul>
          </Card>
        </>
      ))}
    </div>
  );
}
