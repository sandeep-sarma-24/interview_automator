export default function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 p-10 text-center text-slate-500">
      <p className="text-base font-medium">{title}</p>
      {hint && <p className="max-w-xs text-sm text-slate-400">{hint}</p>}
      {action}
    </div>
  );
}
