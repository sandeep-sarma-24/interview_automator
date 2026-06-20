import { scorePct } from "../../lib/format";

export default function ScoreBar({ score }: { score: number | null }) {
  const pct = score == null ? 0 : Math.round(score * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div className="h-full rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-semibold tabular-nums">{scorePct(score)}</span>
    </div>
  );
}
