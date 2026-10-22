import html
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

from fastapi import HTTPException
from sqlalchemy import select

from .config import settings
from .models import Domain

log = logging.getLogger(__name__)


def require_ready(db, company):
    domain = db.scalar(select(Domain).where(Domain.company_id == company.id))
    if company.blocked:
        raise HTTPException(409, "Компания заблокирована")
    if not domain or not domain.verified_at:
        raise HTTPException(409, "Сначала подтвердите DNS-домен")
    if not company.authorization.strip():
        raise HTTPException(409, "Не сохранено подтверждение полномочий")
    if not company.infrastructure_approved:
        raise HTTPException(409, "Почтовая инфраструктура не согласована")
    if (
        not company.smtp_host
        or not company.sender
        or company.sender not in company.approved_senders
    ):
        raise HTTPException(409, "Не согласован SMTP-релей или отправитель")
    if company.sender.rsplit("@", 1)[-1].lower() != company.domain:
        raise HTTPException(409, "Отправитель вне домена компании")
    if company.smtp_tls == "none" and not settings.smtp_allow_insecure:
        raise HTTPException(409, "SMTP требует TLS")
    if company.smtp_user and (
        not company.smtp_secret_env or not os.getenv(company.smtp_secret_env)
    ):
        raise HTTPException(409, "Не задан секрет SMTP в окружении")


def deliver(company, to, name, template, link, test=False):
    # Only built-in HTML; names and URLs are escaped before substitution.
    body = template.html.format(
        name=html.escape(name), link=html.escape(link, quote=True)
    )
    message = EmailMessage()
    message["From"] = company.sender
    message["To"] = to
    message["Subject"] = ("[TEST] " if test else "") + template.subject
    message.set_content(
        f"Здравствуйте, {name}!\nВнутреннее учебное уведомление: {link}"
    )
    message.add_alternative(body, subtype="html")
    cls = smtplib.SMTP_SSL if company.smtp_tls == "ssl" else smtplib.SMTP
    kwargs = {"host": company.smtp_host, "port": company.smtp_port, "timeout": 15}
    if company.smtp_tls == "ssl":
        kwargs["context"] = ssl.create_default_context()
    smtp = cls(**kwargs)
    try:
        if company.smtp_tls == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if company.smtp_user:
            smtp.login(company.smtp_user, os.environ[company.smtp_secret_env])
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    finally:
        # SMTP acceptance is determined by DATA, not by the later QUIT reply.
        # Cleanup must neither turn an accepted message into a failure nor mask
        # the original TLS/authentication/delivery exception.
        try:
            code, _ = smtp.quit()
            if code != 221:
                log.warning("SMTP relay returned an unexpected QUIT status")
        except (OSError, smtplib.SMTPException):
            log.warning("SMTP connection cleanup failed")
        finally:
            try:
                smtp.close()
            except (OSError, smtplib.SMTPException):
                log.warning("SMTP connection close failed")
