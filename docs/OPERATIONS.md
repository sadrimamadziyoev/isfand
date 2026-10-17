# Operations and security

## Isolation and authentication

Every tenant-owned domain, employee, campaign, recipient, event, and company-scoped audit row is filtered by a transaction-local `app.company_id` PostgreSQL setting with **FORCE ROW LEVEL SECURITY**. Composite foreign keys also prevent assigning a recipient/event to another company's campaign or employee. The company directory has a separate policy allowing the authenticated Platform Administrator to enumerate companies; there are no client accounts. A narrowly scoped SECURITY DEFINER function resolves only a tenant ID from a random token hash for public tracking. Migration functions must be owned by the database owner; do not grant the runtime role BYPASSRLS. RLS is a defense against missing application filters, not against a compromised runtime-role connection that can set its own tenant context.

Opaque session tokens are hashed in PostgreSQL, last eight hours, and use HttpOnly/Secure/SameSite=Strict cookies. Mutations require a per-session CSRF header. Passwords use Argon2id. MFA secrets use Fernet authenticated encryption with an external key, and TOTP code reuse is rejected. There is no password-recovery interface: an authorized operator must use a controlled database/CLI procedure to revoke sessions and reenroll an administrator. Back up before performing account maintenance.

Login/public/test/DNS request limits are process-local with bounded keys. Production is intentionally configured for **one API process**; if scaling horizontally, replace these limits with a shared store and trusted edge policy first. The application does not trust arbitrary X-Forwarded-For. Place the service behind the supplied gateway; direct container ports must remain private. Gateway request-size limits and the application CSV limit bound uploads. Mail content is fixed; user names are HTML-escaped, the template preview is sandboxed, React escapes administrative data, CSV exports protect spreadsheet formula prefixes, and API responses use anti-framing and content-type headers.

## Backups and retention

Run `./ops/backup.sh` on a schedule (e.g. daily). It produces a private PostgreSQL custom-format dump under ignored `backups/`. Copy backups to encrypted, access-controlled off-host storage, define retention with clients, and periodically test restoration into an isolated database:

```sh
# Use an empty restore database, never a live production database.
docker compose exec -T db pg_restore -U postgres -d awareguard_restore --no-owner < backups/<file>.dump
```

Back up `.env`/MFA encryption key separately using a secret manager; do not put keys in database dumps. Treat SMTP credentials, recipient tracking tokens, exports, dumps, and audit records as sensitive. Disable request-path logging for tracking URLs at any external proxy; API access logging is disabled by default. Do not add analytics to training pages.

The retention container runs `python -m app.cli purge` daily. It deletes expired campaigns and their recipients/events, then expired employees with no retained campaign participation, company-scoped audit entries past the agreed deadline, and expired sessions. Retention locks the company against concurrent sends. Purging expired running campaigns cancels their unsent work. Domain authorization/company settings remain until a separate authorized company-data deletion; they do not contain employee results. Backup expiry must be managed separately; application deletion does not erase old backups automatically.

## Before a real pilot

The repository implements the product workflow; deploying it is not evidence a corporate pilot has been authorized or security-reviewed. Configure a real TLS hostname, trusted approved SMTP relay and credential, client sender allowlist, domain TXT proof, written authorization, retention/backups, and the independent approval process. Confirm SPF/DKIM/DMARC and mail-scanner behavior with the client's IT team. Do not use a relay or sender without agreement. No messages are sent automatically just by starting the application.

Run dependency and container-image vulnerability scans, the integration suite against the restricted PostgreSQL role, and a deployment-specific security review. Check TLS trust, DNS, SMTP authentication/allowlists, backup restore, worker restart/ambiguous delivery handling, isolation and deletion behavior. The project's automated tests are not a penetration test and cannot establish the absence of all high/critical vulnerabilities. Local SMTP and mocked DNS verification do not prove a client's infrastructure works.

## Corporate build proxies

Both Docker builds accept an optional BuildKit secret named `build_ca`. Compose supplies the operator's CA bundle from `BUILD_CA_CERT` (defaults to `/etc/ssl/certs/ca-certificates.crt`). On a non-Linux host, set this to an existing PEM CA-bundle path. Python uses that bundle for pip TLS verification; Node adds it to its trusted roots during npm installation. The bundle is not embedded in the final image. Use only your organization's trusted CA bundle, never disable certificate validation. Python packages are hash-locked in `backend/requirements.lock`; npm uses `package-lock.json` with `npm ci`.
