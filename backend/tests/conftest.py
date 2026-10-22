import os
import socketserver
import threading

import pyotp
import pytest
from cryptography.fernet import Fernet

os.environ["MFA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://awareguard:local-app-test-only@127.0.0.1:5432/awareguard",
)
os.environ.setdefault(
    "TEST_ADMIN_DATABASE_URL",
    "postgresql+psycopg://postgres:local-test-only@127.0.0.1:5432/awareguard",
)
os.environ["COOKIE_SECURE"] = "false"
os.environ["SMTP_ALLOW_INSECURE"] = "true"
os.environ["PUBLIC_URL"] = "http://testserver"
from app.db import Session
from app.main import app
from app.models import Admin
from app.security import encrypt_mfa, hasher, limits


class SMTPHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b"220 local test relay\r\n")
        while line := self.rfile.readline():
            cmd = line.decode(errors="replace").strip().upper()
            if cmd.startswith(("EHLO", "HELO")):
                self.wfile.write(b"250-localhost\r\n250 SIZE 1000000\r\n")
            elif cmd.startswith("DATA"):
                self.wfile.write(b"354 Send message\r\n")
                parts = []
                while (part := self.rfile.readline()) not in (b".\r\n", b""):
                    parts.append(part)
                self.server.messages.append(b"".join(parts))
                self.wfile.write(b"250 Accepted\r\n")
            elif cmd.startswith("QUIT"):
                self.wfile.write(
                    f"{getattr(self.server, 'quit_code', 221)} Bye\r\n".encode()
                )
                break
            else:
                self.wfile.write(b"250 OK\r\n")


@pytest.fixture
def smtp():
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), SMTPHandler)
    server.messages = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def client():
    engine = create_engine(os.environ["TEST_ADMIN_DATABASE_URL"])
    with engine.begin() as db:
        db.execute(text("TRUNCATE companies, admin_users, audit_logs CASCADE"))
    engine.dispose()
    limits.clear()
    with Session() as db:
        db.add(
            Admin(
                email="admin@platform.example.com",
                password_hash=hasher.hash("Test-only-long-password"),
                mfa_secret=encrypt_mfa("JBSWY3DPEHPK3PXP"),
            )
        )
        db.commit()
    with TestClient(app) as c:
        r = c.post(
            "/api/auth/login",
            json={
                "email": "admin@platform.example.com",
                "password": "Test-only-long-password",
                "otp": pyotp.TOTP("JBSWY3DPEHPK3PXP").now(),
            },
        )
        assert r.status_code == 200, r.text
        c.headers["X-CSRF-Token"] = r.json()["csrf"]
        yield c
