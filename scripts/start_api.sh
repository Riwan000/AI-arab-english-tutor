#!/bin/sh
set -e

DB_DIR="${DATABASE_PATH%/*}"
if [ -n "$DB_DIR" ]; then
  mkdir -p "$DB_DIR"
fi

exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips='*'
