"""Fire-and-forget work that outlives the request that started it.

Notifications go out on threads because the endpoints they talk to are a twenty-second
timeout away and nobody should hold a request open for them (see _send_order_whatsapp
and push.py). Under uvicorn that is free: the process stays up and the thread finishes
on its own.

A script has no such luxury. reconcile.py settles a payment, mark_paid starts the
customer's WhatsApp confirmation on a daemon thread, `__main__` returns — and
interpreter shutdown kills that thread wherever it happens to be, silently dropping the
one message the sweep exists to send. So the threads are registered here and a script
waits for them on its way out.
"""
import threading
import time

_lock = threading.Lock()
_threads = []


def spawn(target, *, name, args=(), kwargs=None):
    """Run `target` off the request path. Returns the thread, so a test can wait."""
    t = threading.Thread(target=target, name=name, args=args, kwargs=kwargs or {}, daemon=True)
    with _lock:
        # Pruning on the way in keeps a long-lived server from accumulating a
        # reference per notification it has ever sent.
        _threads[:] = [x for x in _threads if x.is_alive()]
        _threads.append(t)
    t.start()
    return t


def wait_all(timeout=30.0):
    """Give the outstanding sends their chance to finish. For scripts, not requests.

    Returns how many were still running when the wait ran out, so the caller can say
    so rather than exit looking successful.
    """
    deadline = time.monotonic() + timeout
    with _lock:
        pending = [t for t in _threads if t.is_alive()]
    for t in pending:
        t.join(max(0.0, deadline - time.monotonic()))
    return sum(1 for t in pending if t.is_alive())
