# AwareGuard MVP Lite

A corporate phishing-awareness training platform built from [the supplied specification](docs/SPEC.ru.md). Russian-language administration, three fixed educational email scenarios, and a responsive training page. Modular FastAPI monolith, React/TypeScript + Ant Design, PostgreSQL 16, SQLAlchemy/Alembic, SMTP, Docker Compose.

## Start with Docker Compose

Prerequisites: Git, Docker with Compose 2.24+, and Python 3.12+ for the initial configuration helper. On macOS, start Docker Desktop first.

```sh
git clone https://github.com/sadrimamadziyoev/isfand.git
cd isfand
python3.12 -m venv .venv
.venv/bin/pip install --require-hashes -r backend/requirements.lock
.venv/bin/python ops/configure.py
docker compose up -d --build
docker compose exec api python -m app.cli create-admin --email admin@your-company.com
```

Run these commands from the project root: it must contain `backend/requirements.lock`, `frontend`, and `compose.yaml`. If you already cloned the repository, use that checkout instead of cloning again. If the lockfile is missing, check `pwd`, `git status`, and your checkout before installing; do not substitute a different requirements file.

The configuration helper detects a host CA bundle on Linux or macOS and saves `BUILD_CA_CERT` in `.env`, so Docker builds retain TLS verification. To use a corporate CA bundle, export `BUILD_CA_CERT=/absolute/path/to/trusted-bundle.pem` before running the helper. It never overwrites an existing `.env`. If you created `.env` with an earlier version on macOS, add `BUILD_CA_CERT=/etc/ssl/cert.pem` to that file (or use your actual trusted bundle path); preserve the existing database passwords and MFA key.

The CLI prompts privately for a password (12+ characters), generates an authenticator enrollment secret, and requires a valid TOTP code before creating the administrator. Enroll using your authenticator's manual-entry option; protect the displayed secret. There is no default account or public registration. Keep `MFA_ENCRYPTION_KEY` outside the database and back it up securely; losing it prevents MFA decryption. Never commit `.env`.

