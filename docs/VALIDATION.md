# Validation record — 2026-10-17

Verified in the cloud workspace with Python 3.12, Node 24, PostgreSQL 16, and system Chromium:

- **12 PostgreSQL integration tests passed.** `ops/test.sh` created a fresh disposable container on a random loopback port, applied migrations 001–004, ran the tests using the restricted runtime role, then removed that container.
- **1 Playwright workflow passed.** Real MFA login, company creation, two-person CSV import, draft creation, approval disabled until a test send, results drawer, CSV download, sandboxed template preview, mobile layout, and public training page. Browser data used unverified example.com addresses; no real recipients were contacted.
- **Production frontend build passed** (TypeScript + Vite). Vite reports a large-bundle warning; the application is functional, but further route/chunk splitting would improve initial-load performance.
- **Backend lint passed** with the checked-in Ruff configuration. The test runner reports a Starlette/httpx deprecation warning, not a failing test.
- **Both Docker images built** using verified TLS and hash-locked Python/npm dependencies. The corporate build-proxy CA was supplied as a BuildKit secret, without disabling TLS verification.
- **Compose cold startup passed** on an empty database: initial restricted role, migrations, healthy API/database, Nginx, delivery worker, retention process, and Caddy gateway.
- **HTTPS functional smoke checks passed** with Caddy's local CA explicitly trusted: database-backed health, app HTML, production JS/CSS assets, and the training page. The gateway excludes internal Docker service names from an inherited outbound proxy.
- **Backup and restore passed:** a custom-format dump restored into a separate database; three templates and forced recipient RLS were confirmed. The temporary restore database was removed.
- **Dependency audits:** pip-audit of `backend/requirements.lock` and npm audit reported zero known advisories at validation time. This is time-sensitive, not a guarantee of future vulnerability status.
- **Privilege check:** the API container has no database-owner password binding. MFA and SMTP secrets are not committed.

## Boundaries

DNS TXT lookup is mocked in automated tests. SMTP protocol delivery is exercised against a local relay; tests do not establish connectivity, deliverability, SPF/DKIM/DMARC configuration, or permissions for any real client's infrastructure. The browser workflow runs against the local development API/Vite server; deployment smoke checks separately verify HTTPS and static/API routing. Production has no seeded administrator or sample companies.

No real email campaign, public deployment, penetration test, OS/container-image vulnerability scan, or environment publication is claimed. Those release checks and client approvals remain prerequisites for a real pilot. See OPERATIONS.md for configuration, retention, logging, and delivery limitations.
