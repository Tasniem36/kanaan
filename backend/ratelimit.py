"""Tiny in-memory sliding-window rate limiter for sensitive endpoints
(login/register). Single-process deployment, so a module-level dict is enough —
no Redis needed. Fails open on its own errors: never blocks a request by mistake."""
import threading
import time

from fastapi import HTTPException, Request

_hits: dict[str, list[float]] = {}
_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    client = getattr(request, "client", None)
    return client.host if client else "unknown"


def rate_limit(request: Request, *, bucket: str, limit: int, window: float, key: str | None = None):
    """Allow at most `limit` requests per `window` seconds. Raises 429 when exceeded.

    Counted per IP by default. An endpoint that knows who is calling should pass
    `key=<user id>` instead: a family at home or a shop full of staff share one
    address, so an IP-keyed budget lets one person's activity throttle everyone
    else's. Sign-up and sign-in stay on the IP deliberately — there is no trusted
    identity yet, and the address is exactly what needs limiting there.
    """
    key = f"{bucket}:{key or _client_ip(request)}"
    now = time.monotonic()
    with _lock:
        recent = [t for t in _hits.get(key, ()) if now - t < window]
        if len(recent) >= limit:
            raise HTTPException(429, "Too many attempts. Please try again in a minute.")
        recent.append(now)
        _hits[key] = recent
