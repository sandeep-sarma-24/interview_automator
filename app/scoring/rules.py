"""Deterministic scoring rules (no LLM).

Stage 0  hard filters (BLOCKED company, remote gate, seniority/total-years gate).
Stage 2  weighted dimensions: trajectory, skills, location, experience, salary,
         then a company-preference adjustment.

Design rules baked in here:
  * The experience gate is on TOTAL/seniority years only. Domain-specific
    experience the candidate is acquiring (e.g. ML) is NEVER a gate — it becomes
    a flagged "stretch" signal so transition roles survive.
  * Trajectory dominates (weight 0.45); salary is a tiny modifier (0.05) and
    missing salary is neutral, never penalized.
  * LEAP roles always shortlist (high recall), labelled with warnings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app import util
from app.config import get_settings
from app.domain import (COMPANY_PREFERENCE_ADJUST, DEFAULT_WEIGHTS, Reason,
                        TRAJECTORY_SCORES)

_YEARS_RE = re.compile(
    r"(\d{1,2})\s*(?:\+|to|-|–|—)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)", re.I)
_LPA_RE = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d{1,3}(?:\.\d+)?)\s*(?:-|to|–)?\s*"
                     r"(\d{1,3}(?:\.\d+)?)?\s*(?:lpa|lakhs?|l\b)", re.I)


# ─────────────────────────────── profile ──────────────────────────────────
@dataclass
class Profile:
    total_experience_months: int = 0
    core_skills: List[str] = field(default_factory=list)
    acquiring_skills: List[str] = field(default_factory=list)
    target_roles: List[str] = field(default_factory=list)
    acceptable_roles: List[str] = field(default_factory=list)
    avoid_roles: List[str] = field(default_factory=list)
    domain_signals: List[str] = field(default_factory=list)
    cities: List[str] = field(default_factory=list)
    remote_required: bool = False
    current_ctc: Optional[float] = None
    mult_min: float = 1.3
    mult_target: float = 1.7
    mult_stretch: float = 2.5
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    @property
    def target_text(self) -> str:
        return " ".join(self.target_roles + self.domain_signals
                        + self.acquiring_skills + self.core_skills)


def build_profile(pv: Dict[str, Any]) -> Profile:
    loc = util.loads(pv.get("location_prefs_json"), {}) or {}
    weights = dict(DEFAULT_WEIGHTS)
    weights.update(util.loads(pv.get("weights_json"), {}) or {})
    return Profile(
        total_experience_months=int(pv.get("total_experience_months") or 0),
        core_skills=[util.normalize_text(s) for s in util.loads(pv.get("core_skills_json"), [])],
        acquiring_skills=[util.normalize_text(s) for s in util.loads(pv.get("acquiring_skills_json"), [])],
        target_roles=[util.normalize_text(s) for s in util.loads(pv.get("target_roles_json"), [])],
        acceptable_roles=[util.normalize_text(s) for s in util.loads(pv.get("acceptable_roles_json"), [])],
        avoid_roles=[util.normalize_text(s) for s in util.loads(pv.get("avoid_roles_json"), [])],
        domain_signals=[util.normalize_text(s) for s in util.loads(pv.get("target_domain_signals_json"), [])],
        cities=[util.normalize_text(c) for c in loc.get("cities", [])],
        remote_required=bool(pv.get("remote_required")),
        current_ctc=pv.get("current_ctc"),
        mult_min=float(pv.get("salary_min_multiplier") or 1.3),
        mult_target=float(pv.get("salary_target_multiplier") or 1.7),
        mult_stretch=float(pv.get("salary_stretch_multiplier") or 2.5),
        weights=weights,
    )


# ─────────────────────────────── parsing ──────────────────────────────────
def parse_experience_months(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Best-effort (min,max) in months from a JD. Treated as TOTAL seniority."""
    if not text:
        return None, None
    m = _YEARS_RE.search(text)
    if not m:
        return None, None
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else None
    return lo * 12, (hi * 12 if hi else None)


def parse_salary_annual(*texts: str) -> Optional[float]:
    blob = " ".join(t for t in texts if t)
    if not blob:
        return None
    m = _LPA_RE.search(blob)
    if m:
        lo = float(m.group(1))
        hi = float(m.group(2)) if m.group(2) else lo
        return (lo + hi) / 2.0 * 100000.0  # lakhs -> rupees
    return None


def _phrase_in(text: str, phrase: str) -> bool:
    phrase = phrase.strip()
    return bool(phrase) and phrase in text


def _any_in(text: str, phrases: List[str]) -> bool:
    return any(_phrase_in(text, p) for p in phrases)


