// Display helpers. Match-explanation parsing keeps the "explanation is the hero".

export function scorePct(score: number | null | undefined): string {
  return score == null ? "—" : String(Math.round(score * 100));
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "unknown";
  const secs = Math.max(0, (Date.now() - then) / 1000);
  if (secs < 90) return "just now";
  const mins = secs / 60;
  if (mins < 90) return `${Math.round(mins)}m ago`;
  const hrs = mins / 60;
  if (hrs < 36) return `${Math.round(hrs)}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export type ParsedSignal = { sign: "+" | "−" | "~"; text: string };

// explanation_summary looks like: "+Strong move toward AI +Python −No salary data ~Stretch…"
// Prefixes are exactly +, − (U+2212) and ~, so we can split on those boundaries.
export function parseExplanation(summary: string | null | undefined): ParsedSignal[] {
  if (!summary) return [];
  const out: ParsedSignal[] = [];
  const re = /([+~−])([^+~−]+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(summary)) !== null) {
    const sign = (m[1] === "−" ? "−" : m[1]) as ParsedSignal["sign"];
    out.push({ sign, text: m[2].trim() });
  }
  return out;
}
