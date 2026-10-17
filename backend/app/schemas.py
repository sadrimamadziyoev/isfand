import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)
    otp: str = Field(pattern=r"^\d{6}$")


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=3, max_length=253)
    authorization: str = Field(default="", max_length=10000)
    infrastructure_approved: bool = False
    smtp_host: str = Field(default="", max_length=253)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = Field(default="", max_length=200)
    smtp_secret_env: str = Field(
        default="", max_length=100, pattern=r"^(|AG_SMTP_[A-Z0-9_]+)$"
    )
    smtp_tls: str = Field(default="starttls", pattern=r"^(starttls|ssl|none)$")
    sender: str = Field(default="", max_length=254)
    approved_senders: list[EmailStr] = Field(default_factory=list, max_length=20)
    retention_days: int = Field(default=90, ge=1, le=365)

    @field_validator("domain")
    @classmethod
    def domain_valid(cls, v):
        v = v.strip().lower().encode("idna").decode()
        if not re.fullmatch(
            r"(?=.{3,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", v
        ):
            raise ValueError("Invalid corporate domain")
        return v

    @field_validator("smtp_host")
    @classmethod
    def host_valid(cls, v):
        if v and not re.fullmatch(r"[a-zA-Z0-9.-]+", v):
            raise ValueError("Invalid SMTP host")
        return v

    @field_validator("sender")
    @classmethod
    def sender_valid(cls, v):
        if v:
            from email_validator import validate_email

            return validate_email(v, check_deliverability=False).normalized.lower()
        return v


class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company_id: str
    template_id: str
    employee_ids: list[str] = Field(min_length=1, max_length=500)


class ApprovalIn(BaseModel):
    approver_name: str = Field(min_length=2, max_length=200)
    approver_email: EmailStr
    approved_at: datetime
    document: str = Field(min_length=10, max_length=10000)
    independent_confirmation: bool


class TestIn(BaseModel):
    email: EmailStr


class ExcludeIn(BaseModel):
    excluded: bool
