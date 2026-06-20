import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useProfile } from "../hooks/useProfile";
import LoadingSkeleton from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";

export default function YouPage() {
  const { token, logout } = useAuth();
  const { data, isLoading, isError, refetch } = useProfile();

  if (isLoading) return <LoadingSkeleton label="Loading profile…" />;
  if (isError || !data) return <ErrorState onRetry={() => refetch()} />;

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold">You</h1>

      <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-900">
        <p className="font-medium">{data.display_name}</p>
        <p className="text-slate-500">{data.email}</p>
        <p className="mt-1 text-xs text-slate-400">
          Profile v{data.profile_version_no ?? "—"} · {data.resumes.length} resume(s)
        </p>
      </div>

      <section>
        <h2 className="mb-1 text-xs font-semibold uppercase text-slate-400">Resumes</h2>
        {data.resumes.length === 0 ? (
          <p className="text-sm text-slate-400">None yet.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {data.resumes.map((r) => (
              <li key={r.label} className="flex justify-between rounded-md border border-slate-200 px-3 py-1.5 dark:border-slate-800">
                <span>{r.label}</span>
                <span className="text-slate-400">{r.target_role || "—"}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="space-y-2">
        <Link to="/onboarding" className="block rounded-md border border-slate-300 py-2 text-center text-sm font-medium">
          Edit trajectory profile
        </Link>
        <Link to="/diagnostics" className="block rounded-md border border-slate-300 py-2 text-center text-sm font-medium">
          Discovery diagnostics
        </Link>
        <button
          onClick={() => token && navigator.clipboard?.writeText(token)}
          className="block w-full rounded-md border border-slate-300 py-2 text-center text-sm"
        >
          Copy my token
        </button>
        <button
          onClick={logout}
          className="block w-full rounded-md border border-red-300 py-2 text-center text-sm font-medium text-red-600"
        >
          Log out / switch candidate
        </button>
      </div>
    </div>
  );
}
