#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  ARIA — VM-side backup of the two data volumes.
#
#  Run ON the VM, from deploy/:
#      ./backup.sh              → writes ../backups/aria-data-*.tar.gz
#                                  (+ aria-gateway-*.tar.gz, the spending ledger)
#      ./backup.sh /some/dir    → custom destination
#
#  Keeps the newest 14 of each, deletes older ones. Wire into cron
#  (weekly is plenty for the pilot):
#      crontab -e
#      15 3 * * 1  cd /opt/aria/deploy && ./backup.sh >> backup.log 2>&1
#
#  Restore (chat/ledger data REPLACED — confirm the target is disposable):
#      docker cp ../backups/<archive>.tar.gz "$(docker compose ps -q backend)":/tmp/restore.tar.gz
#      docker compose stop backend
#      docker compose run --rm --entrypoint sh backend -c "tar -xzf /tmp/restore.tar.gz -C /data"
#      docker compose start backend
#      (same pattern for aria-gateway archives → the gateway container)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

cd "$(dirname "$0")"

DEST="${1:-../backups}"
STAMP="$(date +%Y%m%d-%H%M)"
mkdir -p "$DEST"

for SVC in backend gateway; do
  [ "$SVC" = "gateway" ] && PREFIX="aria-gateway" || PREFIX="aria-data"
  docker compose exec "$SVC" tar -czf /tmp/aria-backup.tar.gz -C /data .
  docker compose cp "$SVC":/tmp/aria-backup.tar.gz "$DEST/$PREFIX-$STAMP.tar.gz.tmp"
  docker compose exec "$SVC" rm -f /tmp/aria-backup.tar.gz
  mv "$DEST/$PREFIX-$STAMP.tar.gz.tmp" "$DEST/$PREFIX-$STAMP.tar.gz"
done

# Retention: keep the newest 14 of each prefix.
for PREFIX in aria-data aria-gateway; do
  ls -1t "$DEST"/$PREFIX-*.tar.gz 2>/dev/null | tail -n +15 | xargs -r rm --
done

echo "backup ok: $(du -h "$DEST"/aria-data-$STAMP.tar.gz "$DEST"/aria-gateway-$STAMP.tar.gz | paste -sd' ' -)"
