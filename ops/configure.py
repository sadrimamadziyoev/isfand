"""Create a local .env without overwriting existing configuration."""

import secrets
from pathlib import Path

from cryptography.fernet import Fernet

root = Path(__file__).resolve().parent.parent
path = root / ".env"
if path.exists():
    raise SystemExit(".env exists; edit it without replacing existing secrets.")
content = f"""POSTGRES_PASSWORD={secrets.token_urlsafe(32)}
APP_DB_PASSWORD={secrets.token_urlsafe(32)}
MFA_ENCRYPTION_KEY={Fernet.generate_key().decode()}
SITE_ADDRESS=localhost
PUBLIC_URL=https://localhost
COOKIE_SECURE=true
SMTP_ALLOW_INSECURE=false
"""
path.write_text(content)
path.chmod(0o600)
print("Created .env. Configure SITE_ADDRESS and PUBLIC_URL before production.")
