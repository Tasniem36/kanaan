"""Work that must outlive the request — but not the process that started it.

A notification goes out on a thread so nobody holds a request open for Meta's
twenty-second timeout. Under uvicorn that thread finishes on its own; in a script it
is killed at interpreter shutdown, which is how reconcile.py came to settle payments
and silently drop every confirmation it had just started sending.
"""
import threading

import background


def test_wait_all_waits_for_a_send_to_finish():
    done = threading.Event()
    background.spawn(lambda: (threading.Event().wait(0.05), done.set()), name="slow")
    assert background.wait_all(timeout=5) == 0
    assert done.is_set(), "a script must not exit while a confirmation is still going out"


def test_wait_all_reports_what_it_could_not_wait_for():
    """A stuck send is not a reason to hang a cron job forever — but the run must say
    so rather than exit looking like everything got through."""
    release = threading.Event()
    background.spawn(release.wait, name="stuck")
    try:
        assert background.wait_all(timeout=0.05) == 1
    finally:
        release.set()


def test_finished_threads_are_not_kept_forever():
    """The registry exists for scripts; in a long-lived server it must not grow a
    reference for every notification the shop has ever sent."""
    for _ in range(5):
        background.spawn(lambda: None, name="quick")
    background.wait_all(timeout=5)
    background.spawn(lambda: None, name="quick")  # prunes the dead ones on the way in
    assert len(background._threads) <= 2
    background.wait_all(timeout=5)
