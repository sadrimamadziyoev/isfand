"""Create a local .env without overwriting existing configuration."""

import json
import os
import secrets
import ssl
from pathlib import Path

from cryptography.fernet import Fernet


def build_ca_path():
    """Use an explicit trusted bundle, or discover one on Linux/macOS."""
    explicit = os.environ.get("BUILD_CA_CERT")
    candidates = (
        [explicit]
        if explicit
        else [
            ssl.get_default_verify_paths().cafile,
            "/etc/ssl/certs/ca-certificates.crt",
            "/etc/ssl/cert.pem",
        ]
    )
    for candidate in candidates:
        if candidate:
            path = Path(candidate).expanduser().absolute()
            if path.is_file():
                return path
    raise SystemExit(
        "No CA bundle found. Set BUILD_CA_CERT to an existing trusted PEM CA bundle."
    )


def configure(root):
    path = root / ".env"
    if path.exists():
        raise SystemExit(".env exists; edit it without replacing existing secrets.")
    ca_path = build_ca_path()
    content = f"""POSTGRES_PASSWORD={secrets.token_urlsafe(32)}
APP_DB_PASSWORD={secrets.token_urlsafe(32)}
MFA_ENCRYPTION_KEY={Fernet.generate_key().decode()}
BUILD_CA_CERT={json.dumps(str(ca_path))}
SITE_ADDRESS=localhost
PUBLIC_URL=https://localhost
COOKIE_SECURE=true
SMTP_ALLOW_INSECURE=false
"""
    # Exclusive creation preserves an existing configuration even if another
    # setup process creates it after the existence check.
    with open(
        path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)
    ) as file:
        file.write(content)
    print("Created .env. Configure SITE_ADDRESS and PUBLIC_URL before production.")


if __name__ == "__main__":
    configure(Path(__file__).resolve().parent.parent)
