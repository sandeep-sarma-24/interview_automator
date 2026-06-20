import type { TrajectoryDirection } from "../../lib/types";

const STYLES: Record<TrajectoryDirection, string> = {
  LEAP: "bg-green-100 text-green-800 border-green-300",
  FORWARD: "bg-blue-100 text-blue-800 border-blue-300",
  LATERAL: "bg-slate-100 text-slate-700 border-slate-300",
  STALL: "bg-yellow-100 text-yellow-800 border-yellow-300",
  BACKWARD: "bg-red-100 text-red-800 border-red-300",
};

export default function TrajectoryBadge({ direction }: { direction: TrajectoryDirection | null }) {
  if (!direction) return null;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${STYLES[direction]}`}
    >
      {direction}
    </span>
  );
}
