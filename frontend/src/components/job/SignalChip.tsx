type Sign = "+" | "−" | "~";

// Color AND glyph (never color alone) — accessibility.
const STYLE: Record<Sign, string> = {
  "+": "bg-green-50 text-green-700 border-green-200",
  "−": "bg-red-50 text-red-700 border-red-200",
  "~": "bg-amber-50 text-amber-700 border-amber-200",
};

export default function SignalChip({ sign, text }: { sign: Sign; text: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs ${STYLE[sign]}`}
    >
      <span className="font-bold">{sign}</span>
      {text}
    </span>
  );
}
