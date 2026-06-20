"""Global 'heavy resource' lock.

On an 8 GB laptop only one heavy operation may run at a time (today: embeddings;
later: a browser session or an LLM). A single OS file lock enforces that and also
prevents two worker processes from running concurrently. Non-blocking: if the
lock is held, the caller skips this cycle rather than piling on.
"""
from __future__ import annotations

import fcntl
from contextlib import contextmanager
from typing import Iterator

from app.config import get_settings


class ResourceBusy(Exception):
    pass


@contextmanager
def heavy_resource_lock() -> Iterator[None]:
    settings = get_settings()
    lock_path = settings.base_dir / "worker.lock"
    fh = open(lock_path, "w")
    try:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ResourceBusy("another heavy operation/worker holds the lock")
        yield
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()
