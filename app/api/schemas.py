"""Request/response models for the API (onboarding wizard, preferences, jobs)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app import util


class CandidateCreate(BaseModel):
    display_name: str
    email: str
    consent: bool = True


class TrajectorySpec(BaseModel):
    """The onboarding wizard payload -> a new current profile version."""
    total_experience_months: int = 0
    seniority_label: Optional[str] = None
    core_skills: List[str] = Field(default_factory=list)
    acquiring_skills: List[str] = Field(default_factory=list)
    target_roles: List[str] = Field(default_factory=list)
    acceptable_roles: List[str] = Field(default_factory=list)
    avoid_roles: List[str] = Field(default_factory=list)
    target_domain_signals: List[str] = Field(default_factory=list)
    cities: List[str] = Field(default_factory=list)
    remote_required: bool = False
    current_ctc: Optional[float] = None
    salary_min_multiplier: float = 1.3
    salary_target_multiplier: float = 1.7
    salary_stretch_multiplier: float = 2.5
    weights: Optional[Dict[str, float]] = None

    def to_spec(self) -> Dict[str, Any]:
        return {
            "total_experience_months": self.total_experience_months,
            "seniority_label": self.seniority_label,
            "core_skills_json": util.dumps(self.core_skills),
            "acquiring_skills_json": util.dumps(self.acquiring_skills),
            "target_roles_json": util.dumps(self.target_roles),
            "acceptable_roles_json": util.dumps(self.acceptable_roles),
            "avoid_roles_json": util.dumps(self.avoid_roles),
            "target_domain_signals_json": util.dumps(self.target_domain_signals),
            "location_prefs_json": util.dumps({"cities": self.cities}),
            "remote_required": 1 if self.remote_required else 0,
            "current_ctc": self.current_ctc,
            "salary_min_multiplier": self.salary_min_multiplier,
            "salary_target_multiplier": self.salary_target_multiplier,
            "salary_stretch_multiplier": self.salary_stretch_multiplier,
            "weights_json": util.dumps(self.weights) if self.weights else None,
        }


class ResumeUpsert(BaseModel):
    label: str
    target_role: Optional[str] = None
    content_text: Optional[str] = None


class PreferenceSet(BaseModel):
    company: str
    preference: str  # PREFERRED | NEUTRAL | AVOID | BLOCKED
    note: Optional[str] = None


class ManualUrl(BaseModel):
    url: str
