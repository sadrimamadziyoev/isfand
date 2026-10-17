import hashlib
import os
import secrets
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from sqlalchemy import text

from .db import get_db
from .models import Admin, AdminSession, Audit, now

hasher = PasswordHasher()
DUMMY = hasher.hash(secrets.token_urlsafe(32))
limits = defaultdict(deque)


def mfa_cipher():
    return Fernet(os.environ["MFA_ENCRYPTION_KEY"].encode())


def encrypt_mfa(value):
    return mfa_cipher().encrypt(value.encode()).decode()


def decrypt_mfa(value):
    return mfa_cipher().decrypt(value.encode()).decode()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def rate_limit(key, maximum=20, seconds=60):
    current = time.monotonic()
    # Bound memory used by anonymous clients.
    if len(limits) > 10000:
        for k in list(limits):
            if not limits[k] or limits[k][-1] < current - 300:
                limits.pop(k, None)
        if len(limits) > 10000:
            raise HTTPException(429, "Слишком много запросов")
    q = limits[key]
    while q and q[0] < current - seconds:
        q.popleft()
    if len(q) >= maximum:
        raise HTTPException(429, "Слишком много запросов. Повторите позже.")
    q.append(current)


def authenticate(request: Request, db=Depends(get_db)):
    token = request.cookies.get("ag_session", "")
    session = db.get(AdminSession, digest(token)) if token else None
    if not session or session.expires_at <= now():
        raise HTTPException(401, "Необходим вход")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not secrets.compare_digest(
            request.headers.get("X-CSRF-Token", ""), session.csrf
        ):
            raise HTTPException(403, "Недействительный CSRF-токен")
    admin = db.get(Admin, session.admin_id)
    if not admin:
        raise HTTPException(401, "Необходим вход")
    db.execute(text("SELECT set_config('app.platform_admin', 'true', true)"))
    request.state.session = session
    return admin


def audit(db, admin, action, company_id=None, detail=""):
    db.add(
        Audit(
            actor=admin.email if hasattr(admin, "email") else admin,
            action=action,
            company_id=company_id,
            detail=detail,
        )
    )
