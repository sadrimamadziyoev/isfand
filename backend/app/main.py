import csv
import html
import io
import re
import secrets
from contextlib import asynccontextmanager
from datetime import timedelta

import dns.resolver
import pyotp
from argon2.exceptions import VerificationError
from email_validator import EmailNotValidError, validate_email
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select, text

from .config import settings
from .db import get_db, scope
from .mail import deliver, require_ready
from .models import (
    Admin,
    AdminSession,
    Audit,
    Campaign,
    Company,
    Domain,
    Employee,
    Event,
    Recipient,
    Template,
    now,
)
from .schemas import ApprovalIn, CampaignIn, CompanyIn, ExcludeIn, LoginIn, TestIn
from .security import (
    DUMMY,
    audit,
    authenticate,
    decrypt_mfa,
    digest,
    hasher,
    mfa_cipher,
    rate_limit,
)


@asynccontextmanager
async def lifespan(app):
    mfa_cipher()  # Refuse startup without a valid, external encryption key.
    if settings.cookie_secure and not settings.public_url.startswith("https://"):
        raise RuntimeError("PUBLIC_URL must use HTTPS when secure cookies are enabled")
    yield


app = FastAPI(title="AwareGuard", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'"
    )
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


def company_get(db, company_id, lock=False):
    scope(db, company_id)
    q = select(Company).where(Company.id == company_id)
    if lock:
        q = q.with_for_update()
    company = db.scalar(q)
    if not company:
        raise HTTPException(404, "Компания не найдена")
    return company


def campaign_get(db, company_id, campaign_id, lock=False):
    company_get(db, company_id, lock)
    q = select(Campaign).where(
        Campaign.id == campaign_id, Campaign.company_id == company_id
    )
    if lock:
        q = q.with_for_update()
    c = db.scalar(q)
    if not c:
        raise HTTPException(404, "Кампания не найдена")
    return c


def company_out(db, c):
    scope(db, c.id)
    d = db.scalar(select(Domain).where(Domain.company_id == c.id))
    return {
        k: getattr(c, k)
        for k in [
            "id",
            "name",
            "domain",
            "authorization",
            "infrastructure_approved",
            "blocked",
            "smtp_host",
            "smtp_port",
            "smtp_user",
            "smtp_secret_env",
            "smtp_tls",
            "sender",
            "approved_senders",
            "retention_days",
        ]
    } | {
        "domain_verified": bool(d and d.verified_at),
        "dns_record": f"_awareguard.{c.domain}",
        "dns_value": d.challenge if d else "",
        "employees": db.scalar(
            select(func.count())
            .select_from(Employee)
            .where(Employee.company_id == c.id)
        ),
    }


def campaign_out(c):
    return {
        k: getattr(c, k)
        for k in [
            "id",
            "company_id",
            "name",
            "template_id",
            "status",
            "created_at",
            "created_by",
            "test_sent_at",
            "approved_by",
            "approver_name",
            "approved_at",
            "approval_document",
            "error",
        ]
    }


