"""Domain constants shared across services: workflow states, scoring vocab,
default weights. Kept dependency-free so any service can import it cheaply.
"""
from __future__ import annotations

# ── Workflow states (full set; Sprint 1 only reaches the early ones) ──
class State:
    DISCOVERED = "DISCOVERED"
    FILTERED = "FILTERED"
    SCORED = "SCORED"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    # later milestones: AWAITING_REVIEW, ... SUBMITTED (see schema CHECK)


# Reason codes attached to FILTERED / REJECTED.
class Reason:
    COMPANY_BLOCKED = "COMPANY_BLOCKED"
    NOT_REMOTE = "NOT_REMOTE"
    LOCATION_INELIGIBLE = "LOCATION_INELIGIBLE"
    SENIORITY_UNDER = "SENIORITY_UNDER"
    SENIORITY_OVER = "SENIORITY_OVER"


# ── Trajectory directions and their base scores ──
TRAJECTORY_SCORES = {
    "LEAP": 1.0,
    "FORWARD": 0.8,
    "LATERAL": 0.5,
    "STALL": 0.35,
    "BACKWARD": 0.1,
}

# ── Default dimension weights (Mohit V1: trajectory dominant, salary tiny) ──
DEFAULT_WEIGHTS = {
    "trajectory": 0.45,
    "skills": 0.20,
    "location": 0.15,
    "experience": 0.15,
    "salary": 0.05,
}

# Company-preference adjustments applied after the weighted sum.
COMPANY_PREFERENCE_ADJUST = {
    "PREFERRED": 0.08,
    "NEUTRAL": 0.0,
    "AVOID": -0.12,
    # BLOCKED never reaches scoring (hard-filtered in Stage 0).
}

SIGNAL_TYPES = (
    "TRAJECTORY", "ROLE", "SKILL", "EXPERIENCE", "SALARY",
    "LOCATION", "REMOTE", "SENIORITY", "COMPANY",
)
