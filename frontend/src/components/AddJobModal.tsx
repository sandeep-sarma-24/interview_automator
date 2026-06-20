import { useState } from "react";
import { useManualAdd } from "../hooks/useManualAdd";

export default function AddJobModal({ onClose }: { onClose: () => void }) {
  const [url, setUrl] = useState("");
  const add = useManualAdd();

  return (
    <div
      className="fixed inset-0 z-20 flex items-end justify-center bg-black/40 p-4 sm:items-center"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl bg-white p-4 shadow-lg dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold">Add a job by URL</h2>
        <p className="mt-1 text-xs text-slate-500">
          Paste a posting you found (Reddit, X, referral). It'll be scored on the next run.
        </p>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://…"
          className="mt-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        {add.isError && <p className="mt-1 text-xs text-red-600">Could not add that URL.</p>}
        {add.isSuccess && <p className="mt-1 text-xs text-green-600">Added — re-score to rank it.</p>}
        <div className="mt-3 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-md px-3 py-1.5 text-sm">
            Close
          </button>
          <button
            disabled={!url.trim() || add.isPending}
            onClick={() => add.mutate(url.trim())}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
