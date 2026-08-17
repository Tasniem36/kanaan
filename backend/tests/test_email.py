"""Verification email: headers and delivery behaviour.

Mail is the one channel we can't inspect by looking at the site, so the message
we hand to SMTP is asserted here. No network: smtplib is patched and the built
message captured.
"""
import smtplib
from email import message_from_bytes
from email.utils import parseaddr

import pytest

import messaging


class FakeSMTP:
    """Stands in for smtplib.SMTP, recording what would have been sent."""
    sent = []
    logged_in = None
    tls = False

    def __init__(self, host, port, timeout=None):
        FakeSMTP.host, FakeSMTP.port, FakeSMTP.timeout = host, port, timeout

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        FakeSMTP.tls = True

    def login(self, user, password):
        FakeSMTP.logged_in = (user, password)

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.sent = []
    FakeSMTP.logged_in = None
    FakeSMTP.tls = False
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_USER", "shop@example.com")
    monkeypatch.setenv("SMTP_PASS", "app-password")
    monkeypatch.delenv("SMTP_FROM", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_PORT", raising=False)
    return FakeSMTP


def _send(**kw):
    return messaging.send_email(kw.get("to", "customer@example.com"),
                               kw.get("subject", "رمز التحقق — دكّان كنعان"),
                               kw.get("body", "رمز التحقق الخاص بك هو: 123456"))


# --- configuration ----------------------------------------------------------
def test_unconfigured_email_is_a_no_op_not_an_error(monkeypatch):
    """A shop without SMTP set up must still be able to run."""
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    assert messaging.email_configured() is False
    assert messaging.send_email("a@b.com", "s", "b") is False


def test_send_uses_tls_and_authenticates(smtp):
    assert _send() is True
    assert smtp.tls is True, "credentials must not go over a plaintext connection"
    assert smtp.logged_in == ("shop@example.com", "app-password")
    assert (smtp.host, smtp.port) == ("smtp.gmail.com", 587)


def test_a_failing_server_returns_false_and_never_raises(smtp, monkeypatch):
    """Signup must not 500 because the mail server is down."""
    def boom(self, msg):
        raise smtplib.SMTPException("server said no")
    monkeypatch.setattr(FakeSMTP, "send_message", boom)
    assert _send() is False


# --- the message itself -----------------------------------------------------
def test_required_rfc5322_headers_are_present(smtp):
    """Python does not add Date or Message-ID, and a message missing Date is what
    makes clients show it with no timestamp or file it strangely."""
    _send()
    msg = smtp.sent[0]
    assert msg["Date"], "Date is required by RFC 5322"
    assert msg["Message-ID"], "Message-ID is required by RFC 5322"
    assert msg["Message-ID"].startswith("<") and msg["Message-ID"].endswith(">")


def test_message_id_is_unique_per_send(smtp):
    """A reused Message-ID makes clients collapse separate emails into one, so a
    second verification code can look like it never arrived."""
    _send()
    _send()
    a, b = (m["Message-ID"] for m in smtp.sent)
    assert a != b


def test_from_defaults_to_the_authenticated_account(smtp):
    """The address must be the authenticated one — anything else fails SPF/DKIM
    alignment. (The display name wrapped around it is asserted further down.)"""
    _send()
    assert parseaddr(smtp.sent[0]["From"])[1] == "shop@example.com"


def test_explicit_from_is_honoured(smtp, monkeypatch):
    monkeypatch.setenv("SMTP_FROM", "دكّان كنعان <hello@example.com>")
    _send()
    assert "hello@example.com" in smtp.sent[0]["From"]


def test_arabic_subject_and_body_survive_encoding(smtp):
    """The code has to be readable after transfer-encoding, or the customer can't
    complete signup."""
    _send(subject="رمز التحقق — دكّان كنعان", body="رمزك هو: 654321")
    raw = smtp.sent[0].as_bytes()
    parsed = message_from_bytes(raw)
    assert "رمز التحقق" in str(parsed["Subject"]) or "=?utf-8?" in str(parsed["Subject"]).lower()
    decoded = parsed.get_payload(decode=True).decode("utf-8")
    assert "654321" in decoded
    assert "رمزك" in decoded


def test_recipient_is_exactly_the_address_given(smtp):
    _send(to="someone@else.com")
    assert smtp.sent[0]["To"] == "someone@else.com"


def test_body_is_plain_text(smtp):
    """Plain text keeps the code visible even where HTML is blocked, and avoids
    the spam weighting an HTML-only mail attracts."""
    _send()
    assert smtp.sent[0].get_content_type() == "text/plain"


# --- deliverability: the headers that decide inbox vs spam -------------------
def test_from_gets_a_display_name(smtp):
    """A bare address reads as machine mail; filters and people both prefer a name."""
    _send()
    assert smtp.sent[0]["From"] == "دكّان كنعان <shop@example.com>"


def test_display_name_is_configurable(smtp, monkeypatch):
    monkeypatch.setenv("SMTP_FROM_NAME", "Dukkan Kanaan")
    _send()
    assert smtp.sent[0]["From"] == "Dukkan Kanaan <shop@example.com>"


def test_an_explicit_from_with_a_name_is_left_alone(smtp, monkeypatch):
    """Don't double-wrap what the admin already formatted."""
    monkeypatch.setenv("SMTP_FROM", "متجرنا <hello@example.com>")
    _send()
    assert smtp.sent[0]["From"] == "متجرنا <hello@example.com>"


def test_reply_to_defaults_to_a_real_mailbox(smtp):
    """Never a noreply black hole — a stuck customer needs somewhere to reply."""
    _send()
    assert smtp.sent[0]["Reply-To"] == "shop@example.com"


def test_reply_to_is_overridable(smtp, monkeypatch):
    monkeypatch.setenv("SMTP_REPLY_TO", "support@example.com")
    _send()
    assert smtp.sent[0]["Reply-To"] == "support@example.com"


def test_marked_as_automated_transactional_mail(smtp):
    """RFC 3834 — keeps receivers from weighing it as bulk, and stops
    auto-responders replying to a verification code."""
    _send()
    assert smtp.sent[0]["Auto-Submitted"] == "auto-generated"


def test_a_from_on_another_domain_is_warned_about(smtp, monkeypatch, capsys):
    """SPF/DKIM misalignment is the usual reason this mail lands in spam, and it
    is otherwise completely silent."""
    monkeypatch.setattr(messaging, "_warned_alignment", False)
    monkeypatch.setenv("SMTP_FROM", "noreply@dukkan-kanaan.com")
    _send()
    out = capsys.readouterr().out
    assert "WARNING" in out and "SPF/DKIM" in out


def test_matching_domains_produce_no_warning(smtp, monkeypatch, capsys):
    monkeypatch.setattr(messaging, "_warned_alignment", False)
    monkeypatch.setenv("SMTP_FROM", "orders@example.com")   # same domain as SMTP_USER
    _send()
    assert "WARNING" not in capsys.readouterr().out
