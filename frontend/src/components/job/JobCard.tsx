import { Link } from "react-router-dom";
import type { FeedItem } from "../../lib/types";
import { parseExplanation } from "../../lib/format";
import TrajectoryBadge from "./TrajectoryBadge";
import ScoreBar from "./ScoreBar";
import SignalChip from "./SignalChip";
import ConfidenceDots from "./ConfidenceDots";
import VerdictButtons from "./VerdictButtons";

export default function JobCard({ item }: { item: FeedItem }) {
  const signals = parseExplanation(item.explanation_summary).slice(0, 3);
  const where = item.is_remote === 1 ? "Remote" : item.location || "—";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between">
        <TrajectoryBadge direction={item.trajectory_direction} />
        <ScoreBar score={item.total_score} />
      </div>

      <Link to={`/review/${item.application_id}`} className="mt-2 block">
        <p className="text-xs text-slate-500">
          {item.company} · {where}
          {item.signal_density === "THIN" && " · limited info"}
        </p>
        <p className="font-semibold leading-snug">{item.title}</p>
      </Link>

      <div className="mt-2 flex flex-wrap gap-1">
        {signals.map((s, i) => (
          <SignalChip key={i} sign={s.sign} text={s.text} />
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <ConfidenceDots confidence={item.confidence} />
        <VerdictButtons applicationId={item.application_id} current={item.verdict} compact />
      </div>
    </div>
  );
}
