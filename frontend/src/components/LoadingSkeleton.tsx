export default function LoadingSkeleton({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-10 text-slate-400">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-transparent" />
      <span className="text-sm">{label}</span>
    </div>
  );
}
