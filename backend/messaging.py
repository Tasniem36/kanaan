"""Outbound email (SMTP / Gmail app-password) and SMS (Twilio) for verification
codes. Both are best-effort: they return True if actually sent, False if the
channel isn't configured or the send failed. Never raise.

Configure in the environment:
  Email (Gmail app password):  SMTP_HOST (default smtp.gmail.com), SMTP_PORT (587),
                               SMTP_USER, SMTP_PASS, SMTP_FROM (defaults to SMTP_USER)
  SMS (Twilio):                TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

import requests


def email_configured() -> bool:
    return bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))


def sms_configured() -> bool:
    return bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN") and os.getenv("TWILIO_FROM"))


def send_email(to: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    sender = os.getenv("SMTP_FROM") or user
    if not user or not password:
        return False
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        msg.set_content(body)
        with smtplib.SMTP(host, port, timeout=15) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(user, password)
            s.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        print("[email] send failed:", e)
        return False


def send_sms(to: str, body: str) -> bool:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    frm = os.getenv("TWILIO_FROM")
    if not sid or not token or not frm:
        return False
    try:
        res = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"To": to, "From": frm, "Body": body},
            auth=(sid, token),
            timeout=15,
        )
        if not res.ok:
            print("[sms] send failed:", res.status_code, res.text[:200])
            return False
        return True
    except Exception as e:  # noqa: BLE001
        print("[sms] send error:", e)
        return False
