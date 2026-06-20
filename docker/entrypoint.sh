#!/bin/sh
# Thin entrypoint (runs as non-root 'app'). Ensures the data subdirs exist on a
# possibly-fresh volume, then execs the requested command. No privilege changes.
set -e

mkdir -p /data/resumes /data/backups /data/secrets 2>/dev/null || true

exec "$@"
