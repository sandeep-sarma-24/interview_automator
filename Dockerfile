# syntax=docker/dockerfile:1
# Multi-stage build for the Job Discovery & Application Copilot.
# Base: python 3.12 slim (Debian bookworm -> SQLite 3.40, satisfies STRICT >= 3.37).

# ───────────────────────────── builder ─────────────────────────────
FROM python:3.12-slim-bookworm AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencies install from manylinux wheels (numpy, google libs, httpx, etc.),
# so no compiler toolchain is needed.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install -r requirements.txt

# ───────────────────────────── runtime ─────────────────────────────
FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    SCRAPER_BASE_DIR=/data

# Non-root user (fixed uid/gid so volume ownership is predictable).
RUN groupadd -g 10001 app \
    && useradd -u 10001 -g app -m -s /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY app/ ./app/
COPY docker/entrypoint.sh docker/healthcheck-api.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/healthcheck-api.sh \
    && mkdir -p /data/resumes /data/backups /data/secrets \
    && chown -R app:app /data /app

# An empty named volume mounted at /data inherits this ownership on first use,
# so the app runs entirely as non-root with a writable data dir.
USER app

ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "-m", "app.cli", "serve"]
