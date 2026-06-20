import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useFeed } from "../hooks/useFeed";
import JobCard from "../components/job/JobCard";
import LoadingSkeleton from "../components/LoadingSkeleton";
import ErrorState from "../components/ErrorState";
import EmptyState from "../components/EmptyState";
import AddJobModal from "../components/AddJobModal";

const LIMIT = 25;
const PRESETS: { label: string; states: string }[] = [
  { label: "Shortlisted", states: "SHORTLISTED" },
  { label: "All scored", states: "SHORTLISTED,SCORED" },
  { label: "Interested", states: "AWAITING_REVIEW" },
  { label: "Rejected", states: "REJECTED" },
];

export default function ReviewPage() {
  const [params, setParams] = useSearchParams();
  const states = params.get("states") || "SHORTLISTED";
  const search = params.get("search") || "";
  const offset = Number(params.get("offset") || 0);
  const [showAdd, setShowAdd] = useState(false);

  const { data, isLoading, isError, refetch, isFetching } = useFeed({
    states,
    search,
    limit: LIMIT,
    offset,
  });

  function update(next: Record<string, string>) {
    const p = new URLSearchParams(params);
    Object.entries(next).forEach(([k, v]) => (v ? p.set(k, v) : p.delete(k)));
    if (!("offset" in next)) p.set("offset", "0"); // reset page on filter/search change
    setParams(p);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">Review</h1>
        <button onClick={() => setShowAdd(true)} className="text-sm text-blue-600">
          ➕ Add
        </button>
      </div>

      <input
        defaultValue={search}
        onKeyDown={(e) => e.key === "Enter" && update({ search: (e.target as HTMLInputElement).value })}
        placeholder="search company or title (Enter)"
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
      />

      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {PRESETS.map((p) => (
          <button
            key={p.states}
            onClick={() => update({ states: p.states })}
            className={`whitespace-nowrap rounded-full border px-3 py-1 text-xs ${
              states === p.states ? "border-blue-500 bg-blue-50 text-blue-700" : "border-slate-300"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingSkeleton label="Loading jobs…" />
      ) : isError || !data ? (
        <ErrorState onRetry={() => refetch()} />
      ) : data.items.length === 0 ? (
        <EmptyState
          title="No jobs here yet"
          hint="Run discovery + re-score, or add a job by URL. Blocked/filtered jobs won't appear."
        />
      ) : (
        <>
          <p className="text-xs text-slate-400">
            {data.total} total {isFetching && "· refreshing…"}
          </p>
          <div className="space-y-2">
            {data.items.map((item) => (
              <JobCard key={item.application_id} item={item} />
            ))}
          </div>
          <div className="flex items-center justify-between pt-2">
            <button
              disabled={offset === 0}
              onClick={() => update({ offset: String(Math.max(0, offset - LIMIT)) })}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40"
            >
              ‹ Prev
            </button>
            <span className="text-xs text-slate-400">
              {offset + 1}–{Math.min(offset + LIMIT, data.total)} of {data.total}
            </span>
            <button
              disabled={offset + LIMIT >= data.total}
              onClick={() => update({ offset: String(offset + LIMIT) })}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Next ›
            </button>
          </div>
        </>
      )}

      {showAdd && <AddJobModal onClose={() => setShowAdd(false)} />}
    </div>
  );
}
