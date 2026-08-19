"""Server-side audit trail. log_action() is called from inside route handlers
(never from the frontend). Fire-and-forget: runs in a thread, never raises.

Each row records the API call that produced it, which is the action the customer
took; `page` (from the Referer) is only where they were standing at the time.

This is a trail of what CUSTOMERS did, not a request log:
  * the shop's own staff are never recorded — a manager moderating or browsing is
    not customer activity, and their rows would crowd out the ones that matter;
  * anything a page polls in the background is never logged at all;
  * repeat-heavy actions are collapsed (see _COLLAPSE), so one shopper browsing
    doesn't bury the interesting rows."""
import json
import threading
import time
from urllib.parse import parse_qsl, urlencode, urlparse

from db import execute, fetch_one


def _client_ip(request):
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    client = getattr(request, "client", None)
    return client.host if client else None


# Actions a single visitor repeats just by using the site. One row per window per
# visitor is plenty — the 30 minutes is a rough "same sitting".
_COLLAPSE = {"visit": 1800}
_recent: dict[str, float] = {}
_recent_lock = threading.Lock()


def _is_repeat(action, user_id, ip) -> bool:
    """True when this visitor already logged `action` inside its collapse window."""
    window = _COLLAPSE.get(action)
    if not window:
        return False
    key = f"{action}:{user_id or ip or 'anon'}"
    now = time.monotonic()
    with _recent_lock:
        last = _recent.get(key)
        if last is not None and now - last < window:
            return True
        _recent[key] = now
        # drop entries that can no longer suppress anything, so this can't grow
        if len(_recent) > 5000:
            for k, t in list(_recent.items()):
                if now - t >= window:
                    del _recent[k]
    return False


# user_id -> (is_manager, checked_at). Managers are a handful and rarely change, so
# this keeps the role lookup off almost every write. The TTL means a promotion or
# demotion is picked up without a restart.
_ROLE_TTL = 600
_roles: dict[str, tuple[bool, float]] = {}
_roles_lock = threading.Lock()


def _is_staff(user_id) -> bool:
    """Whether this actor is the shop's own manager. Runs on the audit thread, so the
    lookup never delays a customer's request. Fails open: on a DB hiccup the row is
    written rather than silently dropped."""
    if not user_id:
        return False
    key = str(user_id)
    now = time.monotonic()
    with _roles_lock:
        cached = _roles.get(key)
        if cached and now - cached[1] < _ROLE_TTL:
            return cached[0]
    try:
        row = fetch_one("select role from users where id = %s", [user_id])
    except Exception as e:  # noqa: BLE001
        print("[audit] role lookup failed:", e)
        return False
    staff = bool(row and row.get("role") == "manager")
    with _roles_lock:
        _roles[key] = (staff, now)
    return staff


def _api(request):
    """The endpoint that recorded this — "POST /api/orders"."""
    if request is None:
        return None
    method = getattr(request, "method", None)
    path = getattr(getattr(request, "url", None), "path", None)
    return f"{method} {path}" if method and path else None


# Ad and analytics parameters. A click from an Instagram campaign arrives with a
# dozen of them, which turns the stored page into an unreadable wall — and they say
# nothing about what the customer did. The campaign itself is worth keeping, so
# traffic_source() pulls that out before they're dropped.
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {
    "fbclid", "gclid", "gbraid", "wbraid", "msclkid", "ttclid", "twclid", "igshid",
    "li_fat_id", "mc_cid", "mc_eid", "yclid", "dclid", "_gl", "ref_src", "ref_url",
}


def _is_tracking(key: str) -> bool:
    k = key.lower()
    return k in _TRACKING_KEYS or k.startswith(_TRACKING_PREFIXES)


def _page(request):
    # the page the action came from — the Referer of the API call (same-origin, so
    # the full path survives our Referrer-Policy). Stored as path(+query), no host,
    # and without the ad parameters.
    if request is None:
        return None
    ref = request.headers.get("referer")
    if not ref:
        return None
    try:
        parts = urlparse(ref)
        kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                if not _is_tracking(k)]
        query = urlencode(kept)
        return (parts.path or "/") + (f"?{query}" if query else "")
    except Exception:
        return ref[:300]


def traffic_source(request):
    """Where a visitor came from, read off the campaign tags on the landing URL:
    {"source": "ig", "medium": "paid", "campaign": "1202…"} — or None for a direct
    visit. Worth recording once per visit: it's the only place the shop learns which
    ad or post actually brings shoppers in."""
    if request is None:
        return None
    ref = request.headers.get("referer") or ""
    try:
        params = dict(parse_qsl(urlparse(ref).query, keep_blank_values=True))
    except Exception:
        return None
    src = {
        "source": params.get("utm_source"),
        "medium": params.get("utm_medium"),
        "campaign": params.get("utm_campaign"),
    }
    src = {k: v[:80] for k, v in src.items() if v}
    # a bare fbclid with no utm tags still means "came from a Facebook/Instagram link"
    if not src and any(k in params for k in ("fbclid", "igshid")):
        src = {"source": "facebook"}
    return src or None


def log_action(*, user_id=None, action, detail=None, request=None):
    ip = _client_ip(request)
    if _is_repeat(action, user_id, ip):
        return
    page = _page(request)
    api = _api(request)
    payload = json.dumps(detail, default=str) if detail is not None else None

    def _insert():
        try:
            if _is_staff(user_id):
                return   # the shop's own actions are not customer activity
            execute(
                """insert into audit_logs (user_id, action, detail, ip, page, api)
                   values (%s, %s, %s::jsonb, %s, %s, %s)""",
                [user_id, action, payload, ip, page, api],
            )
        except Exception as e:  # never let auditing break a request
            print("[audit]", e)

    threading.Thread(target=_insert, daemon=True).start()
