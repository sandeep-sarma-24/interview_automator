import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useOpsAuth } from "../OpsAuthContext";

export default function OpsLogin() {
  const { token, login } = useOpsAuth();
  const nav = useNavigate();
  const [val, setVal] = useState("");
  if (token) nav("/ops", { replace: true });

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-4 px-6">
      <header>
        <h1 className="text-lg font-bold">⚙ Operator Dashboard</h1>
        <p className="text-sm text-slate-500">Enter the operator token (SCRAPER_OPS_TOKEN).</p>
      </header>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (val.trim()) {
            login(val.trim());
            nav("/ops", { replace: true });
          }
        }}
        className="space-y-2"
      >
        <input
          type="password"
          value={val}
          onChange={(e) => setVal(e.target.value)}
          placeholder="operator token"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <button className="w-full rounded-md bg-slate-800 py-2 text-sm font-medium text-white">
          Enter
        </button>
      </form>
      <p className="text-xs text-slate-400">
        This is for system operators, not candidates. If it returns "disabled", set
        <code className="mx-1">SCRAPER_OPS_TOKEN</code> in the API environment.
      </p>
    </div>
  );
}
