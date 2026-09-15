#!/usr/bin/env bash
# Back up the database and the uploaded files.
#
# Usage, from the project folder on the Docker host:
#   bash scripts/backup.sh
#
# Everything runs inside one-off containers: files are read from /data and the backup is
# written to /backups, whatever is mounted there (a host folder or a NAS through the SMB/NFS
# override files). With STORAGE_BACKEND=s3 only the database is dumped; protect the bucket with
# versioning or replication at the provider. The real .env is never included (it holds secrets):
# keep a protected copy of it separately.
set -euo pipefail

cd "$(dirname "$0")/.."

env_value() {
  [ -f .env ] || return 0
  grep -E "^$1=" .env | tail -n1 | cut -d= -f2- | sed -e "s/^'//" -e "s/'$//" || true
}

run_backend() {
  docker compose run --rm --no-deps -T backend sh -c "$1"
}

storage_backend="$(env_value STORAGE_BACKEND)"
keep="$(env_value BACKUP_KEEP)"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
name="information-board-$timestamp"

echo "Stopping backend and worker for a consistent backup (short interruption)..."
docker compose stop backend worker

restart_services() {
  echo "Starting backend and worker again..."
  docker compose start backend worker
}
trap restart_services EXIT

run_backend "mkdir -p /backups/$name"

echo "Dumping the database..."
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  | docker compose run --rm --no-deps -T backend sh -c "cat > /backups/$name/database.dump"

if [ "$storage_backend" = "s3" ]; then
  echo "STORAGE_BACKEND=s3: uploaded files stay in the bucket and are not copied."
else
  echo "Archiving uploaded files..."
  run_backend "tar -C /data -czf /backups/$name/data.tar.gz ."
fi

run_backend "cd /backups/$name && sha256sum database.dump \$(ls data.tar.gz 2>/dev/null) > manifest.sha256 && printf 'created_at_utc=%s\nstorage_backend=%s\n' '$timestamp' '${storage_backend:-local}' > info.txt"

if [[ "$keep" =~ ^[0-9]+$ ]] && [ "$keep" -gt 0 ]; then
  echo "Keeping the $keep most recent backups..."
  run_backend "ls -1d /backups/information-board-* | sort | head -n -$keep | xargs -r rm -rf"
fi

echo "Backup created: $name (inside the backups location: ${BOARD_BACKUPS_PATH:-$(env_value BOARD_BACKUPS_PATH)})"
echo "Remember: .env is not included. Keep a protected copy of it separately."
