export default function ConfidenceDots({ confidence }: { confidence: number | null }) {
  const filled = confidence == null ? 0 : Math.round(confidence * 4);
  return (
    <span className="inline-flex items-center gap-0.5" title={`confidence ${confidence ?? "—"}`}>
      {[0, 1, 2, 3].map((i) => (
        <span
          key={i}
          className={`h-1.5 w-1.5 rounded-full ${i < filled ? "bg-slate-600" : "bg-slate-300"}`}
        />
      ))}
    </span>
  );
}
