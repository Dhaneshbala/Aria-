#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  ARIA — VM-side backup of the backend data volume (aria_data).
#
#  Run ON the VM, from deploy/:
#      ./backup.sh              → writes ../backups/aria-data-YYYYmmdd-HHMM.tar.gz
#      ./backup.sh /some/dir    → custom destination
#
#  Keeps the newest 14 archives, deletes older ones. Wire it into cron
#  (weekly is plenty for the pilot):
#      crontab -e
#      15 3 * * 1  cd /opt/aria/deploy && ./backup.sh >> backup.log 2>&1
#
#  Restore (data REPLACED — confirm the target is disposable):
#      docker compose down backend
#      docker compose run --rm --entrypoint sh backend \
#          -c "tar -xzf /tmp/restore.tar.gz -C /data"
#      (after: docker cp <archive> <aria-backend-1>:/tmp/restore.tar.gz)
#      docker compose up -d backend
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")"

DEST="${1:-../backups}"
mkdir -p "$DEST"
ARCHIVE="$DEST/aria-data-$(date +%Y%m%d-%H%M).tar.gz"

# The compose project is named "aria" → the volume is aria_aria_data.
# Pack through a throwaway alpine container so no service is disturbed.
docker compose exec backend tar -czf /tmp/aria-data-backup.tar.gz -C /data .
docker compose cp backend:/tmp/aria-data-backup.tar.gz "$ARCHIVE.tmp"
docker compose exec backend rm -f /tmp/aria-data-backup.tar.gz
mv "$ARCHIVE.tmp" "$ARCHIVE"

# Retention: keep the newest 14.
ls -1t "$DEST"/aria-data-*.tar.gz 2>/dev/null | tail -n +15 | xargs -r rm --

echo "backup ok: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"