@app.get("/api/health")
def health(db=Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(data: LoginIn, request: Request, response: Response, db=Depends(get_db)):
    rate_limit(("login", request.client.host), 5, 300)
    email = str(data.email).lower()
    rate_limit(("account", email), 10, 300)
    admin = db.scalar(select(Admin).where(Admin.email == email))
    valid = False
    try:
        valid = hasher.verify(admin.password_hash if admin else DUMMY, data.password)
    except VerificationError:
        pass
    if (
        not admin
        or not valid
        or not pyotp.TOTP(decrypt_mfa(admin.mfa_secret)).verify(
            data.otp, valid_window=1
        )
    ):
        audit(db, email, "auth.failed")
        db.commit()
        raise HTTPException(401, "Неверные данные или код MFA")
    # Reject reuse of a TOTP time step across sessions.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:email))"), {"email": email})
    if db.scalar(
        select(Audit.id).where(
            Audit.actor == email,
            Audit.action == "auth.login",
            Audit.created_at > now() - timedelta(seconds=90),
            Audit.detail == digest(data.otp),
        )
    ):
        raise HTTPException(401, "Этот код уже использован. Дождитесь нового кода.")
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    db.add(
        AdminSession(
            id=digest(token),
            admin_id=admin.id,
            csrf=csrf,
            expires_at=now() + timedelta(hours=settings.session_hours),
        )
    )
    audit(db, admin, "auth.login", detail=digest(data.otp))
    response.set_cookie(
        "ag_session",
        token,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    return {"email": admin.email, "csrf": csrf}


@app.get("/api/auth/me")
def me(request: Request, admin=Depends(authenticate)):
    return {"email": admin.email, "csrf": request.state.session.csrf}


@app.post("/api/auth/logout")
def logout(
    request: Request,
    response: Response,
    admin=Depends(authenticate),
    db=Depends(get_db),
):
    db.delete(request.state.session)
    audit(db, admin, "auth.logout")
    response.delete_cookie("ag_session", path="/")
    return {"ok": True}


@app.get("/api/companies")
def companies(admin=Depends(authenticate), db=Depends(get_db)):
    return [
        company_out(db, c)
        for c in db.scalars(select(Company).order_by(Company.created_at.desc())).all()
    ]


@app.post("/api/companies", status_code=201)
def create_company(data: CompanyIn, admin=Depends(authenticate), db=Depends(get_db)):
    if db.scalar(select(Company.id).where(Company.domain == data.domain)):
        raise HTTPException(409, "Компания с этим доменом уже существует")
    c = Company(**data.model_dump(mode="json"))
    db.add(c)
    db.flush()
    scope(db, c.id)
    db.add(
        Domain(
            company_id=c.id,
            challenge="awareguard-verification=" + secrets.token_urlsafe(24),
        )
    )
    db.flush()
    audit(db, admin, "company.created", c.id)
    return company_out(db, c)


@app.put("/api/companies/{company_id}")
def update_company(
    company_id: str, data: CompanyIn, admin=Depends(authenticate), db=Depends(get_db)
):
    c = company_get(db, company_id, True)
    if data.domain != c.domain:
        raise HTTPException(409, "Создайте новую компанию для другого домена")
    active = db.scalar(
        select(Campaign.id).where(
            Campaign.company_id == company_id,
            Campaign.status.in_(["Approved", "Running"]),
        )
    )
    if active:
        raise HTTPException(
            409,
            "Остановите утверждённые и запущенные кампании перед изменением настроек",
        )
    for k, v in data.model_dump(mode="json").items():
        setattr(c, k, v)
    for draft in db.scalars(
        select(Campaign).where(Campaign.company_id == c.id, Campaign.status == "Draft")
    ):
        draft.test_sent_at = None
    audit(db, admin, "company.updated", c.id)
    return company_out(db, c)


@app.post("/api/companies/{company_id}/verify-domain")
def verify_domain(company_id: str, admin=Depends(authenticate), db=Depends(get_db)):
    c = company_get(db, company_id, True)
    rate_limit(("dns", c.id), 5, 60)
    d = db.scalar(select(Domain).where(Domain.company_id == c.id))
    try:
        answers = dns.resolver.resolve(f"_awareguard.{c.domain}", "TXT", lifetime=5)
        values = [b"".join(r.strings).decode() for r in answers]
    except dns.exception.DNSException:
        raise HTTPException(
            422, "TXT-запись пока не найдена. Проверьте DNS и повторите."
        )
    if d.challenge not in values:
        raise HTTPException(422, "TXT-запись не совпадает с кодом подтверждения")
    d.verified_at = now()
    audit(db, admin, "company.domain_verified", c.id)
    return {"verified": True}


@app.post("/api/companies/{company_id}/block")
def block_company(company_id: str, admin=Depends(authenticate), db=Depends(get_db)):
    c = company_get(db, company_id, True)
    c.blocked = True
    for campaign in db.scalars(
        select(Campaign).where(
            Campaign.company_id == c.id,
            Campaign.status.in_(["Draft", "Approved", "Running"]),
        )
    ):
        campaign.status = "Stopped"
    audit(db, admin, "company.blocked", c.id)
    return {"blocked": True}


@app.get("/api/employees")
def employees(company_id: str, admin=Depends(authenticate), db=Depends(get_db)):
    company_get(db, company_id)
    return list(
        db.scalars(
            select(Employee)
            .where(Employee.company_id == company_id)
            .order_by(Employee.full_name)
        )
    )


@app.post("/api/employees/import")
async def import_employees(
    company_id: str = Form(...),
    file: UploadFile = File(...),
    admin=Depends(authenticate),
    db=Depends(get_db),
):
    c = company_get(db, company_id, True)
    raw = await file.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise HTTPException(413, "CSV превышает 1 МБ")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if reader.fieldnames != ["full_name", "email", "department"]:
            raise ValueError("Нужны столбцы full_name,email,department в этом порядке")
        rows = list(reader)
        if len(rows) > 500:
            raise ValueError("Не более 500 строк")
        existing = set(
            db.scalars(select(Employee.email).where(Employee.company_id == c.id))
        )
        seen = set(existing)
        prepared = []
        duplicates = 0
        for number, row in enumerate(rows, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Строка {number}: неверное число столбцов")
            email = validate_email(
                row["email"].strip(), check_deliverability=False
            ).normalized.lower()
            if email.rsplit("@", 1)[-1] != c.domain:
                raise ValueError(f"Строка {number}: email вне домена компании")
            name = row["full_name"].strip()
            dept = row["department"].strip()
            if not name or len(name) > 200 or len(dept) > 200:
                raise ValueError(f"Строка {number}: неверное имя или подразделение")
            if email in seen:
                duplicates += 1
                continue
            seen.add(email)
            prepared.append(
                Employee(company_id=c.id, full_name=name, email=email, department=dept)
            )
        if len(seen) > 500:
            raise ValueError("Лимит компании — 500 сотрудников")
    except (UnicodeDecodeError, ValueError, EmailNotValidError, csv.Error) as exc:
        raise HTTPException(422, str(exc))
    db.add_all(prepared)
    audit(
        db,
        admin,
        "employees.import",
        c.id,
        detail=f"imported={len(prepared)},duplicates={duplicates}",
    )
    return {"imported": len(prepared), "duplicates": duplicates}


@app.patch("/api/employees/{employee_id}")
def exclude(
    employee_id: str,
    company_id: str,
    data: ExcludeIn,
    admin=Depends(authenticate),
    db=Depends(get_db),
):
    company_get(db, company_id, True)
    e = db.scalar(
        select(Employee).where(
            Employee.id == employee_id, Employee.company_id == company_id
        )
    )
    if not e:
        raise HTTPException(404, "Сотрудник не найден")
    e.excluded = data.excluded
    audit(
        db,
        admin,
        "employee.excluded" if data.excluded else "employee.included",
        company_id,
        e.id,
    )
    return {"ok": True}


@app.delete("/api/employees/{employee_id}")
def delete_employee(
    employee_id: str, company_id: str, admin=Depends(authenticate), db=Depends(get_db)
):
    company_get(db, company_id, True)
    e = db.scalar(
        select(Employee).where(
            Employee.id == employee_id, Employee.company_id == company_id
        )
    )
    if not e:
        raise HTTPException(404, "Сотрудник не найден")
    if db.scalar(
        select(Recipient.id)
        .join(Campaign, Recipient.campaign_id == Campaign.id)
        .where(
            Recipient.employee_id == e.id,
            Campaign.status.in_(["Draft", "Approved", "Running"]),
        )
    ):
        raise HTTPException(
            409, "Сотрудник участвует в активной кампании; используйте исключение"
        )
    audit(db, admin, "employee.deleted", company_id, e.id)
    db.delete(e)
    return {"ok": True}


@app.get("/api/templates")
def templates(admin=Depends(authenticate), db=Depends(get_db)):
    return list(db.scalars(select(Template)))


@app.get("/api/campaigns")
def campaigns(company_id: str, admin=Depends(authenticate), db=Depends(get_db)):
    company_get(db, company_id)
    return [
        campaign_out(c)
        for c in db.scalars(
            select(Campaign)
            .where(Campaign.company_id == company_id)
            .order_by(Campaign.created_at.desc())
        )
    ]


@app.post("/api/campaigns", status_code=201)
def create_campaign(data: CampaignIn, admin=Depends(authenticate), db=Depends(get_db)):
    c = company_get(db, data.company_id, True)
    if c.blocked:
        raise HTTPException(409, "Компания заблокирована")
    if not db.get(Template, data.template_id):
        raise HTTPException(422, "Шаблон не найден")
    ids = set(data.employee_ids)
    es = list(
        db.scalars(
            select(Employee).where(
                Employee.company_id == c.id,
                Employee.id.in_(ids),
                Employee.excluded.is_(False),
            )
        )
    )
    if len(es) != len(ids) or any(e.email.rsplit("@", 1)[-1] != c.domain for e in es):
        raise HTTPException(
            422, "В списке есть исключённые сотрудники или сотрудники другой компании"
        )
    campaign = Campaign(
        name=data.name,
        company_id=c.id,
        template_id=data.template_id,
        created_by=admin.email,
    )
    db.add(campaign)
    db.flush()
    for e in es:
        token = secrets.token_urlsafe(32)
        db.add(
            Recipient(
                company_id=c.id,
                campaign_id=campaign.id,
                employee_id=e.id,
                token=token,
                token_hash=digest(token),
            )
        )
    audit(db, admin, "campaign.created", c.id, campaign.id)
    return campaign_out(campaign)


@app.post("/api/campaigns/{campaign_id}/test")
def test_campaign(
    campaign_id: str,
    company_id: str,
    data: TestIn,
    admin=Depends(authenticate),
    db=Depends(get_db),
):
    c = company_get(db, company_id, True)
    campaign = campaign_get(db, company_id, campaign_id)
    if campaign.status != "Draft":
        raise HTTPException(409, "Тест доступен только для черновика")
    require_ready(db, c)
    email = str(data.email).lower()
    if email.rsplit("@", 1)[-1] != c.domain:
        raise HTTPException(422, "Тестовый адрес должен принадлежать компании")
    if not db.scalar(
        select(Employee.id).where(
            Employee.company_id == c.id,
            Employee.email == email,
            Employee.excluded.is_(False),
        )
    ):
        raise HTTPException(422, "Выберите включённого сотрудника компании для теста")
    rate_limit(("test", c.id), 3, 60)
    try:
        deliver(
            c,
            email,
            "Тестовый получатель",
            db.get(Template, campaign.template_id),
            settings.public_url + "/training-preview",
            True,
        )
    except Exception:
        raise HTTPException(
            502, "SMTP не принял тестовое письмо. Проверьте настройки релея."
        )
    campaign.test_sent_at = now()
    audit(db, admin, "campaign.test_sent", c.id, campaign.id)
    return {"sent": True}


@app.post("/api/campaigns/{campaign_id}/approve")
def approve(
    campaign_id: str,
    company_id: str,
    data: ApprovalIn,
    admin=Depends(authenticate),
    db=Depends(get_db),
):
    c = company_get(db, company_id, True)
    campaign = campaign_get(db, company_id, campaign_id)
    require_ready(db, c)
    if campaign.status != "Draft" or not campaign.test_sent_at:
        raise HTTPException(409, "Сначала отправьте тестовое письмо для черновика")
    if not data.independent_confirmation or str(data.approver_email).lower() in (
        admin.email,
        campaign.created_by,
    ):
        raise HTTPException(
            422, "Нужно независимое подтверждение другим уполномоченным лицом"
        )
    if (
        data.approved_at.tzinfo is None
        or data.approved_at > now()
        or data.approved_at < campaign.test_sent_at
    ):
        raise HTTPException(
            422, "Время подтверждения должно быть после теста и не в будущем"
        )
    campaign.status = "Approved"
    campaign.approved_by = str(data.approver_email).lower()
    campaign.approver_name = data.approver_name
    campaign.approved_at = data.approved_at
    campaign.approval_document = data.document
    audit(db, admin, "campaign.approved", c.id, campaign.id)
    return campaign_out(campaign)


@app.post("/api/campaigns/{campaign_id}/start")
def start(
    campaign_id: str, company_id: str, admin=Depends(authenticate), db=Depends(get_db)
):
    c = company_get(db, company_id, True)
    campaign = campaign_get(db, company_id, campaign_id)
    require_ready(db, c)
    if campaign.status != "Approved":
        raise HTTPException(409, "Кампания должна быть независимо утверждена")
    campaign.status = "Running"
    campaign.next_send_at = now()
    audit(db, admin, "campaign.started", c.id, campaign.id)
    return campaign_out(campaign)


@app.post("/api/campaigns/{campaign_id}/stop")
def stop(
    campaign_id: str, company_id: str, admin=Depends(authenticate), db=Depends(get_db)
):
    campaign = campaign_get(db, company_id, campaign_id, True)
    if campaign.status not in ("Draft", "Approved", "Running"):
        raise HTTPException(409, "Кампания уже завершена")
    campaign.status = "Stopped"
    audit(db, admin, "campaign.stopped", company_id, campaign.id)
    return campaign_out(campaign)


def result_rows(db, c):
    return list(
        db.execute(
            select(Recipient, Employee)
            .join(Employee, Recipient.employee_id == Employee.id)
            .where(Recipient.campaign_id == c.id, Recipient.company_id == c.company_id)
            .order_by(Employee.full_name)
        )
    )


@app.get("/api/campaigns/{campaign_id}/statistics")
def statistics(
    campaign_id: str, company_id: str, admin=Depends(authenticate), db=Depends(get_db)
):
    c = campaign_get(db, company_id, campaign_id)
    rows = result_rows(db, c)
    sent = sum(r.delivery == "sent" for r, e in rows)
    clicked = sum(bool(r.clicked_at) and r.delivery == "sent" for r, e in rows)
    return {
        "campaign": campaign_out(c),
        "total": len(rows),
        "sent": sent,
        "failed": sum(r.delivery == "failed" for r, e in rows),
        "clicked": clicked,
        "training_viewed": sum(bool(r.training_at) for r, e in rows),
        "click_rate": round(clicked / sent * 100, 2) if sent else 0,
        "recipients": [
            {
                "id": r.id,
                "full_name": e.full_name,
                "email": e.email,
                "department": e.department,
                "delivery": r.delivery,
                "clicked_at": r.clicked_at,
                "training_at": r.training_at,
                "sent_at": r.sent_at,
            }
            for r, e in rows
        ],
    }


def csv_safe(v):
    s = str(v or "")
    return "'" + s if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else s


@app.get("/api/campaigns/{campaign_id}/export")
def export(
    campaign_id: str, company_id: str, admin=Depends(authenticate), db=Depends(get_db)
):
    c = campaign_get(db, company_id, campaign_id)
    company = db.get(Company, company_id)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "company",
            "campaign",
            "full_name",
            "email",
            "delivery_status",
            "confirmed_click",
            "event_time",
        ]
    )
    event_times = dict(
        db.execute(
            select(Event.employee_id, func.max(Event.created_at))
            .where(Event.campaign_id == c.id)
            .group_by(Event.employee_id)
        ).all()
    )
    for r, e in result_rows(db, c):
        writer.writerow(
            [
                csv_safe(v)
                for v in [
                    company.name,
                    c.name,
                    e.full_name,
                    e.email,
                    r.delivery,
                    "yes" if r.clicked_at else "no",
                    event_times[e.id].isoformat() if e.id in event_times else "",
                ]
            ]
        )
    audit(db, admin, "campaign.exported", company_id, c.id)
    return Response(
        "\ufeff" + out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="campaign-{c.id}.csv"'},
    )


@app.get("/api/audit")
def audit_list(company_id: str, admin=Depends(authenticate), db=Depends(get_db)):
    company_get(db, company_id)
    return list(
        db.scalars(
            select(Audit)
            .where(Audit.company_id == company_id)
            .order_by(Audit.created_at.desc())
            .limit(200)
        )
    )


TRAINING_STYLE = "body{font:17px/1.6 system-ui;background:#f0f5f4;color:#143b36;margin:0;padding:24px}main{max-width:680px;margin:7vh auto;background:white;border-radius:24px;padding:40px;box-shadow:0 20px 80px #173f3610}h1{font-size:30px;line-height:1.2}a,button{background:#147d64;color:white;border:0;padding:14px 22px;border-radius:8px;font:inherit;cursor:pointer}li{margin:14px 0}small{color:#60736f}"


def training_page(signs):
    return HTMLResponse(
        '<!doctype html><html lang="ru"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Обучение • AwareGuard</title><style>'
        + TRAINING_STYLE
        + "</style><main><small>AWAREGUARD / ОБУЧЕНИЕ</small><h1>Это была учебная симуляция фишинга.</h1><p>Вы в безопасности. Это письмо помогло потренироваться распознавать подозрительные сообщения.</p><h2>На что обратить внимание</h2><ul>"
        + "".join("<li>" + html.escape(s) + "</li>" for s in signs)
        + "</ul><p>Не вводите пароли по ссылкам из писем. Открывайте сервисы через закладки. Сообщайте о подозрительных письмах в вашу службу информационной безопасности.</p><small>Мы не собираем пароли, коды MFA или другие секреты.</small></main></html>"
    )


@app.get("/training-preview", response_class=HTMLResponse)
def preview():
    return training_page(
        ["Проверьте отправителя", "Проверьте домен ссылки", "Не поддавайтесь срочности"]
    )


def tracking_recipient(db, token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(404, "Ссылка недоступна")
    company_id = db.scalar(
        text("SELECT public.tracking_company(:h)"), {"h": digest(token)}
    )
    if not company_id:
        raise HTTPException(404, "Ссылка недоступна")
    scope(db, company_id)
    r = db.scalar(
        select(Recipient).where(Recipient.token_hash == digest(token)).with_for_update()
    )
    c = db.get(Campaign, r.campaign_id)
    company = db.get(Company, company_id)
    if (
        company.blocked
        or c.status not in ("Running", "Completed")
        or r.delivery != "sent"
        or c.created_at < now() - timedelta(days=company.retention_days)
    ):
        raise HTTPException(410, "Симуляция завершена или ссылка устарела")
    return r, c


@app.get("/t/{token}", response_class=HTMLResponse)
def tracking_landing(
    token: str, request: Request, response: Response, db=Depends(get_db)
):
    rate_limit(("track", request.client.host), 60, 60)
    r, c = tracking_recipient(db, token)
    # GETs (including scanners) never affect click statistics.
    nonce = secrets.token_urlsafe(32)
    page = HTMLResponse(
        '<!doctype html><html lang="ru"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AwareGuard</title><style>'
        + TRAINING_STYLE
        + '</style><main><small>AWAREGUARD</small><h1>Открыть уведомление</h1><p>Чтобы продолжить, нажмите кнопку ниже.</p><form method="post" action="/t/'
        + html.escape(token)
        + '/confirm"><input type="hidden" name="nonce" value="'
        + nonce
        + '"><button type="submit">Продолжить</button></form></main></html>'
    )
    page.set_cookie(
        "ag_tracking",
        digest(token + nonce),
        max_age=600,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
        path="/t/" + token,
    )
    return page


@app.post("/t/{token}/confirm", response_class=HTMLResponse)
def confirm_tracking(
    token: str,
    request: Request,
    nonce: str = Form(..., max_length=100),
    db=Depends(get_db),
):
    rate_limit(("confirm", request.client.host), 30, 60)
    if not secrets.compare_digest(
        request.cookies.get("ag_tracking", ""), digest(token + nonce)
    ):
        raise HTTPException(403, "Повторно откройте ссылку из письма")
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != settings.public_url.rstrip("/"):
        raise HTTPException(403, "Недопустимый источник")
    r, c = tracking_recipient(db, token)
    if not r.clicked_at:
        r.clicked_at = now()
        db.add(
            Event(
                company_id=r.company_id,
                campaign_id=r.campaign_id,
                employee_id=r.employee_id,
                kind="link_clicked",
            )
        )
    if not r.training_at:
        r.training_at = now()
        db.add(
            Event(
                company_id=r.company_id,
                campaign_id=r.campaign_id,
                employee_id=r.employee_id,
                kind="training_viewed",
            )
        )
    return training_page(db.get(Template, c.template_id).signs)
