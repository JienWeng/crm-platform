#!/usr/bin/env bash
# Nightly Postgres backup for the Twenty stack.
# Usage: ./backup.sh [output_dir]   (default: ./backups)
# Cron example (2am daily):  0 2 * * * cd /opt/twenty/backend && ./backup.sh >> backup.log 2>&1
set -euo pipefail

OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"

# Read PG user from .env (defaults to postgres); DB name is `default`.
PG_USER="$(grep -E '^PG_DATABASE_USER=' .env | cut -d= -f2- || true)"
PG_USER="${PG_USER:-postgres}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$OUT_DIR/twenty_${STAMP}.sql.gz"

docker compose exec -T db pg_dump -U "$PG_USER" default | gzip > "$OUT_FILE"
echo "Backup written: $OUT_FILE"

# Retain last 14 backups.
ls -1t "$OUT_DIR"/twenty_*.sql.gz | tail -n +15 | xargs -r rm -f
