"""A single delivery worker. No automatic retry of ambiguous SMTP results."""

import logging
import time
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select, text

from .config import settings
from .db import Session, engine, scope
from .mail import deliver, require_ready
from .models import Audit, Campaign, Company, Employee, Event, Recipient, Template, now

log = logging.getLogger(__name__)


def process_one(company_id):
    # A session advisory lock survives the claim transaction and serializes
    # multiple workers without holding the stop/company lock between phases.
    with engine.connect() as connection:
        locked = connection.scalar(
            text("SELECT pg_try_advisory_lock(hashtextextended(:id,0))"),
            {"id": company_id},
        )
        connection.commit()
        if not locked:
            return False
        try:
            return _process_one(company_id, connection)
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:id,0))"),
                {"id": company_id},
            )
            connection.commit()


def _process_one(company_id, connection):
    with Session(bind=connection) as db:
        scope(db, company_id)
        # Serialize workers per company; stop/block transactions use the same lock.
        company = db.scalar(
            select(Company)
            .where(Company.id == company_id)
            .with_for_update(skip_locked=True)
        )
        if not company:
            return False
        campaign = db.scalar(
            select(Campaign)
            .where(
                Campaign.company_id == company_id,
                Campaign.status == "Running",
                Campaign.next_send_at <= now(),
            )
            .order_by(Campaign.created_at)
            .with_for_update(skip_locked=True)
        )
        if not campaign:
            return False
        recipient = db.scalar(
            select(Recipient)
            .where(
                Recipient.campaign_id == campaign.id, Recipient.delivery == "pending"
            )
            .order_by(Recipient.id)
            .with_for_update(skip_locked=True)
        )
        if not recipient:
            ambiguous = db.scalar(
                select(Recipient.id).where(
                    Recipient.campaign_id == campaign.id,
                    Recipient.delivery == "dispatching",
                )
            )
            campaign.status = "Failed" if ambiguous else "Completed"
            if ambiguous:
                campaign.error = "Interrupted delivery: relay acceptance is unknown. Inspect relay logs; no automatic retry."
            db.commit()
            return True
        # Persist a claim BEFORE SMTP: a worker crash never automatically resends
        # a message whose relay acceptance may be unknown.
        recipient.delivery = "dispatching"
        db.commit()
        scope(db, company_id)
        company = db.scalar(
            select(Company)
            .where(Company.id == company_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        db.refresh(campaign)
        db.refresh(recipient)
        if campaign.status != "Running":
            recipient.delivery = "cancelled"
            db.commit()
            return True
        employee = db.get(Employee, recipient.employee_id)
        try:
            require_ready(db, company)
            if (
                not employee
                or employee.company_id != company.id
                or employee.excluded
                or employee.email.rsplit("@", 1)[-1] != company.domain
            ):
                raise HTTPException(
                    409, "Получатель исключён или вне подтверждённого домена"
                )
        except HTTPException as exc:
            campaign.status = "Stopped"
            campaign.error = str(exc.detail)
            recipient.delivery = "cancelled"
            db.add(
                Audit(
                    company_id=company.id,
                    actor="worker",
                    action="campaign.permission_stop",
                    detail=campaign.id,
                )
            )
            db.commit()
            return True
        # Locks stay held through SMTP. A stop waits for at most the in-flight send;
        # after stop returns no next message can start.
        try:
            deliver(
                company,
                employee.email,
                employee.full_name,
                db.get(Template, campaign.template_id),
                f"{settings.public_url}/t/{recipient.token}",
            )
            recipient.delivery = "sent"
            recipient.sent_at = now()
            kind = "email_sent"
        except Exception:
            recipient.delivery = "failed"
            recipient.error = (
                "SMTP delivery failed; inspect relay logs before any manual retry."
            )
            kind = "email_failed"
            log.warning("SMTP failed for recipient id %s", recipient.id)
        db.add(
            Event(
                company_id=company_id,
                campaign_id=campaign.id,
                employee_id=employee.id,
                kind=kind,
            )
        )
        campaign.next_send_at = now() + timedelta(
            seconds=2
        )  # maximum 30 messages/minute/company
        db.commit()
        return True


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            with Session() as db:
                db.execute(
                    text("SELECT set_config('app.platform_admin', 'true', true)")
                )
                ids = list(db.scalars(select(Company.id)))
            for company_id in ids:
                process_one(company_id)
        except Exception:
            log.exception("Worker iteration failed")
        time.sleep(1)


if __name__ == "__main__":
    main()
