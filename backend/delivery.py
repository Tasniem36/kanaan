"""Delivery fee: a city matching a zone's keywords pays that zone's fee; any
other city pays `default_fee`; free once the subtotal reaches `free_threshold`
(0/None disables free shipping). Zones and settings are admin-managed."""
from db import fetch_all, fetch_one

DEFAULTS = {"free_threshold": 250, "default_fee": 25}


def _norm(s: str) -> str:
    s = (s or "").strip().lower().replace(" ", "")
    for a in "أإآ":
        s = s.replace(a, "ا")
    return s.replace("ى", "ي")


def get_config() -> dict:
    row = fetch_one("select value from settings where key = 'delivery'")
    cfg = dict(DEFAULTS)
    if row and isinstance(row.get("value"), dict):
        v = row["value"]
        if v.get("free_threshold") is not None:
            cfg["free_threshold"] = v["free_threshold"]
        # tolerate the older shape that stored fee_low instead of default_fee
        cfg["default_fee"] = v.get("default_fee", v.get("fee_low", DEFAULTS["default_fee"]))
    return cfg


def get_zones() -> list:
    return fetch_all("select id, label, keywords, fee, sort from delivery_zones order by sort, created_at")


def compute_fee(city: str, subtotal: float, cfg: dict | None = None, zones: list | None = None) -> float:
    cfg = cfg or get_config()
    thr = cfg.get("free_threshold")
    try:
        if thr is not None and float(thr) > 0 and float(subtotal) >= float(thr):
            return 0.0
    except (TypeError, ValueError):
        pass
    n = _norm(city)
    zones = zones if zones is not None else get_zones()
    for z in zones:
        kws = [_norm(k) for k in (z.get("keywords") or "").split(",") if k.strip()]
        if any(k and k in n for k in kws):
            return float(z["fee"])
    return float(cfg.get("default_fee", DEFAULTS["default_fee"]))
