"""Stage-1 semantic similarity.

Primary path: Ollama `nomic-embed-text` embeddings + cosine.
Graceful fallback: if Ollama is unreachable, a deterministic token-overlap
similarity is used so scoring still runs (degrade, don't fail). The provider
probes Ollama exactly once per run, not per job.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import httpx
import numpy as np

from app import util
from app.config import get_settings

log = logging.getLogger("scoring.embeddings")


def _cosine(a: List[float], b: List[float]) -> float:
    va, vb = np.asarray(a, dtype="float32"), np.asarray(b, dtype="float32")
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    # map cosine [-1,1] -> [0,1]
    return float((np.dot(va, vb) / (na * nb) + 1.0) / 2.0)


def _token_overlap(a: str, b: str) -> float:
    ta, tb = set(util.tokens(a)), set(util.tokens(b))
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return inter / float(len(ta | tb))  # Jaccard, already 0..1


class EmbeddingProvider:
    def __init__(self) -> None:
        s = get_settings()
        self.url = s.ollama_url.rstrip("/")
        self.model = s.embedding_model
        self.available = self._probe()
        log.info("embedding backend: %s",
                 f"ollama:{self.model}" if self.available else "fallback:token-overlap")

    def _probe(self) -> bool:
        try:
            r = httpx.get(f"{self.url}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def embed(self, text: str) -> Optional[List[float]]:
        if not self.available or not text:
            return None
        try:
            r = httpx.post(f"{self.url}/api/embeddings",
                           json={"model": self.model, "prompt": text[:8000]},
                           timeout=30.0)
            r.raise_for_status()
            vec = r.json().get("embedding")
            return vec if vec else None
        except Exception as e:
            log.warning("embed failed, falling back to token overlap: %s", e)
            self.available = False
            return None

    def similarity(self, text_a: str, text_b: str,
                   vec_a: Optional[List[float]] = None,
                   vec_b: Optional[List[float]] = None) -> Tuple[float, bool]:
        """Return (score 0..1, used_embeddings)."""
        if self.available:
            va = vec_a or self.embed(text_a)
            vb = vec_b or self.embed(text_b)
            if va and vb:
                return _cosine(va, vb), True
        return _token_overlap(text_a, text_b), False
