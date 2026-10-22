import smtplib
from types import SimpleNamespace

import pytest
from app.mail import deliver


@pytest.mark.parametrize("cleanup", ["bad_reply", "quit_error", "close_error"])
@pytest.mark.parametrize("rejected", [False, True])
def test_delivery_result_is_independent_of_cleanup(monkeypatch, cleanup, rejected):
    calls = []
    rejection = smtplib.SMTPDataError(550, b"Rejected")

    class Relay:
        def __init__(self, **kwargs):
            pass

        def send_message(self, message):
            calls.append("DATA")
            if rejected:
                raise rejection
            return {}

        def quit(self):
            calls.append("QUIT")
            if cleanup == "quit_error":
                raise smtplib.SMTPResponseException(500, b"QUIT rejected")
            return (500 if cleanup == "bad_reply" else 221), b"Bye"

        def close(self):
            calls.append("CLOSE")
            if cleanup == "close_error":
                raise OSError("socket close failed")

    monkeypatch.setattr("app.mail.smtplib.SMTP", Relay)
    company = SimpleNamespace(
        sender="training@example.com",
        smtp_tls="none",
        smtp_host="localhost",
        smtp_port=25,
        smtp_user="",
    )
    template = SimpleNamespace(
        subject="Training", html='<p>{name} <a href="{link}">Open</a></p>'
    )
    if rejected:
        with pytest.raises(smtplib.SMTPDataError) as error:
            deliver(
                company,
                "employee@example.com",
                "Employee",
                template,
                "https://example.com/training",
            )
        assert error.value is rejection
    else:
        deliver(
            company,
            "employee@example.com",
            "Employee",
            template,
            "https://example.com/training",
        )
    assert calls == ["DATA", "QUIT", "CLOSE"]