Caddy serves HTTPS at the configured `SITE_ADDRESS` (default `localhost`, using Caddy's local CA). For production, set a real DNS hostname and matching `PUBLIC_URL=https://…`, point DNS at the host, and allow ports 80/443 for certificate issuance. Trust Caddy's local CA when testing locally. The web container also exposes HTTP on **127.0.0.1:8080 for local diagnostics only**; use HTTPS for normal login because session cookies are secure. PostgreSQL and the API are internal services.

The migration job uses the database owner; the API and worker use the separate `awareguard` NOSUPERUSER/NOBYPASSRLS role. On a new volume `ops/init-db.sh` initializes that role. Changing the app password on an existing volume also requires a coordinated PostgreSQL role-password update; changing `.env` alone does not rotate it. Do not run the app with the database superuser.

## Workflow

1. Create a company with its exact corporate domain; save the authorization document reference and agreed retention period.
2. Add the displayed `_awareguard.<domain>` DNS TXT challenge, then use **Проверить DNS**. A DNS lookup must actually match; there is no verification bypass in the application.
3. Configure the client's approved SMTP relay, TLS mode, sender allowlist, and infrastructure approval. SMTP passwords belong in a separate ignored `.env.smtp`, e.g. `AG_SMTP_CLIENT1=…`; enter only that variable's name in company settings, then recreate API/worker containers after adding the variable. This file is injected only into backend services; the database-owner password in `.env` is not exposed to the API. No SMTP password is stored in the database. Relays must be trusted and client-approved; only the platform administrator can change them.
4. Import a UTF-8 CSV with exact header `full_name,email,department`. Addresses must match the verified company's exact domain. Import is atomic, duplicates are skipped, and a company may contain at most 500 employees. Excluding an employee prevents future delivery; deleting also removes associated historical results and is blocked for active campaigns.
5. Create a draft using one of the three built-in templates and up to 500 included employees. Run a test send to an included employee of that company. Test messages are marked `[TEST]` and do not contribute to statistics.
6. Obtain independent authorization outside the application. Record the second person's name and email, actual confirmation time (after the test), and document reference. The creator/current administrator cannot approve their own campaign. The application records this attestation; it cannot prove an off-platform document is authentic.
7. Start the approved campaign. The worker delivers at most 30 messages/minute/company, checking permissions immediately before every delivery. Inspect results and export CSV. Stop or block a company to prevent subsequent sends.

## Tracking semantics

A random 256-bit token links each recipient to its campaign. A GET from an email scanner never creates a click or training event. The landing page requires a cookie-bound, explicit form submission before recording a **unique confirmed click** and serving the training content. This filters passive scanners, not every possible browser-automation scanner; validate scanner behavior with each client's mail infrastructure. The service never asks recipients for passwords, OTPs, or other secrets. No IP addresses or user-agent strings are persisted as tracking events.

Click Rate = unique sent recipients with a confirmed click / successfully sent messages × 100. The dashboard's totals are campaign participations (an employee in two campaigns counts twice). Tracking expires at the company's retention deadline and stops when the company is blocked or the campaign stopped. Training events mean the training response was served, not proof the content was read.

## Delivery, stopping, and failure behavior

A dedicated worker claims a recipient durably before contacting SMTP. SMTP acceptance produces `email_sent`; rejection produces `email_failed`. No automatic resend occurs after ambiguous relay acceptance or an interrupted worker. Such recipients remain `dispatching`, and the campaign ends `Failed` once pending recipients are exhausted; reconcile against relay logs before creating a replacement campaign. Advisory locks serialize workers per company; database locks coordinate settings changes, exclusion, retention, and stopping. A stop may wait for the current SMTP operation (15-second timeout per socket operation); an accepted in-flight message cannot be recalled. Once the stop request succeeds, no next message starts. Completed campaigns can still receive tracking events until their retention deadline.

## Development

```sh
make install
# Use a disposable local PostgreSQL 16 database, create the runtime role, then:
cd backend
DATABASE_URL='postgresql+psycopg://awareguard:…@localhost/awareguard' \
MIGRATION_DATABASE_URL='postgresql+psycopg://postgres:…@localhost/awareguard' \
../.venv/bin/alembic upgrade head
# Set DATABASE_URL, MFA_ENCRYPTION_KEY, PUBLIC_URL=http://127.0.0.1:5173,
# COOKIE_SECURE=false, and (only for a local test relay) SMTP_ALLOW_INSECURE=true.
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
# In another terminal, from repository root:
npm run dev --prefix frontend
```

Vite proxies API and training routes to port 8000. Production uses same-origin Nginx behind Caddy; no permissive CORS policy is installed. Do not expose the development server publicly. OpenAPI documentation is available at `/docs` on the API service (route descriptions only; administrative operations still require authentication).

## Verification

Run `make test` to create an isolated PostgreSQL container on a random loopback port, apply all migrations, run the integration suite, and remove that container automatically. It never targets your application database.

**Integration tests delete data. Run only against a disposable database.** They use PostgreSQL, the real restricted application role, and a local in-process SMTP protocol server. DNS TXT answers are mocked; tests never send outside the local relay. Set `DATABASE_URL` to the disposable runtime-role URL and `TEST_ADMIN_DATABASE_URL` to its owner URL, migrate it first, then run:

```sh
cd backend
../.venv/bin/python -m pytest -q
# From repository root:
npm run build --prefix frontend
npm audit --prefix frontend
.venv/bin/pip-audit -r backend/requirements.txt
```

The suite covers a 100-person import, deduplication, atomic validation and 500-person limits, independent approval, SMTP delivery/failure, scanning vs confirmation, idempotent clicks, statistics/CSV consistency, CSV formula escaping, stopping/exclusion/blocking, expiry, session/MFA/CSRF rules, database RLS, and cross-company foreign-key enforcement. Install `pip-audit` separately as a developer tool. See [operations and security](docs/OPERATIONS.md) for deployment prerequisites and verification boundaries.

### Browser smoke test

The checked-in Playwright test exercises real form interactions, CSV upload, draft creation, result viewing, CSV download, template preview, and the responsive training page. Use a disposable local PostgreSQL database initialized with the test credentials in `backend/tests/conftest.py` (never production):

```sh
AWAREGUARD_DISPOSABLE_TEST=1 .venv/bin/python ops/prepare-browser-test.py
# Start uvicorn with --env-file ../.env.development and Vite as above, then:
npm run test:e2e --prefix frontend
```

The helper resets only the hardcoded local test database, creates an ephemeral administrator, and writes credentials to a private `/tmp` file. It does not install a default account in production. The test uses system Chromium (`CHROMIUM_PATH` override available), or adjust the Playwright configuration for your installed browser. Test data uses `example.com` and remains unverified, so it cannot send a campaign. Production starts with an empty database and requires administrator enrollment.
