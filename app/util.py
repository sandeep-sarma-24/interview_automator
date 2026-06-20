"""Small dependency-light helpers shared across the app."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any, List, Optional


def now_iso() -> str:
    """Current UTC time as ISO-8601 (sorts lexically, no tz ambiguity)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def sha256_hex(*parts: str) -> str:
    h = hashlib.sha256()
    h.update("\x1f".join(p or "" for p in parts).encode("utf-8"))
    return h.hexdigest()


def normalize_text(s: Optional[str]) -> str:
    """Lowercase, collapse whitespace, strip punctuation-ish for matching."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[^a-z0-9+#./ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_company_name(name: Optional[str]) -> str:
    n = normalize_text(name)
    # strip punctuation kept by normalize_text (e.g. the '.' in "Inc.")
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    # drop common suffixes so "Stripe, Inc." == "stripe"
    n = re.sub(r"\b(inc|llc|ltd|pvt|private|limited|corp|technologies|technology|labs|co)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def loads(s: Optional[str], default: Any = None) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return default


def tokens(s: Optional[str]) -> List[str]:
    return [t for t in normalize_text(s).split(" ") if t]
