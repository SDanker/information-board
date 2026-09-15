#!/usr/bin/env bash
# Restore a backup created by scripts/backup.sh.
#
# Usage, from the project folder on the Docker host:
#   bash scripts/restore.sh information-board-20260101T030000Z
#
# The checksums are verified before anything is touched, and an explicit confirmation is
# required because the current database is replaced by the one in the backup. Uploaded files
# are extracted over the current ones.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "$#" -ne 1 ]; then
  echo "Usage: bash scripts/restore.sh <backup-name>" >&2
  exit 2
fi

name="$(basename "$1")"
if [[ ! "$name" =~ ^information-board-[0-9TZ]+$ ]]; then
  echo "Unexpected backup name: $name" >&2
  exit 2
fi

run_backend() {
  docker compose run --rm --no-deps -T backend sh -c "$1"
}

echo "Verifying checksums..."
run_backend "cd /backups/$name && sha256sum -c manifest.sha256"

read -r -p "This replaces the current database and restores the files from $name. Type 'yes' to continue: " confirmation
if [ "$confirmation" != "yes" ]; then
  echo "Cancelled."
  exit 1
fi

echo "Stopping backend and worker..."
docker compose stop backend worker
trap 'echo "Starting backend and worker again..."; docker compose start backend worker' EXIT

echo "Restoring the database..."
docker compose run --rm --no-deps -T backend cat "/backups/$name/database.dump" \
  | docker compose exec -T postgres sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  || echo "pg_restore reported warnings; review the output above."

if run_backend "test -f /backups/$name/data.tar.gz"; then
  echo "Restoring uploaded files..."
  run_backend "tar -C /data -xzf /backups/$name/data.tar.gz"
else
  echo "This backup has no data.tar.gz (S3 storage): uploaded files were not restored."
fi

echo "Restore finished. Check it with: docker compose exec -T backend python - < scripts/deployment_smoke.py"
