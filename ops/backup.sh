#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p backups
archive="backups/awareguard-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose exec -T db pg_dump -U postgres -d awareguard -Fc > "$archive"
test -s "$archive"
printf 'Backup saved: %s\n' "$archive"
