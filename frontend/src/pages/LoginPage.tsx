import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../lib/apiClient";

export default function LoginPage() {
  const { token, login, createCandidate } = useAuth();
  const nav = useNavigate();
  const [tokenInput, setTokenInput] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (token) {
    nav("/", { replace: true });
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await createCandidate(name, email);
      nav("/onboarding", { replace: true });
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not create candidate");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-8 px-6">
      <header>
        <h1 className="text-xl font-bold">Job Copilot</h1>
        <p className="text-sm text-slate-500">Review your trajectory-ranked jobs.</p>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (tokenInput.trim()) {
            login(tokenInput.trim());
            nav("/", { replace: true });
          }
        }}
        className="space-y-2"
      >
        <label className="block text-sm font-medium">I have a token</label>
        <input
          value={tokenInput}
          onChange={(e) => setTokenInput(e.target.value)}
          placeholder="paste candidate token"
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <button className="w-full rounded-md bg-blue-600 py-2 text-sm font-medium text-white">
          Sign in
        </button>
      </form>

      <div className="flex items-center gap-3 text-xs text-slate-400">
        <hr className="flex-1 border-slate-200" /> or create a candidate{" "}
        <hr className="flex-1 border-slate-200" />
      </div>

      <form onSubmit={onCreate} className="space-y-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="display name"
          required
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email"
          type="email"
          required
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          disabled={busy}
          className="w-full rounded-md border border-slate-300 py-2 text-sm font-medium disabled:opacity-50"
        >
          Create & continue
        </button>
        {err && <p className="text-xs text-red-600">{err}</p>}
      </form>
    </div>
  );
}
