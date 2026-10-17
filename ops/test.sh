#!/usr/bin/env bash
# Always create a disposable PostgreSQL database; never target a user's database.
set -euo pipefail
cd "$(dirname "$0")/.."
repo_root="$PWD"
if [[ ! -x .venv/bin/python ]]; then echo 'Run make install first.'; exit 1; fi
test_container="awareguard-tests-$$"
trap 'docker rm -f "$test_container" >/dev/null 2>&1 || true' EXIT
owner_password="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(24))')"
app_password="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(24))')"
docker run -d --name "$test_container" -e POSTGRES_DB=awareguard -e POSTGRES_PASSWORD="$owner_password" -p 127.0.0.1::5432 postgres:16-alpine >/dev/null
for attempt in {1..30}; do
  if docker exec "$test_container" pg_isready -h 127.0.0.1 -U postgres -d awareguard >/dev/null 2>&1; then break; fi
  if [[ "$attempt" = 30 ]]; then echo 'Test PostgreSQL did not start'; exit 1; fi
  sleep 1
done
docker exec -i "$test_container" psql -U postgres -d awareguard --set=app_password="$app_password" >/dev/null <<'SQL'
CREATE ROLE awareguard LOGIN PASSWORD :'app_password' NOSUPERUSER NOBYPASSRLS;
GRANT CONNECT ON DATABASE awareguard TO awareguard;
GRANT USAGE ON SCHEMA public TO awareguard;
SQL
binding="$(docker port "$test_container" 5432/tcp)"
port="${binding##*:}"
export DATABASE_URL="postgresql+psycopg://awareguard:$app_password@127.0.0.1:$port/awareguard"
export MIGRATION_DATABASE_URL="postgresql+psycopg://postgres:$owner_password@127.0.0.1:$port/awareguard"
export TEST_ADMIN_DATABASE_URL="$MIGRATION_DATABASE_URL"
cd backend
"$repo_root/.venv/bin/alembic" upgrade head
"$repo_root/.venv/bin/python" -m pytest -q
