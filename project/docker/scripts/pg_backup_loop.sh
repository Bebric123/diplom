#!/usr/bin/env bash
set -euo pipefail
mkdir -p /backups
INTERVAL="${BACKUP_INTERVAL_SEC:-86400}"
DB="${PGDATABASE:-${POSTGRES_DB:-Monitoring}}"
echo "pg_backup: db=${DB} interval=${INTERVAL}s"
while true; do
  TS="$(date +%Y%m%d_%H%M%S)"
  OUT="/backups/${DB}_${TS}.dump"
  if pg_dump -h "${PGHOST:-db}" -U "${PGUSER:-postgres}" -d "$DB" -F c -f "$OUT" 2>/dev/null; then
    echo "pg_backup: wrote $OUT"
    find /backups -name "${DB}_*.dump" -type f -mtime +14 -delete 2>/dev/null || true
  else
    echo "pg_backup: dump failed" >&2
  fi
  sleep "$INTERVAL"
done
