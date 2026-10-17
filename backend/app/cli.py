import argparse
import getpass
from datetime import timedelta

import pyotp
from sqlalchemy import delete, select, text

from .db import Session, scope
from .models import Admin, AdminSession, Audit, Campaign, Company, Employee, now
from .security import encrypt_mfa, hasher


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create-admin", "purge"])
    parser.add_argument("--email")
    args = parser.parse_args()
    with Session() as db:
        if args.command == "create-admin":
            from email_validator import validate_email

            email = validate_email(
                args.email or input("Admin email: "), check_deliverability=False
            ).normalized.lower()
            if db.scalar(select(Admin.id).where(Admin.email == email)):
                raise SystemExit("Admin already exists")
            password = getpass.getpass("Password (minimum 12 characters): ")
            if len(password) < 12:
                raise SystemExit("Password too short")
            secret = pyotp.random_base32()
            print("Enroll this secret in your authenticator (store securely):", secret)
            print(pyotp.TOTP(secret).provisioning_uri(email, issuer_name="AwareGuard"))
            code = input("Enter authenticator code to confirm enrollment: ").strip()
            if not pyotp.TOTP(secret).verify(code, valid_window=1):
                raise SystemExit("Invalid MFA code")
            db.add(
                Admin(
                    email=email,
                    password_hash=hasher.hash(password),
                    mfa_secret=encrypt_mfa(secret),
                )
            )
            db.commit()
            print("Administrator created")
        else:
            db.execute(text("SELECT set_config('app.platform_admin', 'true', true)"))
            for c in db.scalars(select(Company)).all():
                scope(db, c.id)
                db.execute(select(Company).where(Company.id == c.id).with_for_update())
                # Never purge a running campaign. Stop it before retention cleanup.
                expired = list(
                    db.scalars(
                        select(Campaign).where(
                            Campaign.company_id == c.id,
                            Campaign.created_at
                            < now() - timedelta(days=c.retention_days),
                        )
                    )
                )
                for campaign in expired:
                    db.delete(campaign)
                db.flush()
                from .models import Recipient

                for e in db.scalars(
                    select(Employee).where(
                        Employee.company_id == c.id,
                        Employee.created_at < now() - timedelta(days=c.retention_days),
                    )
                ).all():
                    if not db.scalar(
                        select(Recipient.id).where(Recipient.employee_id == e.id)
                    ):
                        db.delete(e)
                db.execute(
                    delete(Audit).where(
                        Audit.company_id == c.id,
                        Audit.created_at < now() - timedelta(days=c.retention_days),
                    )
                )
            db.execute(delete(AdminSession).where(AdminSession.expires_at < now()))
            db.commit()
            print("Expired personal data purged")


if __name__ == "__main__":
    main()
