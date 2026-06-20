import { useState } from "react";
import { useNavigate } from "react-router-dom";
import TagInput from "../components/forms/TagInput";
import Banner from "../components/Banner";
import { useSaveProfile, useSaveResume } from "../hooks/useOnboarding";
import { useSetPreference } from "../hooks/usePreferences";
import type { Preference, TrajectorySpec } from "../lib/types";

const EMPTY: TrajectorySpec = {
  total_experience_months: 0,
  core_skills: [],
  acquiring_skills: [],
  target_roles: [],
  acceptable_roles: [],
  avoid_roles: [],
  target_domain_signals: [],
  cities: [],
  remote_required: false,
  current_ctc: null,
  salary_min_multiplier: 1.3,
  salary_target_multiplier: 1.7,
  salary_stretch_multiplier: 2.5,
};

export default function OnboardingWizard() {
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [spec, setSpec] = useState<TrajectorySpec>(EMPTY);
  const [resume, setResume] = useState({ label: "Primary", target_role: "", content_text: "" });
  const [pref, setPref] = useState<{ company: string; preference: Preference }>({
    company: "",
    preference: "BLOCKED",
  });

  const saveProfile = useSaveProfile();
  const saveResume = useSaveResume();
  const setPreference = useSetPreference();
  const [err, setErr] = useState<string | null>(null);

  const patch = (p: Partial<TrajectorySpec>) => setSpec((s) => ({ ...s, ...p }));

  async function finish() {
    setErr(null);
    try {
      await saveProfile.mutateAsync(spec);
      if (resume.content_text.trim()) await saveResume.mutateAsync(resume);
      nav("/", { replace: true });
    } catch {
      setErr("Could not save profile. Check your inputs and try again.");
    }
  }

  return (
    <div className="mx-auto min-h-screen max-w-md px-4 py-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-bold">Set up your profile</h1>
        <span className="text-xs text-slate-400">Step {step + 1} / 4</span>
      </div>

      {step === 0 && (
        <section className="space-y-4">
          <p className="text-sm text-slate-500">Where are you headed? This drives every ranking.</p>
          <TagInput label="Target roles (ranked)" value={spec.target_roles}
            onChange={(v) => patch({ target_roles: v })} placeholder="ai product engineer" />
          <TagInput label="Roles to avoid" value={spec.avoid_roles}
            onChange={(v) => patch({ avoid_roles: v })} placeholder="qa, sales" />
          <TagInput label="Target domain signals" value={spec.target_domain_signals}
            onChange={(v) => patch({ target_domain_signals: v })} placeholder="llm, rag, ai" />
          <TagInput label="Core skills (you have)" value={spec.core_skills}
            onChange={(v) => patch({ core_skills: v })} placeholder="python, backend" />
          <TagInput label="Acquiring skills (you want)" value={spec.acquiring_skills}
            onChange={(v) => patch({ acquiring_skills: v })} placeholder="ml, ai" />
        </section>
      )}

      {step === 1 && (
        <section className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium">Total experience (months)</span>
            <input type="number" min={0} value={spec.total_experience_months}
              onChange={(e) => patch({ total_experience_months: Number(e.target.value) })}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={spec.remote_required}
              onChange={(e) => patch({ remote_required: e.target.checked })} />
            Remote required
          </label>
          <TagInput label="Preferred cities" value={spec.cities}
            onChange={(v) => patch({ cities: v })} placeholder="bangalore, gurgaon" />
          <label className="block">
            <span className="text-sm font-medium">Current CTC (₹)</span>
            <input type="number" min={0} value={spec.current_ctc ?? ""}
              onChange={(e) => patch({ current_ctc: e.target.value ? Number(e.target.value) : null })}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
          </label>
          <div className="grid grid-cols-3 gap-2">
            {(["salary_min_multiplier", "salary_target_multiplier", "salary_stretch_multiplier"] as const).map(
              (k) => (
                <label key={k} className="block">
                  <span className="text-xs text-slate-500">{k.split("_")[1]}×</span>
                  <input type="number" step="0.1" value={spec[k] ?? 0}
                    onChange={(e) => patch({ [k]: Number(e.target.value) } as Partial<TrajectorySpec>)}
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1 text-sm" />
                </label>
              ),
            )}
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="space-y-3">
          <p className="text-sm text-slate-500">Paste your resume text (file upload comes later).</p>
          <input value={resume.label} onChange={(e) => setResume({ ...resume, label: e.target.value })}
            placeholder="label e.g. Backend SDE"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <input value={resume.target_role} onChange={(e) => setResume({ ...resume, target_role: e.target.value })}
            placeholder="target role e.g. backend engineer"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <textarea value={resume.content_text} onChange={(e) => setResume({ ...resume, content_text: e.target.value })}
            placeholder="paste resume text…" rows={8}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
        </section>
      )}

      {step === 3 && (
        <section className="space-y-3">
          <p className="text-sm text-slate-500">Optional: block or prefer companies.</p>
          <div className="flex gap-2">
            <input value={pref.company} onChange={(e) => setPref({ ...pref, company: e.target.value })}
              placeholder="company"
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" />
            <select value={pref.preference}
              onChange={(e) => setPref({ ...pref, preference: e.target.value as Preference })}
              className="rounded-md border border-slate-300 px-2 text-sm">
              <option>PREFERRED</option><option>NEUTRAL</option>
              <option>AVOID</option><option>BLOCKED</option>
            </select>
            <button onClick={() => pref.company.trim() && setPreference.mutate(pref)}
              className="rounded-md bg-slate-800 px-3 text-sm text-white">Add</button>
          </div>
          {setPreference.isSuccess && <p className="text-xs text-green-600">Saved.</p>}
        </section>
      )}

      {err && <div className="mt-4"><Banner tone="error">{err}</Banner></div>}

      <div className="mt-6 flex justify-between">
        <button disabled={step === 0} onClick={() => setStep((s) => s - 1)}
          className="rounded-md px-3 py-2 text-sm disabled:opacity-40">Back</button>
        {step < 3 ? (
          <button onClick={() => setStep((s) => s + 1)}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white">Continue</button>
        ) : (
          <button disabled={saveProfile.isPending} onClick={finish}
            className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
            Finish
          </button>
        )}
      </div>
    </div>
  );
}
