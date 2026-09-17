"""Server-side failures, recorded where somebody will actually see them.

Two dozen handlers in this codebase have the same shape: something that must not be
allowed to break the thing that triggered it — a customer's WhatsApp, a push, an
audit row, one order in the nightly sweep — failed, and the only trace was a print
into the container's stdout. Nobody reads that until they already know something is
wrong, which is the one moment it is too late for it to help.

These rows go into the same error_reports table the storefront posts to, so the
manager's errors page shows the shop's own failures beside the customers'. They are
marked with a name no customer has, because "a customer hit this" and "our machinery
failed" are not the same thing to whoever reads the page.

The print stays at every call site. stdout is still where you look when the database
is itself the thing that is down — the one failure this module can never record.
"""
import threading
import time
import traceback

from db import execute

# What the manager's errors page shows in the contact column, where a customer report
# carries a name. Without it a server failure renders as "a guest visitor", which is
# both wrong and the most misleading thing that column could say.
_SERVER = "الخادم"

# One row per tag per gap, dropping whatever arrives in between — the same throttle
# the storefront reporter uses (frontend/src/services/report.js).
#
# Per tag rather than on one clock, which is the one place this deliberately differs:
# an expired WhatsApp token fails for every order in the shop, and a single clock
# would let that burst swallow a payment failing beside it. A page that hides the
# rare failure behind the noisy one is worse than no page.
#
# Which is why a tag is a constant naming a call site, never a value: keyed on an
# order id it would throttle nothing (every failure its own key) and grow a dict
# entry per order for the life of the process. Anything varying goes in `note`.
_MIN_GAP_SECONDS = 1.5
_lock = threading.Lock()
_last: dict[str, float] = {}

# The insert can fail for the very reason the caller did — a database that is down is
# what broke them both — and recording that failure would call straight back in here.
# Per thread, because these run on the notification threads as well as on requests.
_busy = threading.local()


def _trace(exc) -> str:
    if not isinstance(exc, BaseException):
        return ""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def report_error(tag, exc, *, note=None, detail=None) -> bool:
    """Record a failure the caller has already decided not to raise on.

    `tag` names the call site and must be a constant (see the throttle above);
    `note` carries what varies — which order, which customer, which of the several
    things that call site does.

    Returns whether a row was written — False for one the throttle dropped, and for
    one that could not be written at all. Never raises: every caller is inside an
    except block whose whole purpose is not failing, and a reporter that could throw
    would turn a missed WhatsApp into a 500 on an order that was paid for.
    """
    try:
        if getattr(_busy, "on", False):
            return False
        now = time.monotonic()
        with _lock:
            if now - _last.get(tag, 0.0) < _MIN_GAP_SECONDS:
                return False
            # Stamped before the write, not after: a database that is refusing
            # connections refuses them slowly, and a hundred callers queueing to find
            # that out one after another is its own outage.
            _last[tag] = now

        what = f"{type(exc).__name__}: {exc}" if isinstance(exc, BaseException) else str(exc)
        message = f"[{tag}] {note} — {what}" if note else f"[{tag}] {what}"
        body = detail if detail is not None else _trace(exc)
        # the tail, so a deep stack keeps the frames nearest the failure
        body = str(body)[-4000:] if body else None

        _busy.on = True
        try:
            execute("insert into error_reports (name, message, detail) values (%s, %s, %s)",
                    [_SERVER, message[:1000], body])
        finally:
            _busy.on = False
        return True
    except Exception as e:  # noqa: BLE001 — the reporter itself must never raise
        print("[errorlog] could not record:", e)
        return False