# ──────────────────────────────── stage 0 ─────────────────────────────────
def stage0_filter(profile: Profile, job: Dict[str, Any],
                  company_pref: Optional[str]) -> Optional[str]:
    """Return a reason code if the job is hard-filtered, else None."""
    if company_pref == "BLOCKED":
        return Reason.COMPANY_BLOCKED

    if profile.remote_required and job.get("is_remote") == 0:
        return Reason.NOT_REMOTE

    stretch = get_settings().experience_stretch_months
    jmin = job.get("min_experience_months")
    jmax = job.get("max_experience_months")
    if jmin is None and jmax is None:
        jmin, jmax = parse_experience_months(job.get("description_text") or job.get("title") or "")
    cand = profile.total_experience_months
    if jmin is not None and cand < jmin - stretch:
        return Reason.SENIORITY_UNDER
    if jmax is not None and cand > jmax + stretch:
        return Reason.SENIORITY_OVER
    return None


# ──────────────────────────────── stage 2 ─────────────────────────────────
def _trajectory(profile: Profile, title: str, text: str,
                embed_sim: float) -> Tuple[str, List[Dict[str, Any]]]:
    sig: List[Dict[str, Any]] = []
    if _any_in(title, profile.avoid_roles) or _any_in(text, profile.avoid_roles):
        sig.append(_s("TRAJECTORY", "NEGATIVE", "Backward move (away from your goal)"))
        return "BACKWARD", sig

    primary = profile.target_roles[0] if profile.target_roles else ""
    if _any_in(text, profile.domain_signals) or (primary and _phrase_in(title, primary)):
        tgt = profile.target_roles[0] if profile.target_roles else "your target"
        sig.append(_s("TRAJECTORY", "POSITIVE", f"Strong move toward {tgt}"))
        return "LEAP", sig

    if _any_in(title, profile.target_roles) or _any_in(title, profile.acceptable_roles) \
            or _any_in(text, profile.target_roles):
        sig.append(_s("TRAJECTORY", "POSITIVE", "Forward move"))
        return "FORWARD", sig

    if _any_in(text, profile.acceptable_roles) or embed_sim >= 0.6:
        sig.append(_s("TRAJECTORY", "NEUTRAL", "Lateral move"))
        return "LATERAL", sig

    sig.append(_s("TRAJECTORY", "NEUTRAL", "Limited career movement"))
    return "STALL", sig


def _skills(profile: Profile, text: str, embed_sim: float) -> Tuple[float, List[Dict[str, Any]]]:
    sig: List[Dict[str, Any]] = []
    if not profile.core_skills:
        return embed_sim, sig
    matched = [s for s in profile.core_skills if _phrase_in(text, s)]
    ratio = len(matched) / float(len(profile.core_skills))
    bonus = 0.1 * len([s for s in profile.acquiring_skills if _phrase_in(text, s)])
    for s in matched[:4]:
        sig.append(_s("SKILL", "POSITIVE", f"+{s}"))
    return min(1.0, ratio + min(0.2, bonus)), sig


