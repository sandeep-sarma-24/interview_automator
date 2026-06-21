"""Role title normalization (M4-P1).

Two steps so the same form is used for aliases AND incoming job titles:
  1. cut trailing qualifiers ("Backend Engineer, Payments" -> "Backend Engineer")
  2. lowercase / strip punctuation / strip seniority tokens
"""
from __future__ import annotations

import re

from app import util

# Cut at the first qualifier separator: comma, '(', '|', bullet, or a spaced dash.
# NOT a bare '/' (would split "QA/SDET") and NOT in-word hyphens (handled below).
_CUT = re.compile(r"\s*[,(|•]|\s+[-–—]\s+")

# Seniority / level tokens removed (canonical roles are seniority-agnostic).
_SENIORITY = re.compile(
    r"\b(senior|sr|staff|principal|lead|junior|jr|associate|intern|entry|mid|level"
    r"|i|ii|iii|iv|v|1|2|3|l[1-9])\b")


def normalize_role(title: str) -> str:
    if not title:
        return ""
    head = _CUT.split(title)[0]
    n = util.normalize_text(head)          # lowercase + strip most punctuation
    n = n.replace("/", " ").replace(".", " ")
    n = _SENIORITY.sub(" ", n)
    return re.sub(r"\s+", " ", n).strip()
