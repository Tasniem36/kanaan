"""Server-side validation is the source of truth (browser checks are UX only)."""
import pytest

from validate import is_email, is_strong_password, normalize_uae_phone


@pytest.mark.parametrize("v,ok", [
    ("a@b.com", True), ("x.y@sub.example.co", True),
    ("nope", False), ("a@b", False), ("a b@c.com", False), ("", False),
])
def test_is_email(v, ok):
    assert is_email(v) is ok


@pytest.mark.parametrize("v,ok", [
    ("Abcd1234", True),            # 8+, upper, lower, digit
    ("short1A", False),           # too short
    ("alllower123", False),       # no uppercase
    ("ALLUPPER123", False),       # no lowercase
    ("NoDigitsHere", False),      # no digit
])
def test_is_strong_password(v, ok):
    assert is_strong_password(v) is ok


@pytest.mark.parametrize("raw,expected", [
    ("0501234567", "+971501234567"),
    ("971501234567", "+971501234567"),
    ("+971 50 123 4567", "+971501234567"),
    ("501234567", "+971501234567"),
    ("0601234567", None),          # not a 5-series mobile
    ("12345", None),
    ("", None),
])
def test_normalize_uae_phone(raw, expected):
    assert normalize_uae_phone(raw) == expected
