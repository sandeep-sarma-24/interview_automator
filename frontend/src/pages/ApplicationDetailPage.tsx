import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useApplication } from "../hooks/useApplication";
import LoadingSkeleton from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import TrajectoryBadge from "../components/job/TrajectoryBadge";
import ScoreBar from "../components/job/ScoreBar";
import ConfidenceDots from "../components/job/ConfidenceDots";
import VerdictButtons from "../components/job/VerdictButtons";

const SIGN: Record<string, "+" | "−" | "~"> = { POSITIVE: "+", NEGATIVE: "−", NEUTRAL: "~" };
const SIGN_CLS: Record<string, string> = {
  POSITIVE: "text-green-700",
  NEGATIVE: "text-red-700",
  NEUTRAL: "text-amber-700",
};

export default function ApplicationDetailPage() {
  const { applicationId } = useParams();
  const id = Number(applicationId);
  const { data, isLoading, isError, refetch } = useApplication(id);
  const [note, setNote] = useState("");

  if (isLoading) return <LoadingSkeleton label="Loading…" />;
  if (isError || !data) return <ErrorState onRetry={() => refetch()} />;

  const where = data.is_remote === 1 ? "Remote" : data.location || "—";

  return (
    <div className="space-y-4">
      <Link to="/review" className="text-sm text-blue-600">
        ‹ Back to review
      </Link>

      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <TrajectoryBadge direction={data.trajectory_direction} />
          <span className="text-xs text-slate-500">{where}</span>
          {data.source_url && (
            <a href={data.source_url} target="_blank" rel="noreferrer" className="text-xs text-blue-600">
              🔗 JD
            </a>
          )}
        </div>
        <p className="text-xs text-slate-500">{data.company}</p>
        <h1 className="text-lg font-bold leading-snug">{data.title}</h1>
        <div className="flex items-center gap-3 pt-1">
          <ScoreBar score={data.total_score} />
          <ConfidenceDots confidence={data.confidence} />
          {data.signal_density === "THIN" && (
            <span className="text-xs text-amber-600">limited info</span>
          )}
        </div>
      </header>

      <section>
        <h2 className="mb-1 text-sm font-semibold text-slate-600">Why this score</h2>
        <ul className="space-y-1">
          {data.signals.map((s, i) => (
            <li key={i} className="text-sm">
              <span className={`font-bold ${SIGN_CLS[s.direction]}`}>{SIGN[s.direction]} </span>
              {s.label}
              {s.detail && <span className="text-slate-400"> — {s.detail}</span>}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg bg-slate-100 p-3 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
        <p>State: {data.current_state}{data.reason_code ? ` (${data.reason_code})` : ""}</p>
        <p>Model: {data.scoring_model_version ?? "—"}</p>
        {data.verdict && <p>Your verdict: {data.verdict}{data.verdict_note ? ` — "${data.verdict_note}"` : ""}</p>}
      </section>

      <section className="space-y-2">
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="optional note (saved with your verdict)"
          rows={2}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <VerdictButtons applicationId={id} current={data.verdict} note={note || undefined} />
      </section>
    </div>
  );
}
