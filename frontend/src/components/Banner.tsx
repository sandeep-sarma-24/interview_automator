type Tone = "info" | "warn" | "error";

const TONES: Record<Tone, string> = {
  info: "bg-blue-50 text-blue-800 border-blue-200",
  warn: "bg-amber-50 text-amber-800 border-amber-200",
  error: "bg-red-50 text-red-800 border-red-200",
};

export default function Banner({ tone = "info", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <div className={`rounded-md border px-3 py-2 text-sm ${TONES[tone]}`}>{children}</div>
  );
}
