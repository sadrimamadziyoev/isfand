import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://awareguard:awareguard@localhost:5432/awareguard",
    )
    public_url: str = os.getenv("PUBLIC_URL", "https://localhost")
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    smtp_allow_insecure: bool = (
        os.getenv("SMTP_ALLOW_INSECURE", "false").lower() == "true"
    )
    session_hours: int = 8


settings = Settings()
