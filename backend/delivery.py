"""Delivery fee: Abu Dhabi / Al Ain cost `fee_high`, every other emirate
`fee_low`; free when the subtotal reaches `free_threshold` (0/None disables it).
The emirate is detected from the free-text city. All amounts are admin-editable
via the `settings` table (key = 'delivery')."""
from db import fetch_one

DEFAULTS = {"fee_high": 30, "fee_low": 25, "free_threshold": 250}

# normalized keywords that map a city to the high (Abu Dhabi emirate) tier
_HIGH = ["ابوظبي", "العين", "abudhabi", "alain"]


def _norm(s: str) -> str:
    s = (s or "").strip().lower().replace(" ", "")
    for a in "أإآ":
        s = s.replace(a, "ا")
    return s.replace("ى", "ي")


def get_config() -> dict:
    row = fetch_one("select value from settings where key = 'delivery'")
    cfg = dict(DEFAULTS)
    if row and isinstance(row.get("value"), dict):
        cfg.update({k: v for k, v in row["value"].items() if v is not None})
    return cfg


def compute_fee(city: str, subtotal: float, cfg: dict | None = None) -> float:
    cfg = cfg or get_config()
    thr = cfg.get("free_threshold")
    try:
        if thr is not None and float(thr) > 0 and float(subtotal) >= float(thr):
            return 0.0
    except (TypeError, ValueError):
        pass
    n = _norm(city)
    high = any(k in n for k in _HIGH)
    return float(cfg["fee_high"] if high else cfg["fee_low"])
