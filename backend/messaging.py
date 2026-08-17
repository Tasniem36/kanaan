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
from email.utils import formataddr, formatdate, make_msgid, parseaddr

import requests

BRAND = "دكّان كنعان"
_warned_alignment = False


def _from_header(sender: str) -> str:
    """"Name <address>" rather than a bare address — a sender with no display name
    reads as machine mail and scores worse with spam filters. An SMTP_FROM that
    already carries a name is left exactly as the admin wrote it."""
    name, addr = parseaddr(sender or "")
    if name or not addr:
        return sender
    return formataddr((os.getenv("SMTP_FROM_NAME", BRAND), addr))


def _warn_if_misaligned(sender: str, user: str) -> None:
    """A From on a different domain than the authenticated account fails SPF/DKIM
    alignment at the receiver, which is the most common reason verification mail
    lands in spam. Legitimate when the address is a verified "send mail as" alias,
    so this warns rather than refuses — but it warns loudly, because the symptom
    (mail silently filed as spam) gives no other clue. Logged once per process."""
    global _warned_alignment
    if _warned_alignment:
        return
    from_domain = parseaddr(sender or "")[1].rpartition("@")[2].lower()
    user_domain = (user or "").rpartition("@")[2].lower()
    if from_domain and user_domain and from_domain != user_domain:
        _warned_alignment = True
        print(f"[email] WARNING: SMTP_FROM is @{from_domain} but authenticating as "
              f"@{user_domain}. Unless that address is a verified alias on the "
              f"sending account, SPF/DKIM will not align and mail will be treated "
              f"as spam. Set SMTP_FROM to the authenticated address, or send "
              f"through a provider authenticated for your own domain.")


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
        _warn_if_misaligned(sender, user)
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = _from_header(sender)
        msg["To"] = to
        # A reply path a human actually reads. Mail with no usable Reply-To (or a
        # noreply@ black hole) scores worse and leaves a stuck customer nowhere
        # to turn.
        msg["Reply-To"] = os.getenv("SMTP_REPLY_TO") or parseaddr(sender)[1] or sender
        # RFC 3834: marks this as an automated transactional message, so receivers
        # don't weigh it as bulk mail and auto-responders don't reply to it.
        msg["Auto-Submitted"] = "auto-generated"
        # Date and Message-ID are required by RFC 5322 and Python does NOT add
        # them. Gmail's submission server fills them in, but a self-hosted or
        # relay SMTP_HOST may not — and a message with no Date is what makes mail
        # clients show it with no timestamp or file it oddly. Cheap to be correct.
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1] if "@" in (sender or "") else None)
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