def _location(profile: Profile, job: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    is_remote = job.get("is_remote")
    loc = util.normalize_text(job.get("location") or "")
    if is_remote == 1:
        return 1.0, [_s("REMOTE", "POSITIVE", "Remote")]
    if loc and any(c in loc for c in profile.cities):
        city = next(c for c in profile.cities if c in loc)
        return 0.7, [_s("LOCATION", "POSITIVE", f"In {city.title()}")]
    if is_remote == 0 and profile.cities:
        return 0.2, [_s("LOCATION", "NEGATIVE", "Not remote / outside preferred cities")]
    return 0.4, [_s("LOCATION", "NEUTRAL", "Location unknown")]


def _experience(profile: Profile, job: Dict[str, Any], direction: str
                ) -> Tuple[float, List[Dict[str, Any]]]:
    jmin = job.get("min_experience_months")
    jmax = job.get("max_experience_months")
    if jmin is None and jmax is None:
        jmin, jmax = parse_experience_months(job.get("description_text") or job.get("title") or "")
    cand = profile.total_experience_months
    stretch = get_settings().experience_stretch_months
    if jmin is None and jmax is None:
        return 0.6, []  # unknown -> neutral, never penalized
    lo = jmin if jmin is not None else 0
    hi = jmax if jmax is not None else lo + 240
    if lo <= cand <= hi:
        return 1.0, []
    if lo - stretch <= cand <= hi + stretch:
        sig = []
        if direction in ("LEAP", "FORWARD") and cand < lo:
            sig.append(_s("EXPERIENCE", "NEUTRAL",
                          "Stretch: a bit below stated experience (transition role)"))
        return 0.6, sig
    return 0.4, []


def _salary(profile: Profile, job: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    annual = parse_salary_annual(job.get("salary_text") or "", job.get("description_text") or "")
    if annual is None or not profile.current_ctc:
        return 0.5, [_s("SALARY", "NEGATIVE", "No salary data")]
    target = profile.current_ctc * profile.mult_target
    stretch = profile.current_ctc * profile.mult_stretch
    minimum = profile.current_ctc * profile.mult_min
    if annual >= stretch:
        return 1.0, [_s("SALARY", "POSITIVE", "At/above your stretch")]
    if annual >= target:
        return 0.85, [_s("SALARY", "POSITIVE", "At/above your target")]
    if annual >= minimum:
        return 0.6, [_s("SALARY", "NEUTRAL", "Between minimum and target")]
    return 0.25, [_s("SALARY", "NEGATIVE", "Below your minimum")]


def _s(stype: str, direction: str, label: str, detail: Optional[str] = None) -> Dict[str, Any]:
    return {"signal_type": stype, "direction": direction, "label": label, "detail": detail}


def canonical_trajectory(role_ctx: Dict[str, Any],
                         embed_sim: float) -> Tuple[str, List[Dict[str, Any]]]:
    """Trajectory direction from CANONICAL role relationship (P1-C).

    role_ctx = {job_canonical, primary, targets:set, avoids:set, related:set, method}.
    Same direction vocabulary + TRAJECTORY_SCORES as before — only the *input*
    changes from substring matching to canonical-role matching.
    """
    jc = role_ctx["job_canonical"]
    det = f"job role: {jc}"
    if jc in role_ctx["avoids"]:
        return "BACKWARD", [_s("TRAJECTORY", "NEGATIVE", "Backward move (away from your goal)", det)]
    if jc == role_ctx["primary"]:
        return "LEAP", [_s("TRAJECTORY", "POSITIVE", f"Strong move toward {jc}", det)]
    if jc in role_ctx["targets"]:
        return "FORWARD", [_s("TRAJECTORY", "POSITIVE", "Forward move (target role)", det)]
    if jc in role_ctx["related"]:
        return "FORWARD", [_s("TRAJECTORY", "POSITIVE", "Forward move (related role family)", det)]
    if embed_sim >= 0.6:
        return "LATERAL", [_s("TRAJECTORY", "NEUTRAL", "Lateral move", det)]
    return "STALL", [_s("TRAJECTORY", "NEUTRAL", "Limited career movement", det)]


def score_job(profile: Profile, job: Dict[str, Any], company_pref: Optional[str],
              embed_sim: float, used_embeddings: bool,
              role_ctx: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Run Stage 2. Returns (result, signals). Assumes Stage 0 already passed."""
    title = util.normalize_text(job.get("title"))
    text = util.normalize_text(f"{job.get('title') or ''} {job.get('description_text') or ''}")

    # Trajectory INPUT: canonical role match when the job title resolved; otherwise
    # fall back to the legacy keyword path (preserves recall on unresolved titles).
    if role_ctx and role_ctx.get("job_canonical"):
        direction, t_sig = canonical_trajectory(role_ctx, embed_sim)
        role_method = role_ctx.get("method", "CANONICAL")
    else:
        direction, t_sig = _trajectory(profile, title, text, embed_sim)
        role_method = "FALLBACK"
    traj_score = TRAJECTORY_SCORES[direction]
    skill_score, sk_sig = _skills(profile, text, embed_sim)
    loc_score, loc_sig = _location(profile, job)
    exp_score, exp_sig = _experience(profile, job, direction)
    sal_score, sal_sig = _salary(profile, job)

    w = profile.weights
    total = (w["trajectory"] * traj_score + w["skills"] * skill_score
             + w["location"] * loc_score + w["experience"] * exp_score
             + w["salary"] * sal_score)

    signals = t_sig + sk_sig + loc_sig + exp_sig + sal_sig
    if company_pref in ("PREFERRED", "AVOID"):
        total += COMPANY_PREFERENCE_ADJUST[company_pref]
        signals.append(_s("COMPANY",
                          "POSITIVE" if company_pref == "PREFERRED" else "NEGATIVE",
                          "Preferred company" if company_pref == "PREFERRED"
                          else "Company you'd rather avoid"))
    total = max(0.0, min(1.0, total))

    density = job.get("signal_density") or "THIN"
    confidence = (0.9 if density == "RICH" else 0.5) * (1.0 if used_embeddings else 0.8)
    leap = direction == "LEAP"

    result = {
        "trajectory_direction": direction,
        "trajectory_score": round(traj_score, 4),
        "skill_score": round(skill_score, 4),
        "location_score": round(loc_score, 4),
        "experience_score": round(exp_score, 4),
        "salary_fit_score": round(sal_score, 4),
        "total_score": round(total, 4),
        "confidence": round(confidence, 4),
        "signal_density": density,
        "leap_override": leap,
        "scoring_model_version": "rules-v2-canonical+" + ("nomic-embed-text" if used_embeddings else "fallback"),
        "breakdown": {
            "weights": w, "embed_sim": round(embed_sim, 4),
            "role_match": {
                "job_canonical": (role_ctx or {}).get("job_canonical"),
                "method": role_method,            # ALIAS | EMBEDDING | FALLBACK
                "direction": direction,
            },
        },
        "explanation_summary": build_summary(signals),
    }
    return result, signals


def build_summary(signals: List[Dict[str, Any]]) -> str:
    parts = []
    for s in signals:
        prefix = {"POSITIVE": "+", "NEGATIVE": "−", "NEUTRAL": "~"}[s["direction"]]
        parts.append(f"{prefix}{s['label']}")
    return " ".join(parts)
