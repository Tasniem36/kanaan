"""Server-side audit trail. log_action() is called from inside route handlers
(never from the frontend). Fire-and-forget: runs in a thread, never raises."""
import json
import threading

from db import execute


def _client_ip(request):
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    client = getattr(request, "client", None)
    return client.host if client else None


def log_action(*, user_id=None, action, detail=None, request=None):
    ip = _client_ip(request)
    payload = json.dumps(detail, default=str) if detail is not None else None

    def _insert():
        try:
            execute(
                "insert into audit_logs (user_id, action, detail, ip) values (%s, %s, %s::jsonb, %s)",
                [user_id, action, payload, ip],
            )
        except Exception as e:  # never let auditing break a request
            print("[audit]", e)

    threading.Thread(target=_insert, daemon=True).start()
