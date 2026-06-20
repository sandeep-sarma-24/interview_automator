import { useVerdict } from "../../hooks/useVerdict";
import type { Verdict } from "../../lib/types";

const ACTIONS: { verdict: Verdict; icon: string; label: string; cls: string }[] = [
  { verdict: "INTERESTED", icon: "👍", label: "Interested", cls: "border-green-300 text-green-700" },
  { verdict: "NOT_INTERESTED", icon: "👎", label: "Not", cls: "border-slate-300 text-slate-600" },
  { verdict: "BOOKMARK", icon: "🔖", label: "Bookmark", cls: "border-blue-300 text-blue-700" },
  { verdict: "WRONG_MATCH", icon: "⚠", label: "Wrong match", cls: "border-amber-300 text-amber-700" },
];

export default function VerdictButtons({
  applicationId,
  current,
  compact = false,
  note,
}: {
  applicationId: number;
  current: Verdict | null;
  compact?: boolean;
  note?: string;
}) {
  const verdict = useVerdict();

  return (
    <div className="flex flex-wrap gap-1.5">
      {ACTIONS.map((a) => {
        const active = current === a.verdict;
        return (
          <button
            key={a.verdict}
            disabled={verdict.isPending}
            onClick={() =>
              verdict.mutate({ applicationId, verdict: a.verdict, note })
            }
            className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium transition disabled:opacity-50 ${
              active ? "ring-2 ring-offset-1 " + a.cls : a.cls
            } hover:bg-slate-50`}
            aria-pressed={active}
            title={a.label}
          >
            <span>{a.icon}</span>
            {!compact && <span>{a.label}</span>}
          </button>
        );
      })}
    </div>
  );
}
