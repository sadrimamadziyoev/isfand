import csv
import io
import re
from datetime import timedelta
from types import SimpleNamespace

import pyotp
import pytest
from app.db import Session, scope
from app.models import Campaign, Company, Employee, Event, Recipient, now
from app.worker import process_one
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError


def make_company(client, smtp, monkeypatch, domain="company.example.com"):
    data = {
        "name": "Test Company",
        "domain": domain,
        "authorization": "Signed authorization AUTH-001",
        "infrastructure_approved": True,
        "smtp_host": "127.0.0.1",
        "smtp_port": smtp.server_address[1],
        "smtp_tls": "none",
        "sender": "training@" + domain,
        "approved_senders": ["training@" + domain],
    }
    r = client.post("/api/companies", json=data)
    assert r.status_code == 201, r.text
    c = r.json()
    monkeypatch.setattr(
        "app.main.dns.resolver.resolve",
        lambda *a, **k: [SimpleNamespace(strings=[c["dns_value"].encode()])],
    )
    r = client.post(f"/api/companies/{c['id']}/verify-domain")
    assert r.status_code == 200, r.text
    return c


def import_staff(client, c, count=100):
    content = "full_name,email,department\n" + "".join(
        f"Employee {i},person{i}@{c['domain']},IT\n" for i in range(count)
    )
    r = client.post(
        "/api/employees/import",
        data={"company_id": c["id"]},
        files={"file": ("staff.csv", content, "text/csv")},
    )
    assert r.status_code == 200, r.text
    return client.get("/api/employees", params={"company_id": c["id"]}).json()


