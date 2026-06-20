import { useState } from "react";

// Minimal tag editor for skills / roles (comma or Enter to add).
export default function TagInput({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");

  function commit() {
    const t = draft.trim().toLowerCase();
    if (t && !value.includes(t)) onChange([...value, t]);
    setDraft("");
  }

  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      <div className="mt-1 flex flex-wrap gap-1 rounded-md border border-slate-300 p-1.5">
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5 text-xs"
          >
            {tag}
            <button
              type="button"
              onClick={() => onChange(value.filter((v) => v !== tag))}
              className="text-slate-400 hover:text-slate-700"
              aria-label={`remove ${tag}`}
            >
              ✕
            </button>
          </span>
        ))}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              commit();
            }
          }}
          onBlur={commit}
          placeholder={placeholder || "type and press Enter"}
          className="min-w-[8rem] flex-1 bg-transparent px-1 text-sm outline-none"
        />
      </div>
    </label>
  );
}
