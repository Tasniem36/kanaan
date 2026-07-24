"""Server-side validation — the source of truth (browser checks are UX only)."""
import re

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# strong password: >=8 chars with at least one lower, one upper, one digit
STRONG_PW_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")


def is_email(v: str) -> bool:
    return bool(EMAIL_RE.match(v or ""))


def is_strong_password(v: str) -> bool:
    return bool(STRONG_PW_RE.match(v or ""))


def normalize_uae_phone(raw):
    """Return a UAE mobile normalized as +9715XXXXXXXX, or None."""
    d = re.sub(r"\D", "", str(raw or ""))
    if d.startswith("971"):
        d = d[3:]
    elif d.startswith("0"):
        d = d[1:]
    return "+971" + d if re.match(r"^5\d{8}$", d) else None