def draft(client, c, es):
    r = client.post(
        "/api/campaigns",
        json={
            "name": "Awareness test",
            "company_id": c["id"],
            "template_id": "document",
            "employee_ids": [e["id"] for e in es],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def path(c, ca, a):
    return f"/api/campaigns/{ca['id']}/{a}?company_id={c['id']}"


def approve(client, c, ca, email):
    r = client.post(path(c, ca, "test"), json={"email": email})
    assert r.status_code == 200, r.text
    r = client.post(
        path(c, ca, "approve"),
        json={
            "approver_name": "Independent Reviewer",
            "approver_email": "reviewer@" + c["domain"],
            "approved_at": now().isoformat(),
            "document": "Signed independent approval REF-123",
            "independent_confirmation": True,
        },
    )
    assert r.status_code == 200, r.text


def test_full_workflow_100_import_smtp_click_csv_stop(client, smtp, monkeypatch):
    c = make_company(client, smtp, monkeypatch)
    es = import_staff(client, c, 100)
    assert len(es) == 100
    assert len(import_staff(client, c, 100)) == 100
    ca = draft(client, c, es)
    assert client.post(path(c, ca, "start")).status_code == 409
    approve(client, c, ca, es[0]["email"])
    assert len(smtp.messages) == 1
    assert client.post(path(c, ca, "start")).status_code == 200
    assert process_one(c["id"])
    assert len(smtp.messages) == 2
    s = client.get(path(c, ca, "statistics")).json()
    assert (s["sent"], s["clicked"], s["total"]) == (1, 0, 100)
    with Session() as db:
        scope(db, c["id"])
        r = db.scalar(
            select(Recipient).where(
                Recipient.campaign_id == ca["id"], Recipient.delivery == "sent"
            )
        )
        token = r.token
    landing = client.get("/t/" + token)
    assert landing.status_code == 200
    assert client.get(path(c, ca, "statistics")).json()["clicked"] == 0
    nonce = re.search(r'name="nonce" value="([^"]+)"', landing.text).group(1)
    assert (
        client.post("/t/" + token + "/confirm", data={"nonce": "bad"}).status_code
        == 403
    )
    response = client.post("/t/" + token + "/confirm", data={"nonce": nonce})
    assert response.status_code == 200
    assert "Это была учебная симуляция" in response.text
    assert (
        client.post("/t/" + token + "/confirm", data={"nonce": nonce}).status_code
        == 200
    )
    s = client.get(path(c, ca, "statistics")).json()
    assert (s["clicked"], s["training_viewed"], s["click_rate"]) == (1, 1, 100)
    with Session() as db:
        scope(db, c["id"])
        assert (
            len(list(db.scalars(select(Event).where(Event.kind == "link_clicked"))))
            == 1
        )
    report = client.get(path(c, ca, "export"))
    rows = list(csv.DictReader(io.StringIO(report.content.decode("utf-8-sig"))))
    assert len(rows) == 100
    assert sum(row["confirmed_click"] == "yes" for row in rows) == 1
    assert client.post(path(c, ca, "stop")).status_code == 200
    assert not process_one(c["id"])
    assert len(smtp.messages) == 2


def test_independent_approval_and_foreign_recipients(client, smtp, monkeypatch):
    c = make_company(client, smtp, monkeypatch)
    es = import_staff(client, c, 2)
    ca = draft(client, c, es)
    data = {
        "approver_name": "Independent Reviewer",
        "approver_email": "reviewer@company.example.com",
        "approved_at": now().isoformat(),
        "document": "Valid independent approval",
        "independent_confirmation": True,
    }
    assert client.post(path(c, ca, "approve"), json=data).status_code == 409
    assert (
        client.post(
            path(c, ca, "test"), json={"email": "outside@other.example.com"}
        ).status_code
        == 422
    )
    assert (
        client.post(path(c, ca, "test"), json={"email": es[0]["email"]}).status_code
        == 200
    )
    data.update(
        approver_email="admin@platform.example.com", approved_at=now().isoformat()
    )
    assert client.post(path(c, ca, "approve"), json=data).status_code == 422
    other = make_company(client, smtp, monkeypatch, "other.example.com")
    other_es = import_staff(client, other, 1)
    r = client.post(
        "/api/campaigns",
        json={
            "name": "Invalid",
            "company_id": c["id"],
            "template_id": "document",
            "employee_ids": [other_es[0]["id"]],
        },
    )
    assert r.status_code == 422
    assert (
        client.get(
            f"/api/campaigns/{ca['id']}/statistics?company_id={other['id']}"
        ).status_code
        == 404
    )


def test_rls_and_composite_foreign_key(client, smtp, monkeypatch):
    a = make_company(client, smtp, monkeypatch)
    ea = import_staff(client, a, 1)
    ca = draft(client, a, ea)
    b = make_company(client, smtp, monkeypatch, "other.example.com")
    eb = import_staff(client, b, 1)
    with Session() as db:
        assert list(db.scalars(select(Employee))) == []
        assert list(db.scalars(select(Company))) == []
        scope(db, b["id"])
        assert [e.id for e in db.scalars(select(Employee))] == [eb[0]["id"]]
        assert db.get(Campaign, ca["id"]) is None
        db.add(
            Recipient(
                company_id=b["id"],
                campaign_id=ca["id"],
                employee_id=eb[0]["id"],
                token="test",
                token_hash="test",
            )
        )
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()
    with Session() as db:
        scope(db, a["id"])
        db.add(
            Employee(
                company_id=b["id"],
                full_name="Foreign",
                email="foreign@other.example.com",
            )
        )
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()


def test_csv_validation_atomic_limit_and_exclusion(client, smtp, monkeypatch):
    c = make_company(client, smtp, monkeypatch)
    for content in [
        "wrong,header\na,b\n",
        "full_name,email,department\nGood,ok@company.example.com,IT\nBad,no@other.example.com,IT\n",
        "full_name,email,department\nBad,invalid,IT\n",
    ]:
        r = client.post(
            "/api/employees/import",
            data={"company_id": c["id"]},
            files={"file": ("bad.csv", content)},
        )
        assert r.status_code == 422
    assert client.get("/api/employees", params={"company_id": c["id"]}).json() == []
    es = import_staff(client, c, 500)
    r = client.post(
        "/api/employees/import",
        data={"company_id": c["id"]},
        files={
            "file": (
                "extra.csv",
                "full_name,email,department\nExtra,extra@company.example.com,IT\n",
            )
        },
    )
    assert r.status_code == 422
    assert (
        client.patch(
            "/api/employees/" + es[0]["id"],
            params={"company_id": c["id"]},
            json={"excluded": True},
        ).status_code
        == 200
    )
    r = client.post(
        "/api/campaigns",
        json={
            "name": "Excluded",
            "company_id": c["id"],
            "template_id": "hr",
            "employee_ids": [es[0]["id"]],
        },
    )
    assert r.status_code == 422


def test_block_and_permission_recheck(client, smtp, monkeypatch):
    c = make_company(client, smtp, monkeypatch)
    es = import_staff(client, c, 2)
    ca = draft(client, c, es)
    approve(client, c, ca, es[0]["email"])
    assert client.post(path(c, ca, "start")).status_code == 200
    for e in es:
        assert (
            client.patch(
                "/api/employees/" + e["id"],
                params={"company_id": c["id"]},
                json={"excluded": True},
            ).status_code
            == 200
        )
    process_one(c["id"])
    assert len(smtp.messages) == 1
    assert (
        client.get(path(c, ca, "statistics")).json()["campaign"]["status"] == "Stopped"
    )
    assert client.post("/api/companies/" + c["id"] + "/block").status_code == 200
    assert client.post(path(c, ca, "start")).status_code == 409


def test_sessions_csrf_mfa_logout(client):
    assert (
        client.post(
            "/api/companies",
            headers={"X-CSRF-Token": ""},
            json={"name": "No", "domain": "no.example.com"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/auth/login",
            json={
                "email": "admin@platform.example.com",
                "password": "Test-only-long-password",
                "otp": "000000",
            },
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={
                "email": "admin@platform.example.com",
                "password": "Test-only-long-password",
                "otp": pyotp.TOTP("JBSWY3DPEHPK3PXP").now(),
            },
        ).status_code
        == 401
    )
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/companies").status_code == 401


def test_dns_must_match_and_smtp_failure(client, smtp, monkeypatch):
    r = client.post(
        "/api/companies",
        json={"name": "Unverified", "domain": "unverified.example.com"},
    )
    c = r.json()
    monkeypatch.setattr(
        "app.main.dns.resolver.resolve",
        lambda *a, **k: [SimpleNamespace(strings=[b"wrong"])],
    )
    assert (
        client.post("/api/companies/" + c["id"] + "/verify-domain").status_code == 422
    )
    es = import_staff(client, c, 1)
    ca = draft(client, c, es)
    assert (
        client.post(path(c, ca, "test"), json={"email": es[0]["email"]}).status_code
        == 409
    )
    c = make_company(client, smtp, monkeypatch, "verified.example.com")
    es = import_staff(client, c, 1)
    ca = draft(client, c, es)
    approve(client, c, ca, es[0]["email"])
    client.post(path(c, ca, "start"))
    monkeypatch.setattr(
        "app.worker.deliver",
        lambda *a, **k: (_ for _ in ()).throw(ConnectionError("test relay down")),
    )
    process_one(c["id"])
    s = client.get(path(c, ca, "statistics")).json()
    assert (s["failed"], s["sent"]) == (1, 0)


def test_tracking_expiry_and_csv_injection(client, smtp, monkeypatch):
    c = make_company(client, smtp, monkeypatch)
    es = import_staff(client, c, 1)
    with Session() as db:
        scope(db, c["id"])
        e = db.get(Employee, es[0]["id"])
        e.full_name = '=HYPERLINK("bad")'
        db.commit()
    ca = draft(client, c, es)
    approve(client, c, ca, es[0]["email"])
    client.post(path(c, ca, "start"))
    process_one(c["id"])
    row = list(
        csv.DictReader(
            io.StringIO(client.get(path(c, ca, "export")).content.decode("utf-8-sig"))
        )
    )[0]
    assert row["full_name"].startswith("'=")
    with Session() as db:
        scope(db, c["id"])
        r = db.scalar(select(Recipient).where(Recipient.campaign_id == ca["id"]))
        token = r.token
        db.get(Campaign, ca["id"]).created_at = now() - timedelta(days=100)
        db.commit()
    assert client.get("/t/" + token).status_code == 410
    assert client.get("/t/not-a-token").status_code == 404


def test_throttle_completion_and_ambiguous_restart(client, smtp, monkeypatch):
    c = make_company(client, smtp, monkeypatch)
    es = import_staff(client, c, 2)
    ca = draft(client, c, es)
    approve(client, c, ca, es[0]["email"])
    client.post(path(c, ca, "start"))
    assert process_one(c["id"])
    assert not process_one(c["id"])
    with Session() as db:
        scope(db, c["id"])
        remaining = db.scalar(
            select(Recipient).where(
                Recipient.campaign_id == ca["id"], Recipient.delivery == "pending"
            )
        )
        remaining.delivery = "dispatching"
        db.get(Campaign, ca["id"]).next_send_at = now()
        db.commit()
    assert process_one(c["id"])
    result = client.get(path(c, ca, "statistics")).json()
    assert result["campaign"]["status"] == "Failed"
    assert len(smtp.messages) == 2  # only the test and first successful send


def test_stop_waits_for_inflight_then_prevents_next(client, smtp, monkeypatch):
    import threading

    from app.mail import deliver

    c = make_company(client, smtp, monkeypatch)
    es = import_staff(client, c, 2)
    ca = draft(client, c, es)
    approve(client, c, ca, es[0]["email"])
    client.post(path(c, ca, "start"))
    entered = threading.Event()
    release = threading.Event()
    stopped = threading.Event()
    result = []

    def slow_send(*a, **kw):
        entered.set()
        assert release.wait(5)
        return deliver(*a, **kw)

    monkeypatch.setattr("app.worker.deliver", slow_send)
    sender = threading.Thread(target=lambda: process_one(c["id"]))
    sender.start()
    assert entered.wait(5)

    def request_stop():
        result.append(client.post(path(c, ca, "stop")).status_code)
        stopped.set()

    stopper = threading.Thread(target=request_stop)
    stopper.start()
    assert not stopped.wait(0.2)
    release.set()
    sender.join(5)
    stopper.join(5)
    assert result == [200]
    assert not process_one(c["id"])
    assert len(smtp.messages) == 2


def test_completion_and_retention_purge(client, smtp, monkeypatch):
    from app.cli import main as cli

    c = make_company(client, smtp, monkeypatch)
    es = import_staff(client, c, 1)
    ca = draft(client, c, es)
    approve(client, c, ca, es[0]["email"])
    client.post(path(c, ca, "start"))
    process_one(c["id"])
    with Session() as db:
        scope(db, c["id"])
        db.get(Campaign, ca["id"]).next_send_at = now()
        db.commit()
    process_one(c["id"])
    assert (
        client.get(path(c, ca, "statistics")).json()["campaign"]["status"]
        == "Completed"
    )
    with Session() as db:
        scope(db, c["id"])
        db.get(Campaign, ca["id"]).created_at = now() - timedelta(days=100)
        db.get(Employee, es[0]["id"]).created_at = now() - timedelta(days=100)
        db.commit()
    monkeypatch.setattr("sys.argv", ["awareguard", "purge"])
    cli()
    with Session() as db:
        scope(db, c["id"])
        assert list(db.scalars(select(Campaign))) == []
        assert list(db.scalars(select(Employee))) == []
        assert list(db.scalars(select(Event))) == []


def test_company_settings_change_requires_new_test(client, smtp, monkeypatch):
    c = make_company(client, smtp, monkeypatch)
    es = import_staff(client, c, 1)
    ca = draft(client, c, es)
    assert (
        client.post(path(c, ca, "test"), json={"email": es[0]["email"]}).status_code
        == 200
    )
    assert client.put("/api/companies/" + c["id"], json=c).status_code == 200
    result = client.get(path(c, ca, "statistics")).json()
    assert result["campaign"]["test_sent_at"] is None


def test_accepted_delivery_survives_bad_smtp_quit(client, smtp, monkeypatch):
    smtp.quit_code = 500
    company = make_company(client, smtp, monkeypatch)
    employees = import_staff(client, company, 1)
    campaign = draft(client, company, employees)
    approve(client, company, campaign, employees[0]["email"])
    assert client.post(path(company, campaign, "start")).status_code == 200
    assert process_one(company["id"])
    stats = client.get(path(company, campaign, "statistics")).json()
    assert (stats["sent"], stats["failed"]) == (1, 0)
    assert len(smtp.messages) == 2
