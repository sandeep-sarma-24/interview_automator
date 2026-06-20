#!/bin/sh
# API container health check: GET /health (which also verifies DB accessibility).
# Uses python (already on PATH) so no curl dependency is added to the image.
exec python - <<'PY'
import sys, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=4) as r:
        sys.exit(0 if r.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
