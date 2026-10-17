"""Destructive setup for the LOCAL disposable test database only."""

import json
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import pyotp
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text

root = Path(__file__).resolve().parent.parent
from dotenv import dotenv_values

key = (
    dotenv_values(root / ".env.development").get("MFA_ENCRYPTION_KEY")
    or Fernet.generate_key().decode()
)
os.environ["MFA_ENCRYPTION_KEY"] = key
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://awareguard:local-app-test-only@127.0.0.1:5432/awareguard"
)
if os.getenv("AWAREGUARD_DISPOSABLE_TEST") != "1":
    raise SystemExit(
        "Set AWAREGUARD_DISPOSABLE_TEST=1 to reset the local disposable test database."
    )
engine = create_engine(
    "postgresql+psycopg://postgres:local-test-only@127.0.0.1:5432/awareguard"
)
with engine.begin() as db:
    db.execute(text("TRUNCATE companies,admin_users,audit_logs CASCADE"))
from app.db import Session
from app.models import Admin
from app.security import encrypt_mfa, hasher

password = secrets.token_urlsafe(24)
mfa = pyotp.random_base32()
email = "browser-admin@example.com"
with Session() as db:
    db.add(
        Admin(
            email=email,
            password_hash=hasher.hash(password),
            mfa_secret=encrypt_mfa(mfa),
        )
    )
    db.commit()
auth = Path("/tmp/awareguard-e2e-auth.json")
auth.write_text(json.dumps({"email": email, "password": password, "mfa": mfa}))
auth.chmod(0o600)
config = root / ".env.development"
config.write_text(
    f"DATABASE_URL={os.environ['DATABASE_URL']}\nMFA_ENCRYPTION_KEY={key}\nPUBLIC_URL=http://127.0.0.1:5173\nCOOKIE_SECURE=false\nSMTP_ALLOW_INSECURE=true\n"
)
config.chmod(0o600)
print(
    "Disposable browser-test account and local runtime configuration prepared. No credentials printed."
)
